"""Build fresh production-layout candidates, never load a signing key or publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import zlib
import struct
import xml.etree.ElementTree as ET

from scripts.native_build_ci.paths import REPO, owned_root, fresh_child, digest, write_json, safe_extract_zip
from scripts.native_build_ci.runner import Journal, source_snapshot, classes_are_java8
from scripts.native_build_ci.toolchain import provision, tool_env, fetch
from scripts.native_build_ci.verify import apk_identity, reject_secret_bytes, verify_windows_payload, verify_installer, PRODUCTION_CERT

WINDOWS_JRE = {
    'id': 'temurin-windows-jre', 'filename': 'windows-jre.zip', 'size': 49106397,
    'url': 'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip',
    'sha256': '2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628',
    'provenance': 'Official Adoptium release asset digest and adjacent .sha256.txt, independently read 2026-11-19',
    'license': 'GPLv2 with Classpath Exception; legal notices included inside the official archive',
}

def unsigned_apk(apk, source, root, journal):
    tools = root / 'tools/sdk/build-tools/android-15'
    journal.run('unsigned-zipalign', [tools / 'zipalign', '-c', '-p', '4', apk])
    identity = apk_identity(journal.run('unsigned-badging', [tools / 'aapt2', 'dump', 'badging', apk]))
    assert identity['package'] == 'app.flowdrop.mobile' and identity['version_name'] == '1.14.0' and identity['version_code'] == '15'
    assert identity['min_sdk'] == 29 and identity['target_sdk'] == 35
    ns='{http://schemas.android.com/apk/res/android}'
    manifest=ET.parse(source/'android/AndroidManifest.xml').getroot()
    assert identity['permissions']==sorted({n.get(ns+'name') for n in manifest if n.tag.startswith('uses-permission')})
    journal.run('unsigned-manifest', [tools / 'aapt2', 'dump', 'xmltree', apk, '--file', 'AndroidManifest.xml'])
    result = subprocess.run([root / 'jdk/bin/java', '-jar', tools / 'lib/apksigner.jar', 'verify', apk], capture_output=True, timeout=120)
    assert result.returncode == 1 and b'DOES NOT VERIFY' in result.stdout+result.stderr, 'Unsigned signature check did not produce the expected verification failure'
    entries = []
    with zipfile.ZipFile(apk) as z:
        assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist()))
        assert not any(n.startswith('META-INF/') for n in z.namelist())
        for entry in z.infolist():
            assert entry.file_size <= 64*1024*1024 and not entry.filename.startswith('/') and '..' not in Path(entry.filename).parts
            data = z.read(entry); reject_secret_bytes(data)
            if entry.filename.endswith('.dex'):
                assert len(data)>=112 and data[:4]==b'dex\n' and hashlib.sha1(data[32:]).digest()==data[12:32] and zlib.adler32(data[12:]) & 0xffffffff==struct.unpack_from('<I',data,8)[0]
            if entry.filename.startswith('assets/fonts/'):
                assert data == (source / 'web' / entry.filename).read_bytes()
            entries.append({'path': entry.filename, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    required = {'AndroidManifest.xml', 'classes.dex', 'resources.arsc', 'assets/fonts/OFL.txt'}
    assert required.issubset({x['path'] for x in entries})
    return {'package': identity['package'], 'version': '1.14.0', 'versionCode': 15, 'minSdk': 29, 'targetSdk': 35,
            'permissions': identity['permissions'], 'sha256': digest(apk), 'size': apk.stat().st_size,
            'entries': entries, 'productionCertificateRequired': PRODUCTION_CERT, 'signed': False}

def install_locked_dependencies(root, source, journal):
    user = root / 'empty-user.npmrc'; user.write_text('')
    global_config = root / 'empty-global.npmrc'; global_config.write_text('')
    journal.run('release-npm-ci', [root / 'node-linux/bin/node', root / 'node-linux/lib/node_modules/npm/bin/npm-cli.js', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--cache', root / 'npm-cache', '--registry', 'https://registry.npmjs.org/', '--userconfig', user, '--globalconfig', global_config], cwd=source, timeout=600)

def prepare(root, cache):
    root = owned_root(root); provision(root, cache, 'all')
    source, info = source_snapshot(root); env = tool_env(root)
    env.update(FLOWDROP_NATIVE_WORK_ROOT=str(root), FLOWDROP_BUILD_STEP_REPORT=str(root / 'logs/builder-steps.jsonl'))
    journal = Journal(root, env)
    install_locked_dependencies(root, source, journal)
    journal.run('release-unsigned-android', [sys.executable, source / 'scripts/build-installers.py', '--only', 'android', '--unsigned'], cwd=source, timeout=1200)
    journal.run('release-production-windows', [sys.executable, source / 'scripts/build-installers.py', '--only', 'windows'], cwd=source, timeout=1800)
    apk = source / 'artifacts/FlowDrop-1.14.0-Android-UNSIGNED.apk'
    exe = source / 'artifacts/FlowDrop-Setup-1.14.0-Windows-x64.exe'
    android = unsigned_apk(apk, source, root, journal)
    payload = root / 'tools/windows-payload'
    windows = verify_windows_payload(payload, source); installer = verify_installer(exe, payload, root, journal)
    head = os.environ.get('FLOWDROP_REVIEWED_HEAD', subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    proof = {'sourceHead': head, 'source': info, 'android': android, 'windows': {'size': exe.stat().st_size, 'sha256': digest(exe)}, 'signingStatus': 'BLOCKED pending owner local original keys; never use CI TEST ONLY APK'}
    export = fresh_child(root, root / 'release-export'); kit = fresh_child(root, root / 'signing-kit')
    for file in [apk, exe]: shutil.copyfile(file, kit / file.name)
    shutil.copyfile(source / 'docs/releases/Release-notes-1.14.0.md', kit / 'Release-notes-1.14.0.md')
    write_json(kit / 'production-build-proof.json', proof)
    (kit / 'scripts').mkdir(); (kit / 'tools').mkdir()
    for name in ['make-release.mjs','release-support.mjs','secure-update.mjs','release-config.mjs']:
        shutil.copyfile(source / 'scripts' / name, kit / 'scripts' / name)
    shutil.copyfile(source / 'scripts/Start-ReleaseSigning.ps1', kit / 'Start-ReleaseSigning.ps1')
    shutil.copyfile(payload / 'runtime/node.exe', kit / 'tools/node.exe')
    shutil.copyfile(payload / 'runtime/LICENSE', kit / 'tools/Node-LICENSE.txt')
    bt = root / 'tools/sdk/build-tools/android-15'
    shutil.copyfile(bt / 'lib/apksigner.jar', kit / 'tools/apksigner.jar')
    shutil.copyfile(bt / 'NOTICE.txt', kit / 'tools/Android-build-tools-NOTICE.txt')
    jre = fetch(WINDOWS_JRE, cache)
    # Verify names/types before including an archive the owner will expand.
    check = fresh_child(root, root / 'windows-jre-inspection'); safe_extract_zip(jre, check)
    assert (check / 'jdk-21.0.13+9-jre/bin/java.exe').is_file()
    shutil.rmtree(check)
    shutil.copyfile(jre, kit / 'tools/windows-jre.zip'); write_json(kit / 'tools/windows-jre-source.json', WINDOWS_JRE)
    (kit / 'READ-ME.txt').write_text('FlowDrop 1.14.0 local signing kit. UNSIGNED APK is NOT installable. Keep both original keys outside this directory. Run: powershell -NoProfile -ExecutionPolicy Bypass -File .\\Start-ReleaseSigning.ps1\nOnly the five public output files belong in the Draft Release. No keys/passwords are uploaded. Do not uninstall FlowDrop 1.13.0. Turbo is experimental.\n', encoding='utf-8')
    records = [{'path': p.relative_to(kit).as_posix(), 'sha256': digest(p)} for p in sorted(kit.rglob('*')) if p.is_file()]
    write_json(kit / 'kit-files.json', records)
    archive = export / 'FlowDrop-1.14.0-LOCAL-SIGNING-KIT.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for file in sorted(kit.rglob('*')):
            if file.is_file(): z.write(file, file.relative_to(kit).as_posix())
    shutil.copyfile(exe, export / exe.name); shutil.copyfile(kit / 'Release-notes-1.14.0.md', export / 'Release-notes-1.14.0.md')
    write_json(export / 'production-build-proof.json', proof)
    write_json(export / 'release-preparation.json', {'status':'PASS','meaning':'Unsigned APK and production-layout Windows source build/structure only','productionSigning':'BLOCKED pending original local keys','sourceHead':head,'java8Classes':classes_are_java8(source / 'android/build/classes'),'windowsPayload':windows,'windowsInstaller':installer,'android':android,'windowsJre':WINDOWS_JRE})
    (export / 'CANDIDATE-SHA256SUMS.txt').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(export.iterdir()) if p.is_file()))
    for file in export.iterdir():
        if file.is_file(): reject_secret_bytes(file.read_bytes())
    print('PASS: fresh unsigned Android and production Windows candidates. Production APK/RSA signing NOT VERIFIED; owner action required.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work-root',required=True);parser.add_argument('--cache-root',required=True);args=parser.parse_args()
    prepare(Path(args.work_root),Path(args.cache_root))
