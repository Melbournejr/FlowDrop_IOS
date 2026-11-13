"""Secret handling for native build tools; never creates or replaces signing keys."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys

KEYSTORE_ENV = 'FLOWDROP_ANDROID_KEYSTORE'
STORE_PASSWORD_ENV = 'FLOWDROP_ANDROID_STORE_PASSWORD'
KEY_PASSWORD_ENV = 'FLOWDROP_ANDROID_KEY_PASSWORD'
SIGNING_ENV = (KEYSTORE_ENV, STORE_PASSWORD_ENV, KEY_PASSWORD_ENV)
KEY_ALIAS = 'flowdrop'  # Public alias from the 1.13.0 source; not an identity replacement.


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
    child_env = dict(source_env)
    if not signing:
        for name in SIGNING_ENV:
            child_env.pop(name, None)
    name = Path(argv[0]).name
    print('Running:', name, flush=True)
    try:
        result = subprocess.run(argv, env=child_env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors='replace',
                                check=False, timeout=900, **kwargs)
    except subprocess.TimeoutExpired:
        raise BuildError(name + ' timed out; raw command/output suppressed') from None
    except OSError:
        raise BuildError(name + ' could not start; raw command suppressed') from None
    if result.stdout:
        print(redact(result.stdout, source_env), end='', flush=True)
    if result.returncode:
        raise BuildError(name + ' failed with exit code ' + str(result.returncode))
    return result


def report_failure(error):
    print('Build failed: ' + redact(str(error)), file=sys.stderr, flush=True)
    return 1
