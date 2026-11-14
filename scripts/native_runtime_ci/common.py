"""Portable test evidence and safety checks. A successful collector is never a test PASS."""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import subprocess
import time

REPO = Path(__file__).resolve().parents[2]
BASE = '9171e7f1ffbc0143d6e11374e3f6c847853341fe'
PURPOSE = 'FlowDrop 2D1 isolated synthetic runtime data v1'
STATES = {'PASS', 'FAIL', 'BLOCKED', 'NOT VERIFIED', 'SKIPPED'}


class Blocked(RuntimeError):
    pass


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def json_file(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def own_root(path):
    path = Path(path).absolute()
    if '..' in path.parts or path.is_symlink():
        raise Blocked('Unsafe runtime work root')
    root = path.resolve()
    if root in [Path(root.anchor), Path.home().resolve(), REPO] or root in REPO.parents or root.is_relative_to(REPO):
        raise Blocked('Runtime work root must be outside checkout and user data')
    root.mkdir(parents=True, exist_ok=True)
    marker = root / '.flowdrop-2d1-owned'
    if marker.is_symlink():
        raise Blocked('Symlink ownership marker')
    if not marker.exists():
        if any(root.iterdir()):
            raise Blocked('Refusing an existing unowned runtime directory')
        marker.write_text(PURPOSE, encoding='utf-8')
    if marker.read_text(encoding='utf-8') != PURPOSE:
        raise Blocked('Runtime root purpose mismatch')
    return root


def child(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    marker = root / '.flowdrop-2d1-owned'
    if not marker.is_file() or marker.is_symlink() or marker.read_text(encoding='utf-8') != PURPOSE:
        raise Blocked('Cleanup requires owned runtime root')
    if path == root or '..' in path.parts or not path.is_relative_to(root):
        raise Blocked('Runtime path escapes owned root')
    current = path
    while current != root:
        if current.is_symlink():
            raise Blocked('Runtime path uses a symlink')
        current = current.parent
    if not path.resolve().is_relative_to(root):
        raise Blocked('Resolved runtime path escapes root')
    return path


def clean_child(root, path):
    path = child(root, path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def clean_env():
    env = dict(os.environ)
    for name in list(env):
        if re.search(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH', name, re.I) or name.startswith('FLOWDROP_ANDROID_'):
            env.pop(name, None)
    for name in ['PYTHONPATH', 'PYTHONHOME', 'NODE_OPTIONS', 'LD_PRELOAD', 'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS',
                 'GITHUB_ENV', 'GITHUB_PATH', 'GITHUB_OUTPUT', 'GITHUB_STEP_SUMMARY', 'BASH_ENV', 'ENV']:
        env.pop(name, None)
    return env


def sanitize(value, secrets=()):
    text = str(value)
    values = list(secrets) + [v for k, v in os.environ.items() if v and re.search('TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH', k, re.I)]
    for v in sorted(set(values), key=len, reverse=True):
        if v:
            text = text.replace(v, '[REDACTED]')
    text = re.sub(r'(?is)-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]', text)
    text = re.sub(r'(?i)(?<![A-Za-z0-9_])(["\']?(?:token|statusToken|offerKey|localUploadCapability|authorization|password|code)["\']?\s*[:=]\s*)(?:["\'][^"\'\r\n]*["\']|[^\s,;}]+)', r'\1"[REDACTED]"', text)
    text = re.sub(r'(?i)Bearer\s+[A-Za-z0-9._~-]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'github_pat_[A-Za-z0-9_]{40,}|gh[pousr]_[A-Za-z0-9]{30,}', '[REDACTED_CREDENTIAL]', text)
    return text


def protected_source():
    manifest = json.loads((REPO / 'docs/testing/RUNTIME-SOURCE-BASELINE-2D1.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        if sha256(REPO / row['path']) != row['sha256']:
            raise Blocked('Protected baseline changed: ' + row['path'])
    return {'base': manifest['base'], 'protected_files': len(manifest['files']),
            'checkout': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
            'reviewed_head': os.environ.get('FLOWDROP_REVIEWED_HEAD', subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip())}


class Recorder:
    def __init__(self, root, target, source, artifact=None):
        self.root = own_root(root)
        (self.root / 'logs').mkdir(exist_ok=True)
        self.target, self.source, self.artifact = target, source, artifact or {}
        self.cases, self.commands, self.secrets = [], [], []
        self.os_version = platform.platform()

    def save(self):
        json_file(self.root / 'logs/test-matrix.json', {'platform': self.target, 'source': self.source, 'artifact': self.artifact, 'tests': self.cases})
        json_file(self.root / 'logs/commands.json', self.commands)

    def run(self, name, argv, timeout=120, env=None, cwd=None, check=True, input=None):
        started = time.monotonic()
        command = [str(v) for v in argv]
        raw, code = '', None
        try:
            completed = subprocess.run(command, cwd=cwd or REPO, env=env or clean_env(), input=input,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace',
                                       timeout=timeout, check=False, encoding='utf-8')
            raw, code = completed.stdout, completed.returncode
        except subprocess.TimeoutExpired as error:
            raw = error.stdout or ''
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='replace')
            code = 124
        except OSError as error:
            raw, code = type(error).__name__ + ': executable could not start', 127
        log = self.root / 'logs' / (name + '.log')
        log.write_text(sanitize(raw, self.secrets), encoding='utf-8')
        self.commands.append({'name': name, 'command': [sanitize(v, self.secrets) for v in command], 'exit_code': code,
                              'wall_seconds': round(time.monotonic() - started, 3), 'timeout_seconds': timeout,
                              'log': log.relative_to(self.root).as_posix(), 'log_sha256': sha256(log)})
        self.save()
        if check and code != 0:
            raise AssertionError(name + ' exit=' + str(code) + '; see sanitized log')
        return raw, code

    @contextlib.contextmanager
    def case(self, test_id, expected, required=True, preconditions='Owned isolated environment and verified artifact'):
        row = {'test_id': test_id, 'platform': self.target, 'os_api': self.os_version, 'source_commit': self.source['reviewed_head'],
               'checkout_commit': self.source['checkout'], 'artifact_sha256': self.artifact,
               'preconditions': preconditions, 'command_or_method': test_id, 'expected': expected,
               'actual': None, 'exit_code': None, 'time_started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'wall_seconds': None, 'evidence_path': 'logs/test-matrix.json', 'required': required, 'status': 'NOT VERIFIED'}
        started = time.monotonic()
        try:
            yield row
            row['status'] = 'SKIPPED' if row.get('skip_reason') else 'PASS'
            if row['actual'] is None:
                row['actual'] = 'Assertions completed successfully'
        except Blocked as error:
            row.update(status='BLOCKED', actual=sanitize(error, self.secrets))
        except Exception as error:
            row.update(status='FAIL', actual=sanitize(type(error).__name__ + ': ' + str(error), self.secrets))
        finally:
            row['wall_seconds'] = round(time.monotonic() - started, 3)
            row['os_api'] = self.os_version
            self.cases.append(row)
            self.save()

    def finish(self, expected_ids):
        seen = {row['test_id'] for row in self.cases}
        for test_id in expected_ids:
            if test_id not in seen:
                self.cases.append({'test_id': test_id, 'platform': self.target, 'os_api': self.os_version,
                    'source_commit': self.source['reviewed_head'], 'checkout_commit': self.source['checkout'],
                    'artifact_sha256': self.artifact, 'preconditions': 'A preceding prerequisite must complete',
                    'command_or_method': test_id, 'expected': 'Required runtime assertion',
                    'actual': 'Prerequisite failure prevented execution', 'exit_code': None, 'wall_seconds': 0,
                    'evidence_path': 'logs/test-matrix.json', 'required': True, 'status': 'NOT VERIFIED'})
        self.save()
        good = all(row['status'] == 'PASS' for row in self.cases if row['required'])
        json_file(self.root / 'logs/results.json', {'status': 'PASS' if good else 'FAIL', 'exit_code': 0 if good else 1,
                 'platform': self.target, 'tests': self.cases, 'production_signing': 'NOT VERIFIED',
                 'physical_devices': 'NOT VERIFIED', 'cross_platform_lan': 'NOT VERIFIED'})
        return 0 if good else 1


def verify_export(directory, role, source):
    from scripts.native_build_ci.artifacts import check_export
    manifest = check_export(directory, role)
    if manifest['source']['checkout_commit'] != source['checkout'] or manifest['source']['uncommitted_paths']:
        raise Blocked('Artifact source checkout differs from runtime checkout or was dirty')
    return manifest
