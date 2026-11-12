"""CI orchestration only: retain real test exit codes and sanitized evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
JAR_URL = 'https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar'
JAR_SHA256 = '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed'
MARKER = '.flowdrop-native-ci-owned'
GROUPS = {
    'fast': [
        ('ci-runner-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/ci', '-p', 'test_*.py', '-v'], 90),
        ('asset-integrity', ['sha256sum', '--check', 'docs/assets/FONT-RESTORATION-SHA256SUMS.txt'], 30),
        ('unit', ['npm', 'test'], 90),
        ('harness-unit', ['node', '--test', 'tests/harness.test.mjs'], 90),
    ],
    # One process, sequential commands: discovery never shares a namespace with a parallel test.
    'integration': [
        ('http', ['node', 'tests/http-integration.mjs'], 120),
        ('android-host', ['node', 'tests/android-host-integration.mjs'], 120),
        ('discovery', ['node', 'tests/discovery-integration.mjs'], 120),
        ('peer', ['node', 'tests/peer-integration.mjs'], 240),
        ('lan-discovery', ['node', 'tests/lan-discovery-integration.mjs'], 240),
        ('android-discovery', ['node', 'tests/android-discovery-state.mjs'], 120),
        ('security', ['node', 'tests/security-integration.mjs'], 120),
    ],
    'stream': [('large-transfer', ['node', 'tests/large-transfer-integration.mjs'], 300)],
    'zip64': [
        ('features', ['node', '--test', 'tests/features-1.10.test.mjs'], 600),
        ('folders', ['node', '--test', 'tests/folder-receive.test.mjs'], 900),
        ('native-client', ['node', 'tests/android-native-client.mjs'], 1500),
    ],
}


def redact(text, env=None):
    env = os.environ if env is None else env
    for name, value in env.items():
        if len(value) >= 8 and re.search(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH', name, re.I):
            text = text.replace(value, '[REDACTED_ENV]')
    text = re.sub(r'(["\x27](?:token|localToken|desktopToken|statusToken|uploadCapability)["\x27]\s*:\s*["\x27])[^"\x27\r\n]+', r'\1[REDACTED]', text, flags=re.I)
    text = re.sub(r'(X-(?:Desktop|Local|Upload)-Token\s*[:=]\s*)[^\s,}\r\n]+', r'\1[REDACTED]', text, flags=re.I)
    text = re.sub(r'\b(?:[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}){1,2}\b', '[REDACTED_UUID]', text, flags=re.I)
    return re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b', '[REDACTED_GITHUB_TOKEN]', text)


def owned_root(value):
    root = Path(value).absolute()
    if root.is_symlink() or root.resolve() in (Path('/'), Path.home(), REPO) or root.resolve() in REPO.parents:
        raise ValueError('Refusing unsafe CI work directory')
    root.mkdir(parents=True, exist_ok=True)
    if not (root / MARKER).is_file():
        if any(root.iterdir()):
            raise ValueError('Refusing an existing unowned work directory')
        (root / MARKER).write_text('FlowDrop native CI scratch owner v1\n')
    for name in ['logs', 'scratch', 'tools']:
        if (root / name).is_symlink():
            raise ValueError('Refusing symlink in CI work directory')
        (root / name).mkdir(exist_ok=True)
    return root


def cleanup(root):
    root = Path(root)
    if root.is_symlink() or not (root / MARKER).is_file():
        raise ValueError('Refusing cleanup without ownership marker')
    for name in ['scratch', 'tools']:
        target = root / name
        if target.is_symlink():
            raise ValueError('Refusing cleanup through symlink')
        shutil.rmtree(target, ignore_errors=False) if target.exists() else None


def memory_limit():
    memory = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    path = Path('/sys/fs/cgroup/memory.max')
    if path.is_file() and path.read_text().strip() != 'max':
        memory = min(memory, int(path.read_text().strip()))
    return memory


def resources(group, root):
    free, memory = shutil.disk_usage(root).free, memory_limit()
    minimum = (18 if group == 'zip64' else 2 if group == 'stream' else 0.5) * 2**30
    ok = platform.system() == 'Linux' and free >= minimum and memory >= 2 * 2**30
    if group == 'stream':
        ok = ok and Path('/proc/self/status').is_file()
    return {'supported': bool(ok), 'free_disk_bytes': free, 'memory_limit_bytes': memory,
            'minimum_disk_bytes': int(minimum), 'minimum_memory_bytes': 2 * 2**30}


def execute(name, command, deadline, root, env):
    started = time.monotonic()
    record = {'name': name, 'command': command, 'status': 'NOT VERIFIED', 'executed': False,
              'exit_code': None, 'raw_returncode': None, 'timeout': False, 'timeout_seconds': deadline}
    child = None
    output = ''
    try:
        child = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, start_new_session=True)
        record['executed'] = True
        try:
            output, _ = child.communicate(timeout=deadline)
        except subprocess.TimeoutExpired:
            record['timeout'] = True
            os.killpg(child.pid, signal.SIGTERM)
            try:
                output, _ = child.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                output, _ = child.communicate()
        code = child.returncode
        record['raw_returncode'] = code
        record['exit_code'] = 124 if record['timeout'] else code if code >= 0 else 128 - code
        record['status'] = 'PASS' if record['exit_code'] == 0 else 'FAIL'
    except OSError as error:
        record['exit_code'] = 127
        output = 'Command could not start: ' + type(error).__name__
    finally:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        record['wall_seconds'] = round(time.monotonic() - started, 3)
        (root / 'logs' / (name + '.log')).write_text(redact(output, env))
    return record


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def verify_jar(path):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != JAR_SHA256:
        raise ValueError('org.json 20240303 SHA-256 mismatch; refusing compilation')


def setup(root):
    env = dict(os.environ)
    steps = []
    for name, command, pattern in [
        ('node-version', ['node', '--version'], r'^v24\.'),
        ('java-version', ['java', '-version'], r'version "21[.\"]'),
        ('python-version', [sys.executable, '--version'], r'^Python 3\.'),
    ]:
        result = execute(name, command, 30, root, env)
        steps.append(result)
        text = (root / 'logs' / (name + '.log')).read_text()
        if result['exit_code'] != 0 or not re.search(pattern, text):
            write_json(root / 'logs' / 'setup.json', {'status': 'FAIL', 'steps': steps})
            return result['exit_code'] or 1
    jar = root / 'tools' / 'json-20240303.jar'
    commands = [
        ('jar-download', ['curl', '--fail', '--location', '--retry', '3', '--connect-timeout', '15',
                          '--max-time', '120', '--proto', '=https', JAR_URL, '-o', str(jar)], 150),
        ('npm-ci', ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--cache', str(root / 'tools' / 'npm-cache')], 300),
    ]
    for name, command, deadline in commands:
        result = execute(name, command, deadline, root, env)
        steps.append(result)
        if result['exit_code'] != 0:
            write_json(root / 'logs' / 'setup.json', {'status': 'FAIL', 'steps': steps})
            return result['exit_code']
        if name == 'jar-download':
            verify_jar(jar)
    write_json(root / 'logs' / 'setup.json', {'status': 'PASS', 'jar_url': JAR_URL,
                                          'jar_sha256': JAR_SHA256, 'steps': steps})
    return 0


def run_group(group, root):
    verify_jar(root / 'tools' / 'json-20240303.jar')
    results = [{'name': name, 'command': argv, 'status': 'NOT VERIFIED', 'executed': False,
                'exit_code': None, 'reason': 'Not started'} for name, argv, _ in GROUPS[group]]
    status = {'group': group, 'status': 'NOT VERIFIED', 'exit_code': 78, 'results': results}
    write_json(root / 'logs' / 'results.json', status)
    for index, (name, argv, deadline) in enumerate(GROUPS[group]):
        available = resources(group, root)
        if not available['supported']:
            results[index].update(reason='Runner resources/OS not sufficient', resources=available)
            status['exit_code'] = 78
            write_json(root / 'logs' / 'results.json', status)
            print('NOT VERIFIED: ' + name + ' (resource/OS preflight)', flush=True)
            return status
        scratch = root / 'scratch' / name
        scratch.mkdir()
        env = dict(os.environ, TMPDIR=str(scratch), FLOWDROP_TEST_TMPDIR=str(scratch),
                   FLOWDROP_TEST_JSON_JAR=str(root / 'tools' / 'json-20240303.jar'),
                   FLOWDROP_TEST_REPORT_DIR=str(scratch / 'reports'), FLOWDROP_DISABLE_UPDATES='1',
                   FLOWDROP_DEFAULT_RECEIVE_DIR=str(scratch / 'received'), NPM_CONFIG_UPDATE_NOTIFIER='false')
        print('RUN: ' + name, flush=True)
        result = execute(name, argv, deadline, root, env)
        result['resources'] = available
        results[index] = result
        shutil.rmtree(scratch)
        write_json(root / 'logs' / 'results.json', status)
        print(result['status'] + ': ' + name + ' exit=' + str(result['exit_code']) + ' duration=' + str(result['wall_seconds']) + 's', flush=True)
    failure = next((r['exit_code'] for r in results if r['exit_code'] != 0), 0)
    status.update(status='FAIL' if failure else 'PASS', exit_code=failure)
    write_json(root / 'logs' / 'results.json', status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('group', choices=['setup', 'cleanup', *GROUPS])
    parser.add_argument('--work-root', required=True)
    args = parser.parse_args()
    if args.group == 'cleanup':
        cleanup(Path(args.work_root))
        return 0
    root = owned_root(args.work_root)
    try:
        if args.group == 'setup':
            return setup(root)
        result = run_group(args.group, root)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write('### Native ' + args.group + '\n\n| Suite | Status | Exit |\n|---|---|---|\n')
                for entry in result['results']:
                    summary.write('| ' + entry['name'] + ' | ' + entry['status'] + ' | ' + str(entry['exit_code']) + ' |\n')
        return result['exit_code']
    except (OSError, ValueError) as error:
        (root / 'logs' / 'orchestrator-error.log').write_text(redact(type(error).__name__ + ': ' + str(error)))
        print('FAIL: CI setup/orchestrator; see sanitized logs', flush=True)
        return 1
    except KeyboardInterrupt:
        print('NOT VERIFIED: interrupted', flush=True)
        return 130


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    raise SystemExit(main())
