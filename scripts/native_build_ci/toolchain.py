"""Provision exact authenticated tools into a disposable working copy."""
import argparse
import base64
import io
import json
import lzma
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET

from .paths import Blocked, REPO, digest, fresh_child, owned_root, safe_extract_tar, safe_extract_zip, write_json

LOCK = REPO / 'docs/build/NATIVE-TOOLCHAIN-LOCK-2C2.json'


def read_lock():
    lock = json.loads(LOCK.read_text())
    if lock['schema'] != 1 or lock['production_certificate_sha256'] != '65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f':
        raise Blocked('Lock schema/production identity mismatch')
    for row in lock['artifacts']:
        if not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or Path(row['filename']).name != row['filename']:
            raise Blocked('Invalid toolchain lock entry')
        if not row['url'].startswith('https://'):
            raise Blocked('Toolchain source must be HTTPS')
    return lock


def resources(root):
    memory = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    limit = Path('/sys/fs/cgroup/memory.max')
    if limit.exists() and limit.read_text().strip() != 'max':
        memory = min(memory, int(limit.read_text()))
    value = {'os': platform.platform(), 'architecture': platform.machine(),
             'free_disk_bytes': shutil.disk_usage(root).free, 'memory_bytes': memory}
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or memory < 2 * 2**30 or value['free_disk_bytes'] < 8 * 2**30:
        raise Blocked('Linux x86_64 with at least 8 GiB free disk and 2 GiB RAM is required')
    return value


