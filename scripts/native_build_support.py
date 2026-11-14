"""Secret handling for native build tools; never creates or replaces signing keys."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
import json
import time
import shutil

KEYSTORE_ENV = 'FLOWDROP_ANDROID_KEYSTORE'
STORE_PASSWORD_ENV = 'FLOWDROP_ANDROID_STORE_PASSWORD'
KEY_PASSWORD_ENV = 'FLOWDROP_ANDROID_KEY_PASSWORD'
SIGNING_ENV = (KEYSTORE_ENV, STORE_PASSWORD_ENV, KEY_PASSWORD_ENV)
KEY_ALIAS = 'flowdrop'  # Public alias from the 1.13.0 source; not an identity replacement.


def verification_root(env):
    value = env.get('FLOWDROP_NATIVE_WORK_ROOT')
    if not value:
        return None
    root = Path(value).absolute()
    marker = root / '.flowdrop-2c2-owned'
    if root.is_symlink() or marker.is_symlink() or not marker.is_file() or marker.read_text() != 'FlowDrop 2C2 TEST ONLY v1':
        raise BuildError('Invalid isolated verification work root')
    return root.resolve()


def build_path(path, parent, env=None):
    env = os.environ if env is None else env
    path, parent = Path(path).absolute(), Path(parent).absolute()
    if '..' in path.parts or path == parent or not path.is_relative_to(parent) or parent.is_symlink():
        raise BuildError('Unsafe build cleanup path')
    current = path
    while current != parent:
        if current.is_symlink():
            raise BuildError('Refusing build path through symlink')
        current = current.parent
    root = verification_root(env)
    if root is not None and not path.resolve().is_relative_to(root):
        raise BuildError('Build path is outside the isolated verification root')
    return path


def fresh_build_directory(path, parent):
    path = build_path(path, parent)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        raise BuildError('Build directory is an unexpected file')
    path.mkdir(parents=True)
    return path


def clear_build_output(path, parent):
    path = build_path(path, parent)
    if path.is_dir():
        raise BuildError('Build output is an unexpected directory')
    path.unlink(missing_ok=True)


class BuildError(RuntimeError):
    pass


@dataclass(repr=False, frozen=True)
class AndroidSigning:
    keystore: Path

    def arguments(self):
        return ['--ks', str(self.keystore), '--ks-key-alias', KEY_ALIAS,
                '--ks-pass', 'env:' + STORE_PASSWORD_ENV,
                '--key-pass', 'env:' + KEY_PASSWORD_ENV]


def load_signing(repository, env=None):
    env = os.environ if env is None else env
    for name in SIGNING_ENV:
        value = env.get(name, '')
        if not value or any(c in value for c in '\x00\r\n'):
            raise BuildError('Missing or invalid signing environment variable: ' + name)
    supplied = Path(env[KEYSTORE_ENV])
    if not supplied.is_absolute() or supplied.is_symlink():
        raise BuildError('Signing keystore must be an external regular file with an absolute path')
    try:
        key = supplied.resolve(strict=True)
    except OSError:
        raise BuildError('Signing keystore file is unavailable') from None
    root = Path(repository).resolve()
    if not key.is_file() or key == root or root in key.parents:
        raise BuildError('Signing keystore must be outside the source checkout')
    isolated = verification_root(env)
    if isolated is not None:
        if not key.is_relative_to(isolated / 'test-secrets'):
            raise BuildError('Verification can only use its own temporary test keystore')
        record = isolated / 'test-certificate.json'
        if not record.is_file() or record.is_symlink():
            raise BuildError('Missing temporary test certificate purpose record')
        info = json.loads(record.read_text())
        if info.get('purpose') != 'FlowDrop 2C2 TEST ONLY' or not re.fullmatch(r'[0-9a-f]{64}', info.get('sha256', '')):
            raise BuildError('Invalid temporary certificate record')
        if info['sha256'] == '65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f':
            raise BuildError('Production certificate is forbidden in build verification')
    return AndroidSigning(key)


def require_tool_root(env=None):
    env = os.environ if env is None else env
    supplied = env.get('FLOWDROP_BUILD_TOOLS', '')
    if not supplied or not Path(supplied).is_absolute() or not Path(supplied).is_dir():
        raise BuildError('Set FLOWDROP_BUILD_TOOLS to an existing absolute toolchain directory')
    return Path(supplied)


def redact(text, env=None):
    env = os.environ if env is None else env
    values = [value for name, value in env.items() if value and
              (name in SIGNING_ENV or re.search(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH', name, re.I))]
    for value in sorted(set(values), key=len, reverse=True):
        text = text.replace(value, '[REDACTED]')
    return re.sub(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----',
                  '[REDACTED_PRIVATE_KEY]', text, flags=re.S)


def run_command(args, signing=False, **kwargs):
    argv = [str(value) for value in args]
    if any(value.startswith('pass:') for value in argv):
        raise BuildError('Inline signing passwords are forbidden; use env: references')
    source_env = dict(kwargs.pop('env', os.environ))
    isolated = verification_root(source_env)
    if argv[0] == 'java' and isolated is not None:
        java = Path(source_env.get('FLOWDROP_BUILD_JAVA', ''))
        if not java.is_absolute() or not java.is_file() or not java.resolve().is_relative_to(isolated / 'jdk'):
            raise BuildError('Verification requires its pinned absolute Java executable')
        argv[0] = str(java)
    step_file = source_env.get('FLOWDROP_BUILD_STEP_REPORT')
    if step_file:
        if isolated is None:
            raise BuildError('Build step report requires an isolated work root')
        report_path = build_path(step_file, isolated / 'logs', source_env)
        report_path.parent.mkdir(parents=True, exist_ok=True)
    def record(code, timeout=False):
        if step_file:
            data = {'command': [redact(v, source_env) for v in argv], 'exit_code': code,
                    'timeout': timeout, 'wall_seconds': round(time.monotonic() - started, 3)}
            descriptor = os.open(report_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'a') as output:
                output.write(json.dumps(data) + '\n')
    child_env = dict(source_env)
    if not signing:
        for name in SIGNING_ENV:
            child_env.pop(name, None)
    name = Path(argv[0]).name
    print('Running:', name, flush=True)
    started = time.monotonic()
    try:
        result = subprocess.run(argv, env=child_env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors='replace',
                                check=False, timeout=900, **kwargs)
    except subprocess.TimeoutExpired:
        record(124, timeout=True)
        raise BuildError(name + ' timed out; raw command/output suppressed') from None
    except OSError:
        record(127)
        raise BuildError(name + ' could not start; raw command suppressed') from None
    record(result.returncode)
    if result.stdout:
        print(redact(result.stdout, source_env), end='', flush=True)
    if result.returncode:
        raise BuildError(name + ' failed with exit code ' + str(result.returncode))
    return result


def report_failure(error):
    print('Build failed: ' + redact(str(error)), file=sys.stderr, flush=True)
    return 1
