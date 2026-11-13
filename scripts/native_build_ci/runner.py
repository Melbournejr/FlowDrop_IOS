"""Build test-only native installers using isolated sources and ephemeral keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time

from scripts.native_build_support import redact
from .paths import Blocked, REPO, digest, fresh_child, owned_root, remove_child, write_json
from .toolchain import provision, read_lock, tool_env
from .verify import PRODUCTION_CERT, reject_secret_bytes, verify_apk, verify_windows_payload, verify_installer


class StepFailed(RuntimeError):
    pass


class Journal:
    def __init__(self, root, env):
        self.root, self.env, self.entries = Path(root), dict(env), []
        (self.root / 'logs').mkdir(exist_ok=True)

    def run(self, name, command, env=None, timeout=900, cwd=None):
        env = self.env if env is None else env
        argv = [str(value) for value in command]
        entry = {'name': name, 'command': [redact(value, env) for value in argv], 'status': 'NOT VERIFIED', 'exit_code': None}
        started = time.monotonic()
        child, output = None, ''
        print('RUN:', name, flush=True)
        try:
            child = subprocess.Popen(argv, cwd=cwd or REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, errors='replace', start_new_session=True)
            try:
                output, _ = child.communicate(timeout=timeout)
                code = child.returncode if child.returncode >= 0 else 128 - child.returncode
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                output, _ = child.communicate()
                code = 124
            entry.update(exit_code=code, raw_returncode=child.returncode, status='PASS' if code == 0 else 'FAIL')
        except OSError as error:
            entry.update(exit_code=127, status='BLOCKED', error=type(error).__name__)
        finally:
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            entry['wall_seconds'] = round(time.monotonic() - started, 3)
            log = self.root / 'logs' / (name + '.log')
            log.write_text(redact(output, env))
            entry['log_sha256'] = digest(log)
            self.entries.append(entry)
            write_json(self.root / 'logs/commands.json', self.entries)
        print(entry['status'] + ': ' + name + ' exit=' + str(entry['exit_code']), flush=True)
        if entry['exit_code'] != 0:
            raise StepFailed(name + ' exit ' + str(entry['exit_code']))
        return output


def source_snapshot(root):
    source = fresh_child(root, root / 'source')
    baseline = json.loads((REPO / 'docs/build/NATIVE-SOURCE-BASELINE-2C2.json').read_text())
    for record in baseline['files']:
        if digest(REPO / record['path']) != record['sha256']:
            raise Blocked('Protected production/baseline file changed: ' + record['path'])
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    for name in names:
        file = REPO / name
        if '..' in Path(name).parts or Path(name).is_absolute() or file.is_symlink() or not file.is_file():
            raise Blocked('Unexpected source snapshot entry')
        if name.startswith(('artifacts/', 'node_modules/', '.git/')) or file.suffix.lower() in ('.jks', '.keystore', '.p12', '.pfx', '.key'):
            raise Blocked('Signing/build/cache material in source snapshot')
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
    return source, {'base_commit': baseline['base'], 'protected_files_checked': len(baseline['files']),
                    'production_source_equivalence': 'PASS', 'snapshot_files': len(names),
                    'checkout_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                    'uncommitted_paths': subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).splitlines()}


def make_test_key(root, journal):
    directory = fresh_child(root, root / 'test-secrets')
    directory.chmod(0o700)
    env = dict(journal.env)
    env.update(FLOWDROP_ANDROID_KEYSTORE=str(directory / 'flowdrop-2c2-test.jks'),
               FLOWDROP_ANDROID_STORE_PASSWORD=secrets.token_urlsafe(32),
               FLOWDROP_ANDROID_KEY_PASSWORD=secrets.token_urlsafe(32))
    keytool = root / 'jdk/bin/keytool'
    old_umask = os.umask(0o077)
    try:
        journal.run('generate-temporary-test-key', [keytool, '-genkeypair', '-alias', 'flowdrop', '-keyalg', 'RSA', '-keysize', '3072',
                    '-sigalg', 'SHA256withRSA', '-validity', '3', '-dname', 'CN=FlowDrop 2C2 TEST ONLY', '-storetype', 'JKS',
                    '-keystore', env['FLOWDROP_ANDROID_KEYSTORE'], '-storepass:env', 'FLOWDROP_ANDROID_STORE_PASSWORD',
                    '-keypass:env', 'FLOWDROP_ANDROID_KEY_PASSWORD', '-noprompt'], env=env)
        public = root / 'test-certificate.der'
        journal.run('export-test-public-certificate', [keytool, '-exportcert', '-alias', 'flowdrop', '-keystore', env['FLOWDROP_ANDROID_KEYSTORE'],
                    '-storepass:env', 'FLOWDROP_ANDROID_STORE_PASSWORD', '-file', public], env=env)
    finally:
        os.umask(old_umask)
    fingerprint = digest(public)
    if fingerprint == PRODUCTION_CERT:
        raise Blocked('Temporary key unexpectedly matches production identity')
    write_json(root / 'test-certificate.json', {'purpose': 'FlowDrop 2C2 TEST ONLY', 'sha256': fingerprint})
    return env, fingerprint


def classes_are_java8(directory):
    count = 0
    for path in Path(directory).rglob('*.class'):
        header = path.read_bytes()[:8]
        if header[:4] != b'\xca\xfe\xba\xbe' or int.from_bytes(header[6:8], 'big') != 52:
            raise Blocked('Java bytecode target differs from Java 8')
        count += 1
    if count == 0:
        raise Blocked('No Java classes were compiled')
    return count


def export_files(root, records, manifest, journal, secrets_to_check=()):
    export = fresh_child(root, root / 'export')
    for original, name in records:
        original = Path(original)
        if not original.is_file() or not name.endswith(('-TEST-ONLY.apk', '-TEST-ONLY.exe')):
            raise Blocked('Only verified TEST-ONLY installers may be exported')
        shutil.copyfile(original, export / name)
    write_json(export / 'artifact-manifest.json', manifest)
    # Only filtered logs and public verification metadata; never a whole work root.
    logs = export / 'logs'
    logs.mkdir()
    for file in (root / 'logs').iterdir():
        if file.suffix in ['.log', '.json', '.jsonl']:
            shutil.copyfile(file, logs / file.name)
    checksums = ''.join(digest(path) + '  ' + path.relative_to(export).as_posix() + '\n'
                        for path in sorted(export.rglob('*')) if path.is_file())
    (export / 'SHA256SUMS.txt').write_text(checksums)
    # Final allowlist check before the workflow can upload this directory.
    for file in export.rglob('*'):
        if file.is_symlink() or file.suffix.lower() in ['.jks', '.keystore', '.p12', '.pfx', '.key']:
            raise Blocked('Unsafe export entry')
        if file.is_file():
            reject_secret_bytes(file.read_bytes(), secrets_to_check)
    return export


def build(root, cache, role):
    root = owned_root(root)
    report = {'status': 'NOT VERIFIED', 'role': role, 'production_signing_equivalence': 'NOT VERIFIED', 'os_smoke': 'NOT VERIFIED'}
    provision(root, cache, role)
    source, source_info = source_snapshot(root)
    env = tool_env(root)
    env.update(FLOWDROP_NATIVE_WORK_ROOT=str(root), FLOWDROP_BUILD_STEP_REPORT=str(root / 'logs/builder-steps.jsonl'))
    journal = Journal(root, env)
    report['source'] = source_info
    try:
        values = []
        if role == 'android':
            signing_env, fingerprint = make_test_key(root, journal)
            signing_env.update(FLOWDROP_NATIVE_WORK_ROOT=str(root), FLOWDROP_BUILD_STEP_REPORT=str(root / 'logs/builder-steps.jsonl'))
            journal.run('build-app-from-source', [sys.executable, source / 'scripts/build-installers.py', '--only', 'android'], env=signing_env, cwd=source, timeout=1200)
            journal.run('build-instrumentation-from-source', [sys.executable, source / 'scripts/build-native-test-apk.py'], env=signing_env, cwd=source, timeout=600)
            report['app_java8_classes'] = classes_are_java8(source / 'android/build/classes')
            report['instrumentation_java8_classes'] = classes_are_java8(root / 'tools/native-instrumentation/classes')
            app = source / 'artifacts/FlowDrop-1.13.0-Android.apk'
            instrumentation = root / 'tools/native-instrumentation/FlowDrop-native-tests.apk'
            values = [signing_env['FLOWDROP_ANDROID_STORE_PASSWORD'], signing_env['FLOWDROP_ANDROID_KEY_PASSWORD']]
            report['android'] = verify_apk(app, source, root, journal, fingerprint, secrets=values)
            report['instrumentation'] = verify_apk(instrumentation, source, root, journal, fingerprint, instrumentation=True, secrets=values)
            records = [(app, 'FlowDrop-1.13.0-Android-TEST-ONLY.apk'), (instrumentation, 'FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk')]
            remove_child(root, root / 'test-secrets')
            del signing_env
        else:
            npmrc = root / 'empty-user.npmrc'
            global_npmrc = root / 'empty-global.npmrc'
            npmrc.write_text('')
            global_npmrc.write_text('')
            journal.run('locked-npm-ci', [root / 'node-linux/bin/node', root / 'node-linux/lib/node_modules/npm/bin/npm-cli.js', 'ci', '--ignore-scripts',
                        '--no-audit', '--no-fund', '--cache', root / 'npm-cache', '--registry', 'https://registry.npmjs.org/',
                        '--userconfig', npmrc, '--globalconfig', global_npmrc], cwd=source, timeout=600)
            journal.run('build-windows-from-source', [sys.executable, source / 'scripts/build-installers.py', '--only', 'windows'], cwd=source, timeout=1800)
            payload = root / 'tools/windows-payload'
            installer = source / 'artifacts/FlowDrop-Setup-1.13.0-Windows-x64.exe'
            report['windows_payload'] = verify_windows_payload(payload, source)
            report['windows_installer'] = verify_installer(installer, payload, root, journal)
            records = [(installer, 'FlowDrop-Setup-1.13.0-Windows-x64-TEST-ONLY.exe')]
        report.update(status='PASS', build_and_structural_verification='PASS', exit_code=0)
        report['builder_steps'] = [json.loads(line) for line in (root / 'logs/builder-steps.jsonl').read_text().splitlines()]
        if not report['builder_steps'] or any(step['exit_code'] != 0 for step in report['builder_steps']):
            raise Blocked('A real compiler/packager step did not pass')
        write_json(root / 'logs/build-results.json', report)
        export_files(root, records, report, journal, values)
        return report
    finally:
        if (root / 'test-secrets').exists():
            remove_child(root, root / 'test-secrets')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=['android', 'windows'], required=True)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--cache-root', required=True)
    args = parser.parse_args()
    root = owned_root(args.work_root)
    try:
        build(root, Path(args.cache_root), args.role)
    except Exception as error:
        write_json(root / 'logs/build-results.json', {'status': 'FAIL' if isinstance(error, StepFailed) else 'BLOCKED',
                   'exit_code': 1, 'reason': str(error), 'role': args.role, 'completed_build_verification': False})
        print('FAIL/BLOCKED: native build verification; see sanitized result', flush=True)
        return 1
    print('PASS: build and structural verification only; runtime/production signing remain separately reported', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
