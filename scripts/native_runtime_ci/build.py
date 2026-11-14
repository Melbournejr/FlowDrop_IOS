"""Same-run native TEST ONLY artifacts; reuse frozen 2C.2 builders/toolchain."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

from scripts.native_build_ci import runner as c2
from scripts.native_build_ci.paths import owned_root, fresh_child, remove_child, digest, write_json
from scripts.native_build_ci.toolchain import provision, tool_env
from scripts.native_build_ci.verify import verify_apk, pe_info, reject_secret_bytes
from .common import protected_source


def checksums(directory):
    directory = Path(directory)
    for path in directory.rglob('*'):
        if path.is_symlink() or path.suffix.lower() in ['.jks', '.keystore', '.p12', '.pfx', '.key']:
            raise RuntimeError('Unsafe runtime build export')
        if path.is_file():
            reject_secret_bytes(path.read_bytes())
    (directory / 'SHA256SUMS.txt').write_text(''.join(digest(path) + '  ' + path.relative_to(directory).as_posix() + '\n'
        for path in sorted(directory.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS.txt'), encoding='utf-8')


def extended_instrumentation(root, source, journal, env, key, adapt=False):
    """Build old four runners plus additional tests without editing protected Git files."""
    output = fresh_child(root, root / 'extended-instrumentation')
    java_source = output / 'src'
    java_source.mkdir()
    source_proof = []
    for file in sorted((source / 'tests/android-native-smoke').glob('*.java')) + sorted((source / 'tests/android-runtime').glob('*.java')):
        raw = file.read_bytes()
        compiled = raw
        if adapt and file.name == 'NativeSmoke.java':
            old = 'Tạo phiên trên điện thoại này'.encode()
            new = '● Điện thoại đang hiển thị trong Wi-Fi'.encode()
            if raw.count(old) != 2 or new not in (source / 'android/src/app/flowdrop/mobile/MainActivity.java').read_bytes():
                raise RuntimeError('Reviewed native selector adaptation no longer applies')
            compiled = raw.replace(old, new)
        (java_source / file.name).write_bytes(compiled)
        source_proof.append({'source': file.relative_to(source).as_posix(), 'original_sha256': hashlib.sha256(raw).hexdigest(),
                             'compiled_test_source_sha256': hashlib.sha256(compiled).hexdigest(), 'selector_only_adaptation': raw != compiled})
    manifest = ET.parse(source / 'tests/android-native-smoke/AndroidManifest.xml')
    ns = 'http://schemas.android.com/apk/res/android'
    ET.register_namespace('android', ns)
    ET.SubElement(manifest.getroot(), 'instrumentation', {'{' + ns + '}name': 'app.flowdrop.mobile.test.NativeRuntimeSmoke',
                  '{' + ns + '}targetPackage': 'app.flowdrop.mobile', '{' + ns + '}label': 'Phase 2D1 native runtime verification'})
    manifest_path = output / 'AndroidManifest.xml'
    manifest.write(manifest_path, encoding='utf-8', xml_declaration=True)
    bt, java = root / 'tools/sdk/build-tools/android-15', root / 'jdk/bin/java'
    jar = root / 'tools/sdk/platforms/android-35/android.jar'
    classes, dex = output / 'classes', output / 'dex'
    classes.mkdir(); dex.mkdir()
    journal.run('runtime-test-resources', [bt / 'aapt2', 'link', '-o', output / 'resources.apk', '-I', jar, '--manifest', manifest_path], env=env)
    journal.run('runtime-test-javac', [java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-source', '8', '-target', '8', '-encoding', 'UTF-8',
        '-bootclasspath', str(bt / 'core-lambda-stubs.jar') + os.pathsep + str(jar), '-classpath', str(jar) + os.pathsep + str(source / 'android/build/classes'),
        '-d', classes, *sorted(java_source.glob('*.java'))], env=env)
    journal.run('runtime-test-d8', [java, '-cp', bt / 'lib/d8.jar', 'com.android.tools.r8.D8', '--release', '--min-api', '29',
        '--lib', jar, '--classpath', source / 'android/build/classes', '--output', dex, *sorted(classes.rglob('*.class'))], env=env)
    unsigned = output / 'unsigned.apk'
    shutil.copyfile(output / 'resources.apk', unsigned)
    with zipfile.ZipFile(unsigned, 'a', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(dex.glob('*.dex')):
            archive.write(file, file.name)
    journal.run('runtime-test-zipalign', [bt / 'zipalign', '-f', '-p', '4', unsigned, output / 'aligned.apk'], env=env)
    apk = output / 'FlowDrop-runtime-tests.apk'
    journal.run('runtime-test-sign', [java, '-jar', bt / 'lib/apksigner.jar', 'sign', '--ks', key,
        '--ks-key-alias', 'flowdrop', '--ks-pass', 'env:FLOWDROP_ANDROID_STORE_PASSWORD', '--key-pass', 'env:FLOWDROP_ANDROID_KEY_PASSWORD',
        '--out', apk, output / 'aligned.apk'], env=env)
    return apk, {'original_tests_retained': 4, 'additional_runner': 'app.flowdrop.mobile.test.NativeRuntimeSmoke',
                  'manifest_sha256': digest(manifest_path), 'sources': source_proof, 'java8_classes': c2.classes_are_java8(classes)}


def android(root, cache, adapt):
    root = owned_root(root)
    protected_source()
    provision(root, cache, 'android')
    source, source_info = c2.source_snapshot(root)
    env = tool_env(root)
    env.update(FLOWDROP_NATIVE_WORK_ROOT=str(root), FLOWDROP_BUILD_STEP_REPORT=str(root / 'logs/builder-steps.jsonl'))
    journal = c2.Journal(root, env)
    try:
        signing, fingerprint = c2.make_test_key(root, journal)
        journal.run('build-app-from-source', [sys.executable, source / 'scripts/build-installers.py', '--only', 'android'], env=signing, cwd=source, timeout=1200)
        journal.run('build-original-instrumentation-from-source', [sys.executable, source / 'scripts/build-native-test-apk.py'], env=signing, cwd=source, timeout=600)
        app = source / 'artifacts/FlowDrop-1.13.0-Android.apk'
        original = root / 'tools/native-instrumentation/FlowDrop-native-tests.apk'
        original_result = verify_apk(original, source, root, journal, fingerprint, instrumentation=True)
        extended, proof = extended_instrumentation(root, source, journal, signing, signing['FLOWDROP_ANDROID_KEYSTORE'], adapt)
        report = {'status': 'PASS', 'exit_code': 0, 'role': 'android', 'source': source_info,
                  'app_java8_classes': c2.classes_are_java8(source / 'android/build/classes'),
                  'instrumentation_java8_classes': proof['java8_classes'], 'derived_test_harness': proof,
                  'original_instrumentation': original_result,
                  'android': verify_apk(app, source, root, journal, fingerprint),
                  'instrumentation': verify_apk(extended, source, root, journal, fingerprint, instrumentation=True),
                  'builder_steps': [json.loads(line) for line in (root / 'logs/builder-steps.jsonl').read_text().splitlines()],
                  'production_signing_equivalence': 'NOT VERIFIED', 'os_runtime': 'NOT VERIFIED; build job only'}
        if any(step['exit_code'] != 0 for step in report['builder_steps']):
            raise RuntimeError('Frozen builder reported a failed child')
        values = [signing['FLOWDROP_ANDROID_STORE_PASSWORD'], signing['FLOWDROP_ANDROID_KEY_PASSWORD']]
        remove_child(root, root / 'test-secrets')
        write_json(root / 'logs/build-results.json', report)
        c2.export_files(root, [(app, 'FlowDrop-1.13.0-Android-TEST-ONLY.apk'),
                        (extended, 'FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk')], report, journal, values)
        return report
    finally:
        if (root / 'test-secrets').exists():
            remove_child(root, root / 'test-secrets')


def windows(root, cache):
    protected_source()
    report = c2.build(root, cache, 'windows')
    root = Path(root)
    helpers = fresh_child(root, root / 'helper-build')
    env = tool_env(root)
    journal = c2.Journal(helpers, env)
    compiler = root / 'tools/mingw/usr/bin/x86_64-w64-mingw32-g++-posix'
    source = root / 'source'
    files = []
    for name in ['windows-native-smoke', 'windows-shell-smoke']:
        output = helpers / ('FlowDrop-' + name + '-TEST-ONLY.exe')
        journal.run('compile-' + name, [compiler, '-std=c++17', '-O2', '-s', '-municode', '-static', '-static-libgcc', '-static-libstdc++',
            '-I', source / 'desktop/windows/vendor', source / 'tests' / (name + '.cpp'), '-o', output,
            '-lwinhttp', '-lcomctl32', '-lole32', '-luuid', '-lshell32', '-luxtheme', '-lgdi32', '-luser32', '-ladvapi32'], timeout=600)
        pe = pe_info(output.read_bytes())
        if pe['machine'] != 0x8664 or pe['subsystem'] != 3:
            raise RuntimeError('Test helper must be a real Windows x64 console PE')
        files.append({'name': output.name, 'sha256': digest(output), 'size': output.stat().st_size,
                      'source': 'tests/' + name + '.cpp', 'source_sha256': digest(source / 'tests' / (name + '.cpp'))})
    export = fresh_child(root, root / 'helper-export')
    for record in files:
        shutil.copyfile(helpers / record['name'], export / record['name'])
    write_json(export / 'helper-manifest.json', {'status': 'PASS', 'purpose': 'TEST ONLY native OS smoke helpers',
               'source': report['source'], 'compiler_commands': journal.entries, 'files': files})
    checksums(export)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=['android', 'windows'], required=True)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--cache-root', required=True)
    parser.add_argument('--adapt-reviewed-selectors', action='store_true')
    args = parser.parse_args()
    root = owned_root(args.work_root)
    try:
        if args.role == 'android':
            android(root, Path(args.cache_root), args.adapt_reviewed_selectors)
        else:
            windows(root, Path(args.cache_root))
    except Exception as error:
        from scripts.native_build_support import redact
        write_json(root / 'logs/build-results.json', {'status': 'FAIL', 'exit_code': 1, 'reason': redact(str(error))})
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