def fetch(row, cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    if cache.is_symlink():
        raise Blocked('Symlink toolchain cache')
    for entry in cache.iterdir():
        if entry.suffix.lower() in ('.jks', '.keystore', '.p12', '.pfx', '.key'):
            raise Blocked('Signing material is forbidden in toolchain cache')
    path = cache / row['filename']
    if path.is_symlink():
        raise Blocked('Symlink cache entry')
    if not path.exists():
        temporary = path.with_name(path.name + '.partial')
        if temporary.exists() or temporary.is_symlink():
            raise Blocked('Stale partial download; use a fresh owned cache')
        result = subprocess.run(['/usr/bin/curl', '--fail', '--location', '--connect-timeout', '20', '--max-time', '300',
                                 '--retry', '2', '--proto', '=https', '--proto-redir', '=https',
                                 row['url'], '-o', str(temporary)], capture_output=True, timeout=930)
        if result.returncode:
            temporary.unlink(missing_ok=True)
            raise Blocked('Tool download failed: ' + row['id'] + ' exit ' + str(result.returncode))
        temporary.rename(path)
    if path.stat().st_size != int(row['size']) or digest(path) != row['sha256']:
        raise Blocked('Toolchain SHA-256/size mismatch: ' + row['id'])
    if row.get('published_sha1') and digest(path, 'sha1') != row['published_sha1']:
        raise Blocked('Published Google checksum mismatch')
    # Archives are inputs only. Builders execute extracted working copies, never this cache.
    path.chmod(0o444)
    return path


def verify_signatures(root, lock, downloaded):
    proof = REPO / 'docs/build/provenance'
    temporary = fresh_child(root, root / 'signature-check')
    home = temporary / 'gnupg'
    home.mkdir(mode=0o700)
    rings = {}
    for label, names in [('debian', ['debian-archive-key-12.asc', 'debian-archive-key-13.asc', 'debian-release-13.asc']),
                         ('releases', ['node-release-key.asc', 'adoptium-key.asc'])]:
        raw = b''
        for name in names:
            result = subprocess.run(['/usr/bin/gpg', '--no-options', '--batch', '--yes', '--dearmor',
                                     '--output', '-', str(proof / name)], capture_output=True, timeout=30)
            if result.returncode:
                raise Blocked('Public verification key decode failed')
            raw += result.stdout
        ring = temporary / (label + '.gpg')
        ring.write_bytes(raw)
        rings[label] = ring
    prefix = ['/usr/bin/gpg', '--no-options', '--batch', '--homedir', str(home), '--no-autostart',
              '--no-default-keyring', '--trust-model', 'always', '--status-fd', '1']
    checks = [('debian', [str(proof / 'debian-InRelease')], ['04B54C3CDCA79751B16BC6B5225629DF75B188BD', '41587F7DB8C774BCCF131416762F67A0B2C39DE4']),
              ('releases', [str(proof / 'node-SHASUMS256.txt.asc')], ['5BE8A3F6C8A5C01D106C0AD820B1A390B168D356'])]
    if 'jdk' in downloaded:
        signature = temporary / 'jdk.sig'
        signature.write_bytes(base64.b64decode((proof / 'OpenJDK21U-jdk_x64_linux_hotspot_21.0.13_9.tar.gz.sig.base64').read_text(), validate=False))
        checks.append(('releases', [str(signature), str(downloaded['jdk'])], ['3B04D753C9050D9A5D343F39843C48A565F8F04B']))
    evidence = []
    for ring_name, args, fingerprints in checks:
        result = subprocess.run(prefix + ['--keyring', str(rings[ring_name]), '--verify', *args], capture_output=True, text=True, timeout=60)
        valid = '\n'.join(line for line in result.stdout.splitlines() if 'VALIDSIG' in line)
        if result.returncode or any(fp not in valid for fp in fingerprints):
            raise Blocked('Distribution signature verification failed')
        evidence.append({'type': ring_name, 'exit_code': result.returncode, 'valid_signatures': valid.splitlines()})
    return evidence


def verify_distribution_records(lock, selected, cache):
    """Bind every archive pin to independently published distribution metadata."""
    proof = REPO / 'docs/build/provenance'
    metadata = lock['distribution_metadata']
    for name in ['google', 'node_readme', 'debian_inrelease']:
        if digest(proof / metadata[name]['file']) != metadata[name]['sha256']:
            raise Blocked('Distribution metadata snapshot was modified')
    release = (proof / 'debian-InRelease').read_text()
    index = metadata['debian_packages']
    signed_record = re.search(r'^ ' + re.escape(index['sha256']) + r'\s+' + str(index['size']) + r'\s+' + re.escape(index['signed_release_path']) + r'$', release, re.M)
    if not signed_record:
        raise Blocked('Package index pin is not in signed Debian Release')
    packages = None
    if any(row['kind'] == 'deb' for row in selected):
        packages = lzma.open(fetch(index, cache), 'rt').read().split('\n\n')
    records = {}
    for paragraph in packages or []:
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
        if fields.get('Package'):
            records[(fields['Package'], fields.get('Version'))] = fields
    google = ET.parse(proof / metadata['google']['file']).getroot()
    published = (proof / 'node-SHASUMS256.txt.asc').read_text()
    readme = (proof / 'node-README.md').read_text()
    if '5BE8A3F6C8A5C01D106C0AD820B1A390B168D356' not in readme:
        raise Blocked('Node signer missing from tagged upstream README')
    for row in selected:
        if row['kind'] == 'deb':
            fields = records.get((row['id'], row['version']), {})
            if (fields.get('SHA256') != row['sha256'] or fields.get('Size') != str(row['size'])
                    or row['url'] != 'https://deb.debian.org/debian/' + fields.get('Filename', '')):
                raise Blocked('Archive pin differs from authenticated Debian package index')
        elif row['id'].startswith('node-'):
            if row['sha256'] + '  ' + row['filename'] not in published:
                raise Blocked('Node archive pin missing from signed SHASUMS')
        elif row.get('published_sha1'):
            matches = [archive for archive in google.iter('complete')
                       if archive.findtext('url') == row['filename']
                       and archive.findtext('size') == str(row['size'])
                       and archive.findtext('checksum') == row['published_sha1']]
            if len(matches) != 1:
                raise Blocked('SDK pin differs from official Google metadata snapshot')
    return {'status': 'PASS', 'debian_index_checked': packages is not None,
            'debian_index_sha256': index['sha256'], 'google_publication': 'official HTTPS SHA-1/size',
            'node_signed_shasums_checked': True}


def tool_env(root):
    root = Path(root)
    env = dict(os.environ)
    for name in list(env):
        if re.search(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH', name, re.I) or name.startswith('FLOWDROP_ANDROID_'):
            env.pop(name, None)
    for name in ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'CPATH',
                 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'CLASSPATH', 'JAVA_TOOL_OPTIONS',
                 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS', 'NODE_OPTIONS', 'NPM_TOKEN', 'NODE_AUTH_TOKEN',
                 'PYTHONPATH', 'PYTHONHOME', 'BASH_ENV', 'ENV', 'PERL5LIB', 'TAR_OPTIONS']:
        env.pop(name, None)
    env['PATH'] = os.pathsep.join([str(root / 'jdk/bin'), str(root / 'node-linux/bin'),
                                 str(root / 'tools/mingw/usr/bin'), '/usr/bin', '/bin'])
    env['LD_LIBRARY_PATH'] = str(root / 'tools/mingw/usr/lib/x86_64-linux-gnu')
    env['JAVA_HOME'] = str(root / 'jdk')
    env['FLOWDROP_BUILD_JAVA'] = str(root / 'jdk/bin/java')
    env['FLOWDROP_BUILD_TOOLS'] = str(root / 'tools')
    env['NSISDIR'] = str(root / 'tools/nsis/usr/share/nsis')
    return env


def probe(root, group):
    root = Path(root)
    env = tool_env(root)
    commands = []
    if group in ('android', 'verify', 'all'):
        java = root / 'jdk/bin/java'
        bt = root / 'tools/sdk/build-tools/android-15'
        commands += [('java', [str(java), '-version'], '21.0.13'),
                     ('aapt2', [str(bt / 'aapt2'), 'version'], '2.19-11948202'),
                     ('d8', [str(java), '-cp', str(bt / 'lib/d8.jar'), 'com.android.tools.r8.D8', '--version'], '8.6.2-dev'),
                     ('apksigner', [str(java), '-jar', str(bt / 'lib/apksigner.jar'), 'version'], '0.9')]
    if group in ('windows', 'all'):
        commands += [('gcc', [str(root / 'tools/mingw/usr/bin/x86_64-w64-mingw32-g++-posix'), '-dumpfullversion'], '14-posix'),
                     ('gcc-target', [str(root / 'tools/mingw/usr/bin/x86_64-w64-mingw32-g++-posix'), '-dumpmachine'], 'x86_64-w64-mingw32'),
                     ('windres', [str(root / 'tools/mingw/usr/bin/x86_64-w64-mingw32-windres'), '--version'], '2.44'),
                     ('nsis', [str(root / 'tools/nsis/usr/bin/makensis'), '-VERSION'], '3.11-1'),
                     ('node-linux', [str(root / 'node-linux/bin/node'), '--version'], 'v24.22.2')]
    if group in ('windows', 'verify', 'all'):
        commands += [('7zip', [str(root / 'tools/mingw/usr/lib/7zip/7z'), 'i'], '25.01')]
    result = []
    for name, args, expected in commands:
        value = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
        output = (value.stdout + value.stderr).strip()
        result.append({'tool': name, 'command': args, 'exit_code': value.returncode, 'observed': output, 'expected': expected})
        write_json(root / 'logs/toolchain-probes.json', result)
        if value.returncode or expected not in output:
            raise Blocked('Pinned tool version probe failed: ' + name + '; see provisioning report')
    return result


def provision(root, cache, group):
    root = owned_root(root)
    report = {'status': 'NOT VERIFIED', 'group': group, 'resources': resources(root), 'artifacts': []}
    lock = read_lock()
    selected = [row for row in lock['artifacts'] if group == 'all' or group in row['groups']]
    downloaded = {}
    for row in selected:
        downloaded[row['id']] = fetch(row, cache)
    report['signatures'] = verify_signatures(root, lock, downloaded)
    report['distribution_records'] = verify_distribution_records(lock, selected, cache)
    for row in selected:
        destination = root / row['destination']
        path = downloaded[row['id']]
        if row['kind'] == 'zip':
            safe_extract_zip(path, destination, row.get('strip', 0))
        elif row['kind'] == 'tar':
            with tarfile.open(path, 'r:*') as stream:
                safe_extract_tar(stream, destination, row.get('strip', 0))
        elif row['kind'] == 'deb':
            value = subprocess.run(['/usr/bin/dpkg-deb', '--fsys-tarfile', str(path)], capture_output=True, timeout=120)
            if value.returncode:
                raise Blocked('Authenticated Debian archive decode failed')
            with tarfile.open(fileobj=io.BytesIO(value.stdout), mode='r:') as stream:
                safe_extract_tar(stream, destination, debian=True)
        else:
            raise Blocked('Unknown toolchain archive type')
        report['artifacts'].append({k: row[k] for k in ['id', 'url', 'sha256', 'size', 'authentication']})
        print('PROVISIONED:', row['id'], flush=True)
    report['versions'] = probe(root, group)
    report.update(status='PASS', exit_code=0)
    write_json(root / 'logs/toolchain.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--cache-root', required=True)
    parser.add_argument('--group', choices=['android', 'windows', 'verify', 'all'], required=True)
    args = parser.parse_args()
    root = owned_root(args.work_root)
    try:
        provision(root, Path(args.cache_root), args.group)
    except Exception as error:
        write_json(root / 'logs/toolchain.json', {'status': 'BLOCKED', 'exit_code': 1, 'reason': str(error)})
        print('BLOCKED: toolchain provisioning; inspect public toolchain report', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
