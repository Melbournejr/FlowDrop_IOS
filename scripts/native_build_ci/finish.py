"""Export only sanitized evidence, then clean children of an owned test root."""
import argparse
from pathlib import Path
import re
import shutil
import json
import os

from scripts.native_build_support import redact
from .paths import Blocked, digest, fresh_child, remove_child, require_owned
from .verify import reject_secret_bytes


def prepare_logs(root):
    root = require_owned(root)
    output = fresh_child(root, root / 'safe-logs')
    for file in (root / 'logs').glob('*'):
        if file.is_symlink() or not file.is_file() or not re.fullmatch(r'[A-Za-z0-9_-]+\.(log|json|jsonl)', file.name):
            raise Blocked('Unexpected evidence entry')
        if file.stat().st_size > 16 * 2**20:
            raise Blocked('Evidence exceeds the sanitized log limit')
        data = redact(file.read_text())
        reject_secret_bytes(data.encode())
        (output / file.name).write_text(data)
    if not list(output.iterdir()):
        (output / 'not-verified.log').write_text('NOT VERIFIED: no completed verification log was produced.\n')
    (output / 'SHA256SUMS.txt').write_text(''.join(digest(file) + '  ' + file.name + '\n' for file in sorted(output.iterdir())))


def cleanup(root):
    root = require_owned(root)
    for name in ['test-secrets', 'signature-check', 'test-certificate.der', 'source', 'tools',
                 'jdk', 'node-linux', 'download-cache', 'npm-cache', 'installer-inspection', 'payload-verification']:
        remove_child(root, root / name)


def status(root):
    root = require_owned(root)
    candidates = ['build-results.json', 'independent-verification.json', 'toolchain.json']
    value = 'NOT VERIFIED'
    for name in candidates:
        path = root / 'logs' / name
        if path.is_file() and not path.is_symlink():
            value = json.loads(path.read_text()).get('status', 'NOT VERIFIED')
            break
    if value not in ['PASS', 'FAIL', 'BLOCKED', 'NOT VERIFIED', 'SKIPPED']:
        raise Blocked('Invalid verification status')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('status=' + value + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['logs', 'cleanup', 'status'])
    parser.add_argument('--work-root', required=True)
    args = parser.parse_args()
    {'logs': prepare_logs, 'cleanup': cleanup, 'status': status}[args.action](Path(args.work_root))


if __name__ == '__main__':
    main()
