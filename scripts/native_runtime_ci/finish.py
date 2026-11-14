"""Screen runtime evidence before upload; no app state, AVDS, keys or caches exported."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import time

from .common import Blocked, STATES, child, clean_child, json_file, own_root, sanitize, sha256


def export(root):
    root = own_root(root)
    destination = root / 'evidence-export'
    clean_child(root, destination)
    planned = []
    for file in (root / 'logs').glob('*'):
        if file.is_symlink() or not file.is_file() or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:json|jsonl|log|png|bmp)', file.name):
            raise Blocked('Unexpected runtime evidence entry')
        if file.stat().st_size > 24 * 2**20:
            raise Blocked('Evidence exceeds explicit size limit')
        if file.suffix in ['.png', '.bmp']:
            if file.name not in ['initial-activity.png', 'initial-native-window.bmp']:
                raise Blocked('Screenshot not in reviewed no-token allowlist')
            data = file.read_bytes()
            if file.suffix == '.png' and not data.startswith(b'\x89PNG\r\n\x1a\n') or file.suffix == '.bmp' and not data.startswith(b'BM'):
                raise Blocked('Screenshot header invalid')
        else:
            data = sanitize(file.read_text(encoding='utf-8')).encode('utf-8')
            if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{40,}|gh[pousr]_[A-Za-z0-9]{30,}', data):
                raise Blocked('Unscreened private material in evidence')
        planned.append((file.name, data))
    if not planned:
        planned.append(('not-verified.json', b'{"status":"NOT VERIFIED","reason":"Runtime command produced no completed evidence"}\n'))
    destination.mkdir()
    for name, data in planned:
        (destination / name).write_bytes(data)
    inventory = [{'path': file.name, 'size': file.stat().st_size, 'sha256': sha256(file)} for file in sorted(destination.iterdir())]
    json_file(destination / 'evidence-manifest.json', {'purpose': 'FlowDrop 2D1 screened native runtime evidence', 'files': inventory})
    (destination / 'SHA256SUMS.txt').write_text(''.join(sha256(file) + '  ' + file.name + '\n' for file in sorted(destination.iterdir())), encoding='utf-8')


def cleanup(root):
    root = own_root(root)
    receipt = root / 'owned-emulator.json'
    if receipt.is_file():
        data = json.loads(receipt.read_text(encoding='utf-8'))
        pid = int(data['pid'])
        executable = Path('/proc') / str(pid) / 'exe'
        if executable.exists() and executable.resolve().is_relative_to(root / 'toolchain/tools/sdk/emulator'):
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            if executable.exists() and executable.resolve().is_relative_to(root / 'toolchain/tools/sdk/emulator'):
                os.kill(pid, signal.SIGKILL)
    for name in ['toolchain', 'android-user', 'avds', 'emulator-output.raw']:
        clean_child(root, root / name)


def status(root):
    root = own_root(root)
    result = root / 'logs/results.json'
    value = json.loads(result.read_text(encoding='utf-8')).get('status') if result.is_file() else 'NOT VERIFIED'
    if value not in STATES:
        raise Blocked('Unknown runtime status')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('status=' + value + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'cleanup', 'status']); parser.add_argument('--work-root', required=True)
    args = parser.parse_args()
    {'export': export, 'cleanup': cleanup, 'status': status}[args.action](args.work_root)


if __name__ == '__main__':
    main()
