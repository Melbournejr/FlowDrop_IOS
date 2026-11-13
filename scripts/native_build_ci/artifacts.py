"""Re-verify downloaded TEST ONLY artifacts in a job independent of builders."""
import argparse
import json
from pathlib import Path
import re
import shutil

from .paths import Blocked, REPO, archive_name, digest, fresh_child, owned_root, write_json
from .runner import Journal, source_snapshot
from .toolchain import provision, tool_env
from .verify import (PRODUCTION_CERT, inspect_installer, reject_secret_bytes,
                     verify_apk, verify_windows_payload)

NAMES = {
    'android': {'FlowDrop-1.13.0-Android-TEST-ONLY.apk', 'FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk'},
    'windows': {'FlowDrop-Setup-1.13.0-Windows-x64-TEST-ONLY.exe'},
}
PLUGINS = {'$PLUGINSDIR/modern-wizard.bmp', '$PLUGINSDIR/nsDialogs.dll', '$PLUGINSDIR/System.dll'}


def check_export(directory, role):
    directory = Path(directory).resolve()
    paths = set()
    for file in directory.rglob('*'):
        if file.is_symlink():
            raise Blocked('Artifact export contains a link')
        if file.is_file():
            name = file.relative_to(directory).as_posix()
            if name not in NAMES[role] | {'artifact-manifest.json', 'SHA256SUMS.txt'} and not (
                    name.startswith('logs/') and len(Path(name).parts) == 2 and file.suffix in ['.json', '.jsonl', '.log']):
                raise Blocked('Artifact export contains an unexpected file')
            reject_secret_bytes(file.read_bytes())
            paths.add(name)
    checksums = {}
    for line in (directory / 'SHA256SUMS.txt').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or archive_name(match[2]) is None or match[2] in checksums:
            raise Blocked('Malformed/duplicate artifact checksum record')
        checksums[match[2]] = match[1]
    if set(checksums) != paths - {'SHA256SUMS.txt'} or not NAMES[role].issubset(paths):
        raise Blocked('Artifact checksum inventory incomplete')
    for name, expected in checksums.items():
        if digest(directory / name) != expected:
            raise Blocked('Downloaded artifact SHA-256 mismatch')
    manifest = json.loads((directory / 'artifact-manifest.json').read_text())
    if manifest.get('status') != 'PASS' or manifest.get('role') != role:
        raise Blocked('Builder did not complete verification')
    if not manifest.get('builder_steps') or any(step['exit_code'] != 0 for step in manifest['builder_steps']):
        raise Blocked('Builder tool exit codes are incomplete or failed')
    return manifest


def verify_downloads(root, cache, android, windows):
    root = owned_root(root)
    manifests = {'android': check_export(android, 'android'), 'windows': check_export(windows, 'windows')}
    provision(root, cache, 'verify')
    source, source_info = source_snapshot(root)
    journal = Journal(root, tool_env(root))
    certificate = manifests['android']['android']['test_certificate_sha256']
    app = verify_apk(Path(android) / 'FlowDrop-1.13.0-Android-TEST-ONLY.apk', source, root, journal, certificate)
    instrumentation = verify_apk(Path(android) / 'FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk', source, root, journal, certificate, instrumentation=True)
    for key, actual in [('android', app), ('instrumentation', instrumentation)]:
        if actual != manifests['android'][key]:
            raise Blocked('APK re-verification differs from producer manifest')
    setup = Path(windows) / 'FlowDrop-Setup-1.13.0-Windows-x64-TEST-ONLY.exe'
    extracted, installer = inspect_installer(setup, root, journal)
    inventory = manifests['windows']['windows_payload']['inventory']
    expected = {item['path'] for item in inventory}
    if set(installer.pop('members')) != expected | PLUGINS or len(expected) != len(inventory):
        raise Blocked('Installer contains unexpected or missing payload files')
    clean = fresh_child(root, root / 'payload-verification')
    for item in inventory:
        name = archive_name(item['path'])
        if name is None:
            raise Blocked('Empty installer inventory name')
        original = extracted / str(name)
        if not original.is_file() or original.is_symlink() or digest(original) != item['sha256'] or original.stat().st_size != item['size']:
            raise Blocked('Extracted installer file differs from producer inventory')
        target = clean / str(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    payload = verify_windows_payload(clean, source)
    if payload != manifests['windows']['windows_payload']:
        raise Blocked('Independent PE/payload verification differs from producer')
    installer['payload_files_verified'] = len(expected)
    if installer != manifests['windows']['windows_installer']:
        raise Blocked('Installer re-verification differs from producer')
    result = {'status': 'PASS', 'exit_code': 0, 'source': source_info, 'android': app,
              'instrumentation': instrumentation, 'windows_installer': installer,
              'windows_payload': payload, 'runtime_equivalence': 'NOT VERIFIED',
              'production_signing_equivalence': 'NOT VERIFIED', 'reproducible_binary': 'NOT VERIFIED'}
    write_json(root / 'logs/independent-verification.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--cache-root', required=True)
    parser.add_argument('--android', required=True)
    parser.add_argument('--windows', required=True)
    args = parser.parse_args()
    root = owned_root(args.work_root)
    try:
        verify_downloads(root, Path(args.cache_root), args.android, args.windows)
    except Exception as error:
        write_json(root / 'logs/independent-verification.json', {'status': 'FAIL', 'exit_code': 1, 'reason': str(error)})
        return 1
    print('PASS: downloaded artifact checksums, APK signatures/metadata and PE/NSIS payload; OS runtime remains separate')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
