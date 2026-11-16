"""Layer-A protocol / portable owner-tool verification; never claims native or physical E2E."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import zipfile

from scripts.native_runtime_ci.common import REPO, Recorder, clean_env, json_file, sha256, sanitize, own_root, clean_child

BASE = 'f9b5a43c5eae93b169717a72d19f5a426d913094'


def protocol_command(rec, argv, env, timeout=2700):
    """Bound one owned POSIX process group, including the Node/JVM hosts it spawns."""
    if os.name != 'posix':
        raise RuntimeError('Protocol process-group control requires the isolated Linux job')
    command = [str(x) for x in argv]; started = time.monotonic(); child = None
    output = ''; code = 127; raw_code = None; timed_out = False
    try:
        child = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', start_new_session=True)
        try:
            output, _ = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGTERM)
            try:
                output, _ = child.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); output, _ = child.communicate()
        raw_code = child.returncode
        code = 124 if timed_out else raw_code if raw_code >= 0 else 128 - raw_code
    finally:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        log = rec.root / 'logs/protocol-command.log'
        log.write_text(sanitize(output, rec.secrets), encoding='utf-8')
        rec.commands.append({'name': 'protocol-command', 'command': [sanitize(x, rec.secrets) for x in command],
                             'exit_code': code, 'raw_returncode': raw_code, 'timeout': timed_out,
                             'timeout_seconds': timeout, 'wall_seconds': time.monotonic() - started,
                             'log': 'logs/protocol-command.log', 'log_sha256': sha256(log)})
        rec.save()
    if code != 0:
        raise AssertionError('Protocol child exit=' + str(code) + '; screened log retained')
    return code


def source_guard():
    doc = json.loads((REPO / 'docs/testing/CROSS-PLATFORM-SOURCE-BASELINE-2D2.json').read_text())
    if doc['base'] != BASE or len(doc['files']) != 790:
        raise RuntimeError('Unexpected Phase 2D.2 baseline')
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASE], cwd=REPO)
    blobs = {}
    for raw in tree.split(b'\0'):
        if raw:
            info, name = raw.split(b'\t', 1)
            mode, kind, blob = info.decode().split()
            if kind != 'blob' or mode not in ['100644', '100755']:
                raise RuntimeError('Unexpected baseline entry')
            blobs[name.decode()] = blob
    if len(blobs) != 790 or set(blobs) != {r['path'] for r in doc['files']}:
        raise RuntimeError('Baseline manifest disagrees with immutable Git commit inventory')
    for row in doc['files']:
        path = REPO / row['path']
        if path.is_symlink() or not path.is_file() or sha256(path) != row['sha256']:
            raise RuntimeError('Frozen baseline modified: ' + row['path'])
        data = path.read_bytes()
        git_hash = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if git_hash != blobs[row['path']]:
            raise RuntimeError('Source bytes differ from immutable base Git object')
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'HEAD'], cwd=REPO, check=True)
    checkout = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=REPO, text=True).strip()
    return {'base': BASE, 'protected_files': 790, 'checkout': checkout,
            'reviewed_head': os.environ.get('FLOWDROP_REVIEWED_HEAD', checkout), 'tracked_worktree_dirty': bool(dirty)}


def export_evidence(root):
    root = own_root(root)
    logs = root / 'logs'
    exported = root / 'export'
    if exported.exists():
        raise RuntimeError('Refusing stale evidence export')
    exported.mkdir()
    rows = []
    for file in sorted(logs.iterdir()):
        if file.is_symlink() or not file.is_file() or file.suffix not in ['.json', '.log']:
            raise RuntimeError('Unexpected log export entry')
        text = sanitize(file.read_text(encoding='utf-8'))
        target = exported / file.name
        target.write_text(text, encoding='utf-8')
        rows.append({'path': target.name, 'size': target.stat().st_size, 'sha256': sha256(target)})
    json_file(exported / 'evidence-manifest.json', {'purpose': 'FlowDrop 2D2 sanitized test evidence', 'files': rows})
    all_files = sorted(exported.iterdir())
    (exported / 'SHA256SUMS.txt').write_text(''.join(sha256(p) + '  ' + p.name + '\n' for p in all_files), encoding='utf-8')


def toolkit_bundle(destination):
    destination = Path(destination)
    if destination.exists():
        raise RuntimeError('Refusing stale toolkit bundle')
    destination.mkdir()
    files = [REPO / 'tools/physical-lan/flowdrop_lan.py', REPO / 'tools/physical-lan/Run-FlowDrop-LAN.ps1',
             REPO / 'tools/physical-lan/Collect-FlowDrop-Network.ps1',
             REPO / 'docs/testing/PHYSICAL-LAN-TEST-GUIDE.md', REPO / 'tools/physical-lan/CHECKLIST.md']
    archive = destination / 'FlowDrop-Physical-LAN-Toolkit-2D2.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as output:
        for file in files:
            if file.is_symlink() or not file.is_file():
                raise RuntimeError('Missing or unsafe toolkit source')
            output.write(file, file.name)
    source = source_guard()
    json_file(destination / 'toolkit-manifest.json', {'source': source, 'purpose': 'Verification tools only, no application installer',
              'files': [{'name': f.name, 'size': f.stat().st_size, 'sha256': sha256(f)} for f in files],
              'archive': {'name': archive.name, 'size': archive.stat().st_size, 'sha256': sha256(archive)}})
    (destination / 'SHA256SUMS.txt').write_text(''.join(sha256(p) + '  ' + p.name + '\n' for p in sorted(destination.iterdir())), encoding='utf-8')


def run(root, role, full, jar):
    source = source_guard(); rec = Recorder(root, '2d2-' + role, source)
    env = clean_env()
    scratch = rec.root / 'synthetic'; scratch.mkdir()
    try:
        if role == 'protocol':
            if jar is None:
                raise RuntimeError('Explicit verified org.json test JAR required')
            if sha256(jar) != '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed':
                raise RuntimeError('Test org.json 20240303 SHA-256 mismatch')
            if full and shutil.disk_usage(scratch).free < 18 * 2**30:
                raise RuntimeError('BLOCKED: full protocol matrix requires 18 GiB free; no data-size fallback')
            env.update(FLOWDROP_REVIEWED_HEAD=source['reviewed_head'], FLOWDROP_CHECKOUT_COMMIT=source['checkout'],
                       FLOWDROP_TEST_JSON_JAR=str(Path(jar).resolve()), FLOWDROP_TEST_TMPDIR=str(scratch),
                       FLOWDROP_TEST_REPORT_DIR=str(rec.root / 'logs'), FLOWDROP_DISABLE_UPDATES='1')
            with rec.case('A-PROTOCOL-MATRIX', 'All four production-engine directions, exact SHA/size, capability and 25/50/75% interrupted upload assertions') as row:
                command = ['node', REPO / 'tests/cross-platform-protocol.mjs'] + (['--full'] if full else [])
                code = protocol_command(rec, command, env, timeout=2700)
                result = json.loads((rec.root / 'logs/protocol-matrix.json').read_text())
                expected = 36 if full else 24
                if result['status'] != 'PASS' or result['exit_code'] != 0 or len(result['cases']) != expected or any(x['status'] != 'PASS' for x in result['cases']):
                    raise AssertionError('Incomplete/failed protocol matrix')
                row.update(exit_code=code, actual={'status': 'PASS', 'engine_cases': expected, 'full_size_matrix': full,
                            'native_e2e': 'BLOCKED', 'physical_wifi': 'NOT VERIFIED'})
        else:
            with rec.case('TOOLKIT-UNIT', 'All original CI unit tests and new safety/honesty tests execute on this OS') as row:
                # New portable tests on Windows; all CI tests run on Linux (old tests have Linux-only assumptions).
                pattern = 'test_physical_lan.py' if os.name == 'nt' else 'test_*.py'
                _, code = rec.run('toolkit-unit', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/ci', '-p', pattern, '-v'], env=env, timeout=90)
                row.update(exit_code=code, actual={'os': platform.platform(), 'test_pattern': pattern,
                           'scope': 'Tool safety/unit only; not physical LAN'})
            tool = REPO / 'tools/physical-lan/flowdrop_lan.py'
            generated = scratch / 'owner-tool'
            with rec.case('TOOLKIT-CLI', 'Portable CLI runs prepare/hash/start/stop/compare/report and verifies exact synthetic file bytes') as row:
                commands = [
                    ['prepare'], ['environment'], ['hash-source'],
                    ['start', '--direction', 'Windows-to-Windows', '--mode', 'test-artifact', '--network', 'isolated-virtual'], ['stop'],
                ]
                if os.name == 'nt':
                    wrapper = REPO / 'tools/physical-lan/Run-FlowDrop-LAN.ps1'
                    rec.run('powershell-wrapper-prepare', ['pwsh', '-NoProfile', '-File', wrapper, '-Action', 'Prepare', '-Root', generated], env=env)
                    commands = commands[1:]
                    rec.run('powershell-readonly-network', ['pwsh', '-NoProfile', '-File', REPO / 'tools/physical-lan/Collect-FlowDrop-Network.ps1', '-Root', generated], env=env)
                for index, command in enumerate(commands):
                    rec.run('toolkit-cli-' + str(index), [sys.executable, '-X', 'utf8', tool, '--root', generated, *command], env=env)
                manifest = json.loads((generated / 'source-manifest.json').read_text())
                # Independent copy is a toolkit self-test, never labelled app transfer.
                received = scratch / 'self-test-copy'; shutil.copytree(generated / manifest['payload_folder'], received)
                rec.run('toolkit-compare', [sys.executable, '-X', 'utf8', tool, '--root', generated, 'compare', '--received-dir', received], env=env)
                rec.run('toolkit-report', [sys.executable, '-X', 'utf8', tool, '--root', generated, 'report'], env=env)
                report = json.loads((generated / 'report.json').read_text())
                if report['file_integrity'] != 'PASS' or report['status'] != 'NOT VERIFIED' or report['native_e2e'] != 'NOT VERIFIED':
                    raise AssertionError('Toolkit falsely promoted a local copy into native/physical E2E PASS')
                row.update(exit_code=0, actual={'files': manifest['file_count'], 'cli_integrity': 'PASS',
                             'overall_physical_status': report['status'], 'transport': 'Test-only filesystem copy'})
            with rec.case('TOOLKIT-BUNDLE', 'Only source scripts/docs enter the downloadable toolkit, with SHA-256/provenance') as row:
                toolkit_bundle(rec.root / 'toolkit')
                row.update(exit_code=0, actual={'manifest': 'toolkit/toolkit-manifest.json'})
    finally:
        clean_child(rec.root, scratch)
        rec.finish(['A-PROTOCOL-MATRIX'] if role == 'protocol' else ['TOOLKIT-UNIT', 'TOOLKIT-CLI', 'TOOLKIT-BUNDLE'])
        result = json.loads((rec.root / 'logs/results.json').read_text())
        result.update(layer='A: protocol/toolkit validation', native_cross_platform_e2e='BLOCKED', physical_lan='NOT VERIFIED')
        json_file(rec.root / 'logs/results.json', result)
        export_evidence(rec.root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['protocol', 'toolkit', 'cleanup'])
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--jar', type=Path)
    args = parser.parse_args()
    if args.role == 'cleanup':
        root = own_root(args.work_root)
        for name in ['synthetic']:
            if (root / name).exists():
                clean_child(root, root / name)
        return 0
    try:
        result = run(args.work_root, args.role, args.full, args.jar)
        return result['exit_code']
    except Exception as error:
        print(sanitize('FAIL/BLOCKED: ' + type(error).__name__ + ': ' + str(error)))
        return 1


if __name__ == '__main__':
    if os.name == 'posix':
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    raise SystemExit(main())
