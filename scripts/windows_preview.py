"""Build a side-by-side Windows Preview in a separate working source tree."""
import hashlib
import os
import re
import json
from pathlib import Path
import shutil
import sys

from scripts.android_preview import replace_once
from scripts.native_build_ci.paths import fresh_child, write_json

LABEL = 'FlowDrop Preview'
EXE = 'FlowDropPreview.exe'
SETUP = 'FlowDrop-Preview-Setup-1.14.0-Windows-x64-TEST-ONLY.exe'
REGISTRY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDropPreview'
UPDATER = '''export class DesktopUpdater {
 constructor({version='1.14.0',busy=()=>false}={}){this.isBusy=busy;this.state={phase:'disabled',version,automatic:false,accepted:false,preview:true,bytes:0,size:0};}
 async start(){} close(){} resume(){}
 snapshot(){return {...this.state,busy:this.isBusy(),canApply:false};}
 async configure(){return this.snapshot();}
 check(){return this.snapshot();} later(){return this.snapshot();} installFailed(){return this.snapshot();}
 accept(){throw Error('FlowDrop Preview không dùng kênh cập nhật production.');}
 async prepareInstall(){throw Error('Cài bản Preview mới bằng bộ cài riêng.');}
}
'''


def prepare(source, root):
    source, root = Path(source).resolve(), Path(root).resolve()
    if source == root or source == root / 'windows-preview-source':
        raise RuntimeError('Preview requires a separate working source')
    output = fresh_child(root, root / 'windows-preview-source')
    for folder in ['desktop/windows', 'web', 'worker', 'node_modules', 'scripts']:
        # Sources are already checked by source_snapshot; don't copy build/cache.
        shutil.copytree(source / folder, output / folder, ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['package.json', 'package-lock.json', 'INSTALL.md']:
        shutil.copyfile(source / name, output / name)
    (output / 'android').mkdir()
    shutil.copyfile(source / 'android/AndroidManifest.xml', output / 'android/AndroidManifest.xml')
    cpp = output / 'desktop/windows/FlowDrop.cpp'
    text = cpp.read_text(encoding='utf-8').replace('FlowDrop', LABEL)
    text = replace_once(text, 'void checkUpdate(){', 'void checkUpdate(){MessageBoxW(window,L"Preview không tự động cập nhật. Cài bản Preview mới bằng bộ cài riêng.",L"FlowDrop Preview",MB_OK|MB_ICONINFORMATION);return;')
    text = replace_once(text, 'EnableWindow(updateAutoCheck,ready&&!applyingUpdate)', 'EnableWindow(updateAutoCheck,FALSE)')
    commit = os.environ.get('FLOWDROP_REVIEWED_HEAD', '')
    build = commit if re.fullmatch(r'[a-f0-9]{40}', commit) else 'source'
    text = '#define FLOWDROP_PREVIEW_BUILD \"' + build + '\"\n' + text
    cpp.write_text(text, encoding='utf-8')
    rc = output / 'desktop/windows/FlowDrop.rc'
    text = rc.read_text(encoding='utf-8').replace('"FlowDrop.exe\\0"', '"FlowDropPreview.exe\\0"').replace('"FlowDrop native Windows application\\0"', '"FlowDrop Preview native Windows application\\0"').replace('"ProductName", "FlowDrop\\0"', '"ProductName", "FlowDrop Preview\\0"')
    rc.write_text(text, encoding='utf-8')
    nsi = output / 'desktop/windows/installer.nsi'
    text = nsi.read_text(encoding='utf-8').replace('FlowDrop.exe', EXE)
    text = text.replace('$LOCALAPPDATA\\Programs\\FlowDrop"', '$LOCALAPPDATA\\Programs\\FlowDrop Preview"')
    text = text.replace('$SMPROGRAMS\\FlowDrop', '$SMPROGRAMS\\FlowDrop Preview').replace('$DESKTOP\\FlowDrop.lnk', '$DESKTOP\\FlowDrop Preview.lnk').replace('$SENDTO\\FlowDrop.lnk', '$SENDTO\\FlowDrop Preview.lnk')
    text = text.replace('\\FlowDrop.lnk', '\\FlowDrop Preview.lnk').replace('\\Stop FlowDrop.lnk', '\\Stop FlowDrop Preview.lnk')
    text = text.replace('CurrentVersion\\Uninstall\\FlowDrop"', 'CurrentVersion\\Uninstall\\FlowDropPreview"')
    text = text.replace('"FlowDrop"', '"FlowDrop Preview"').replace('"FlowDrop Setup"', '"FlowDrop Preview Setup"').replace('"Mo FlowDrop"', '"Mo FlowDrop Preview"')
    guard = '''
 # Never overwrite the original executable, including a silent custom /D path.
 IfFileExists "$INSTDIR\\FlowDrop.exe" 0 +3
 SetErrorLevel 2
 Abort
'''
    text = replace_once(text, 'Section "FlowDrop Preview" SEC_MAIN', 'Section "FlowDrop Preview" SEC_MAIN' + guard)
    # NSIS must release its output/current directory before removing it.
    text = replace_once(text, ' RMDir /r "$INSTDIR"', ''' SetOutPath "$TEMP"
 RMDir /r "$INSTDIR"
 # A just-closed app/backend can briefly retain its working-directory handle.
 # Retry only the empty program directory; never recurse into user data again.
 StrCpy $R2 40
 preview_directory_retry:
 ClearErrors
 RMDir "$INSTDIR"
 IfErrors 0 preview_directory_done
 IntOp $R2 $R2 - 1
 StrCmp $R2 0 preview_directory_done
 Sleep 250
 Goto preview_directory_retry
 preview_directory_done:''')
    text += '''
Function .onVerifyInstDir
 IfFileExists "$INSTDIR\\FlowDrop.exe" 0 +2
 Abort
FunctionEnd
'''
    nsi.write_text(text, encoding='utf-8')
    for name in ['FlowDrop.vbs', 'Stop-FlowDrop.vbs']:
        file = output / 'desktop/windows' / name
        text = file.read_text(encoding='utf-8').replace('\\FlowDrop.exe', '\\' + EXE).replace('\\FlowDrop\\Data', '\\FlowDrop Preview\\Data')
        file.write_text(text, encoding='utf-8')
    file = output / 'desktop/windows/Allow-LAN.ps1'
    file.write_text(file.read_text().replace('FlowDrop-LAN-', 'FlowDrop-Preview-LAN-').replace('FlowDrop Wi-Fi ', 'FlowDrop Preview Wi-Fi '), encoding='utf-8')
    file = output / 'scripts/build-installers.py'
    text = file.read_text(encoding='utf-8')
    text = text.replace("TOOLS/'windows-payload'", "TOOLS/'windows-preview-payload'").replace("TOOLS/'flowdrop-res.o'", "TOOLS/'flowdrop-preview-res.o'")
    text = text.replace("payload/'FlowDrop.exe'", "payload/'FlowDropPreview.exe'").replace("'FlowDrop-Setup-'", "'FlowDrop-Preview-Setup-'")
    file.write_text(text, encoding='utf-8')
    file = output / 'scripts/dev.mjs'
    text = file.read_text(encoding='utf-8')
    text = replace_once(text, "data=process.env.FLOWDROP_DATA_DIR||path.join(root,'.local-data')", "data=process.platform==='win32'?path.join(process.env.LOCALAPPDATA,'FlowDrop Preview','Data'):(process.env.FLOWDROP_DATA_DIR||path.join(root,'.preview-data'))")
    text = replace_once(text, 'process.env.FLOWDROP_DEVICE_NAME||hostname()', "process.env.FLOWDROP_DEVICE_NAME||('Preview · '+hostname())")
    file.write_text(text, encoding='utf-8')
    file = output / 'scripts/stop.mjs'
    text = file.read_text(encoding='utf-8')
    begin, end = text.index('const folder='), text.index('\nconst stateFile=')
    file.write_text(text[:begin] + "const folder=process.platform==='win32'?path.join(process.env.LOCALAPPDATA,'FlowDrop Preview','Data'):'.preview-data';" + text[end:], encoding='utf-8')
    file = output / 'scripts/desktop-storage.mjs'
    file.write_text(file.read_text(encoding='utf-8').replace("'FlowDrop'", "'FlowDrop Preview'"), encoding='utf-8')
    (output / 'scripts/secure-update.mjs').write_text(UPDATER, encoding='utf-8')
    file = output / 'INSTALL.md'
    file.write_text('FlowDrop Preview Windows: app/data/Downloads/shortcuts are separate from FlowDrop. No production auto-updates. Install a new Preview manually. Uninstall only Preview to remove its program; its received files are retained.\n\n' + file.read_text(encoding='utf-8'), encoding='utf-8')
    proof = {'label': LABEL, 'executable': EXE, 'install_directory': r'%LOCALAPPDATA%\Programs\FlowDrop Preview',
             'data_directory': r'%LOCALAPPDATA%\FlowDrop Preview\Data', 'downloads_directory': r'%USERPROFILE%\Downloads\FlowDrop Preview',
             'window_class': 'FlowDrop Preview.NativeDesktop', 'mutex': r'Local\FlowDrop Preview.NativeDesktop.1',
             'uninstall_registry': REGISTRY, 'updates': 'disabled; no feed or installer entry point',
             'source_overlay': [{'path': p.relative_to(output).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in sorted(output.rglob('*')) if p.is_file() and 'node_modules' not in p.parts]}
    write_json(root / 'logs/windows-preview-source.json', proof)
    return output, proof


def build(source, root, journal, env):
    from scripts.native_build_ci.verify import verify_windows_payload, verify_installer
    output, proof = prepare(source, root)
    journal.run('build-windows-preview-from-source', [sys.executable, output / 'scripts/build-installers.py', '--only', 'windows'],
                env=env, cwd=output, timeout=1800)
    payload = Path(root) / 'tools/windows-preview-payload'
    setup = output / 'artifacts/FlowDrop-Preview-Setup-1.14.0-Windows-x64.exe'
    class PreviewJournal:
        def run(self, name, *args, **kwargs):
            return journal.run('preview-' + name, *args, **kwargs)
    result = {'status': 'PASS', 'overlay': proof, 'windows_payload': verify_windows_payload(payload, output, preview=True),
              'windows_installer': verify_installer(setup, payload, root, PreviewJournal(), preview=True)}
    return setup, result
