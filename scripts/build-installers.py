"""Build installable Windows x64 EXE and Android 10+ APK using local toolchains."""
from pathlib import Path
import os,shutil,zipfile,argparse,json,re,hashlib
from native_build_support import BuildError, load_signing, require_tool_root, run_command, report_failure
ROOT=Path(__file__).resolve().parents[1]
TOOLS=Path(os.environ.get('FLOWDROP_BUILD_TOOLS','/workspace/flowdrop-build'))
OUT=ROOT/'artifacts'
# Desktop and Android can ship independently. Use each platform's native version.
VERSION=re.search(r'!define VERSION "([^"]+)"',(ROOT/'desktop/windows/installer.nsi').read_text()).group(1)
import xml.etree.ElementTree as ET
ANDROID_VERSION=ET.parse(ROOT/'android/AndroidManifest.xml').getroot().attrib['{http://schemas.android.com/apk/res/android}versionName']
SDK=TOOLS/'sdk';BT=SDK/'build-tools/android-15';JAR=SDK/'platforms/android-35/android.jar'
def run(args,**kwargs):
    return run_command(args,**kwargs)
def android():
    signing=load_signing(ROOT)
    OUT.mkdir(exist_ok=True)
    build=ROOT/'android/build';shutil.rmtree(build,ignore_errors=True);build.mkdir(parents=True)
    for name in ['aapt2','zipalign']:(BT/name).chmod(0o755)
    run([BT/'aapt2','compile','--dir',ROOT/'android/res','-o',build/'resources.zip'])
    run([BT/'aapt2','link','-o',build/'resources.apk','-I',JAR,'--manifest',ROOT/'android/AndroidManifest.xml',build/'resources.zip'])
    classes=build/'classes';classes.mkdir()
    source=list((ROOT/'android/src').rglob('*.java'))
    boot=str(BT/'core-lambda-stubs.jar')+os.pathsep+str(JAR)
    run(['java','-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-bootclasspath',boot,'-classpath',JAR,'-d',classes,*source])
    dex=build/'dex';dex.mkdir()
    run(['java','-cp',BT/'lib/d8.jar','com.android.tools.r8.D8','--release','--min-api','29','--lib',JAR,'--output',dex,*classes.rglob('*.class')])
    unsigned=build/'unsigned.apk';shutil.copyfile(build/'resources.apk',unsigned)
    with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as archive:
        for f in dex.glob('*.dex'):archive.write(f,f.name)
        for asset in (ROOT/'web/assets/fonts').iterdir():
            if asset.is_file() and asset.suffix in ['.ttf','.txt']:archive.write(asset,'assets/fonts/'+asset.name)
    aligned=build/'aligned.apk';run([BT/'zipalign','-f','-p','4',unsigned,aligned])
    apk=OUT/('FlowDrop-'+ANDROID_VERSION+'-Android.apk')
    run(['java','-jar',BT/'lib/apksigner.jar','sign',*signing.arguments(),'--v1-signing-enabled','true','--v2-signing-enabled','true','--v3-signing-enabled','true','--out',apk,aligned],signing=True)
    run(['java','-jar',BT/'lib/apksigner.jar','verify','--verbose','--print-certs',apk])
    run([BT/'zipalign','-c','-p','4',apk])
    run([BT/'aapt2','dump','badging',apk])
    print('APK:',apk,flush=True)
def windows():
    if not (ROOT/'desktop/windows/FlowDrop.ico').is_file():raise BuildError('Original FlowDrop.ico is required; no substitute will be generated')
    OUT.mkdir(exist_ok=True)
    payload=TOOLS/'windows-payload';shutil.rmtree(payload,ignore_errors=True);payload.mkdir()
    for folder in ['web','worker','node_modules']:shutil.copytree(ROOT/folder,payload/folder)
    (payload/'scripts').mkdir()
    for f in ['request-security.mjs','device-name.mjs','dev.mjs','stop.mjs','discovery.mjs','desktop-storage.mjs','local-bucket.mjs','peer-offers.mjs','lan-discovery.mjs','folder-jobs.mjs','folder-zip.mjs','folder-receive.mjs','code-lookup.mjs','secure-update.mjs','release-config.mjs']:shutil.copyfile(ROOT/'scripts'/f,payload/'scripts'/f)
    for f in ['FlowDrop.vbs','Stop-FlowDrop.vbs','Allow-LAN.ps1']:shutil.copyfile(ROOT/'desktop/windows'/f,payload/f)
    mingw=TOOLS/'mingw/usr/bin'
    env=os.environ.copy();env['PATH']=str(mingw)+os.pathsep+env['PATH']
    run([mingw/'x86_64-w64-mingw32-windres','--preprocessor='+str(mingw/'x86_64-w64-mingw32-gcc-posix'),'--preprocessor-arg=-E','--preprocessor-arg=-xc','--preprocessor-arg=-DRC_INVOKED','FlowDrop.rc','-O','coff','-o',TOOLS/'flowdrop-res.o'],cwd=ROOT/'desktop/windows',env=env)
    run([mingw/'x86_64-w64-mingw32-g++-posix','-std=c++17','-O2','-s','-municode','-mwindows','-static','-static-libgcc','-static-libstdc++','-I',ROOT/'desktop/windows/vendor',ROOT/'desktop/windows/FlowDrop.cpp',TOOLS/'flowdrop-res.o','-o',payload/'FlowDrop.exe','-lwinhttp','-lcomctl32','-lole32','-luuid','-lshell32','-luxtheme','-lgdi32','-luser32','-ladvapi32'],env=env)
    shutil.copyfile(ROOT/'desktop/windows/vendor/json.hpp',payload/'nlohmann-json-license-and-source.hpp')
    shutil.copyfile(ROOT/'package.json',payload/'package.json')
    shutil.copyfile(ROOT/'INSTALL.md',payload/'Huong-dan.md')
    runtime=payload/'runtime';runtime.mkdir()
    runtime_pin=json.loads((ROOT/'desktop/windows/runtime.json').read_text());node=TOOLS/('windows-runtime/node-v'+runtime_pin['nodeVersion']+'-win-x64')
    if hashlib.sha256((node/'node.exe').read_bytes()).hexdigest()!=runtime_pin['executableSha256']:raise BuildError('Bundled Node runtime SHA256 differs from the verified official release.')
    for name in ['node.exe','LICENSE']:shutil.copyfile(node/name,runtime/name)
    nsis=TOOLS/'nsis/usr'
    env=os.environ.copy();env['NSISDIR']=str(nsis/'share/nsis')
    exe=OUT/('FlowDrop-Setup-'+VERSION+'-Windows-x64.exe')
    run([nsis/'bin/makensis','-V3','-DPAYLOAD_DIR='+str(payload),'-DOUTPUT_FILE='+str(exe),ROOT/'desktop/windows/installer.nsi'],env=env)
    print('EXE:',exe,flush=True)
def main():
    global TOOLS,SDK,BT,JAR
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['android','windows']);args=parser.parse_args()
    try:
        TOOLS=require_tool_root();SDK=TOOLS/'sdk';BT=SDK/'build-tools/android-15';JAR=SDK/'platforms/android-35/android.jar'
        if args.only!='windows':android()
        if args.only!='android':windows()
    except (BuildError,OSError,ValueError) as error:
        return report_failure(error)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
