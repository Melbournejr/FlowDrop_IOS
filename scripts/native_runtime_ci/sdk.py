"""Pinned official emulator tooling. No images, userdata or adb keys are artifacts."""
import json
import copy
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import quoteattr

from scripts.native_build_ci.paths import archive_name, owned_root
from scripts.native_build_ci.toolchain import fetch, provision, tool_env
from .common import Blocked, REPO, sha256, json_file


def extract_runtime_zip(path, destination):
    """System images exceed the old build-tool archive limit; validate separately."""
    destination = Path(destination)
    if destination.is_symlink():
        raise Blocked('Runtime archive destination is a link')
    destination.mkdir(parents=True, exist_ok=True)
    plan, names, total = [], set(), 0
    with zipfile.ZipFile(path) as archive:
        for row in archive.infolist():
            name = archive_name(row.filename)
            if name is None:
                continue
            mode = row.external_attr >> 16
            if stat.S_IFMT(mode) not in [0, stat.S_IFREG, stat.S_IFDIR] or row.flag_bits & 1:
                raise Blocked('Runtime archive link/special/encrypted member')
            if str(name).casefold() in names:
                raise Blocked('Duplicate runtime archive path')
            names.add(str(name).casefold())
            total += row.file_size
            if total > 10 * 2**30 or row.file_size > 8 * 2**30:
                raise Blocked('Runtime image archive exceeds explicit limit')
            plan.append((row, name, mode))
        for row, name, mode in plan:
            target = destination / str(name)
            if target.is_symlink() or not target.resolve().is_relative_to(destination.resolve()):
                raise Blocked('Runtime archive escapes destination')
            if row.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise Blocked('Runtime archive would overwrite a previous file')
            with archive.open(row) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            target.chmod(0o755 if mode & 0o111 else 0o644)


def selected_rows(api):
    lock = json.loads((REPO / 'docs/testing/RUNTIME-TOOLCHAIN-LOCK-2D1.json').read_text(encoding='utf-8'))
    selected = [row for row in lock['artifacts'] if not row['id'].startswith('system-images;') or row['id'] == 'system-images;android-' + str(api) + ';default;x86_64']
    for row in selected:
        metadata = REPO / 'docs/testing/runtime-2d1-provenance' / row['metadata']
        if sha256(metadata) != row['metadata_sha256']:
            raise Blocked('Official metadata snapshot hash changed')
        matches = []
        for package in ET.parse(metadata).getroot().findall('remotePackage'):
            if package.get('path') != row['id']:
                continue
            channel = package.find('channelRef')
            if channel is not None and channel.get('ref') != 'channel-0':
                continue
            for complete in package.findall('archives/archive/complete'):
                if complete.findtext('url') == row['filename'] and complete.findtext('checksum') == row['published_sha1'] and complete.findtext('size') == str(row['size']):
                    matches.append(complete)
        if len(matches) != 1 or not row['url'].startswith('https://dl.google.com/android/repository/'):
            raise Blocked('Runtime pin does not match official stable metadata')
    return selected


def installed_metadata(sdk, row):
    """Register the exact downloaded package, as sdkmanager normally would.

    Direct ZIPs omit package.xml. New generic packages (notably emulator) are
    otherwise invisible to avdmanager even though the executable is present.
    Type, revision, dependencies and license are copied from authenticated
    official metadata; no archive selection or binary bytes are changed.
    """
    metadata = REPO / 'docs/testing/runtime-2d1-provenance' / row['metadata']
    if sha256(metadata) != row['metadata_sha256']:
        raise Blocked('Installed package metadata provenance mismatch')
    tree = ET.parse(metadata).getroot()
    matches = [p for p in tree.findall('remotePackage') if p.get('path') == row['id'] and
               any(c.findtext('url') == row['filename'] for c in p.findall('archives/archive/complete'))]
    if len(matches) != 1:
        raise Blocked('Installed package is not uniquely bound to downloaded archive')
    package = ET.Element('localPackage', {'path': row['id'], 'obsolete': 'false'})
    for element in matches[0]:
        if element.tag not in ['archives', 'channelRef']:
            package.append(copy.deepcopy(element))
    namespaces = dict(data for _, data in ET.iterparse(metadata, events=['start-ns']))
    declarations = ' '.join('xmlns:' + prefix + '=' + quoteattr(uri) for prefix, uri in namespaces.items() if prefix)
    raw = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<localrepo:repository xmlns:localrepo="http://schemas.android.com/repository/android/common/02" ' + declarations + '>\n'
           + '\n'.join(ET.tostring(license, encoding='unicode') for license in tree.findall('license'))
           + ET.tostring(package, encoding='unicode') + '\n</localrepo:repository>\n')
    ET.fromstring(raw)
    directory = Path(sdk).joinpath(*row['id'].split(';'))
    if not (directory / 'source.properties').is_file():
        raise Blocked('Installed package directory/source.properties absent')
    destination = directory / 'package.xml'
    with destination.open('x', encoding='utf-8') as output:
        output.write(raw)
    return {'id': row['id'], 'official_metadata_sha256': row['metadata_sha256'], 'installed_package_xml_sha256': sha256(destination)}


def official_ubuntu_mirrors(text):
    urls = [line.split()[0] for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if not urls:
        raise Blocked('Empty Ubuntu mirror list')
    for value in urls:
        url = urllib.parse.urlsplit(value)
        if (url.scheme not in ['http', 'https'] or url.username or url.password or url.query or url.fragment or
            not re.fullmatch(r'(?:[a-z0-9-]+\.)*(?:archive|security)\.ubuntu\.com', url.hostname or '') or url.path.rstrip('/') != '/ubuntu'):
            raise Blocked('Mirror file contains a non-official Ubuntu archive')
    return urls


def host_libraries(emulator, recorder, env):
    """Install only the missing library observed on the isolated Ubuntu 24.04 VM.

    APT verifies distribution signatures; the selected candidate is fixed in the
    install argv and its origin/version are recorded, rather than calling it a
    pinned upstream emulator archive or silently swapping the emulator.
    """
    binary = emulator.parent / 'qemu/linux-x86_64/qemu-system-x86_64'
    # The official launcher supplies these authenticated bundled libraries.
    # Direct ldd without the launcher's paths falsely reports Qt/Android .so files
    # as missing host packages. Scope the paths to dependency inspection only.
    probe_env = dict(env)
    probe_env['LD_LIBRARY_PATH'] = os.pathsep.join(str(emulator.parent / suffix) for suffix in ['lib64', 'lib64/qt/lib'])
    output, code = recorder.run('emulator-host-ldd-before', ['/usr/bin/ldd', binary], env=probe_env, check=False)
    missing = set(re.findall(r'^\s*(\S+) => not found$', output, re.M))
    if not missing:
        if code != 0:
            raise Blocked('Could not inspect emulator host dependencies')
        return
    if missing != {'libpulse.so.0'}:
        raise Blocked('Unreviewed missing emulator host libraries: ' + ', '.join(sorted(missing)))
    os_release = Path('/etc/os-release').read_text()
    if 'ID=ubuntu' not in os_release or 'VERSION_ID="24.04"' not in os_release:
        raise Blocked('Library provisioning is restricted to the owned Ubuntu 24.04 hosted runner')
    recorder.run('ubuntu-signed-package-index', ['sudo', '-n', '/usr/bin/apt-get', 'update'], env=env, timeout=180)
    policy, _ = recorder.run('ubuntu-libpulse-policy', ['/usr/bin/apt-cache', 'policy', 'libpulse0'], env=env)
    candidate = re.search(r'^\s*Candidate:\s*(\S+)$', policy, re.M)
    if not candidate or not re.fullmatch(r'[0-9A-Za-z.+:~_-]+', candidate.group(1)) or candidate.group(1) == '(none)':
        raise Blocked('No explicit libpulse0 distribution candidate')
    # Hosted images now use APT's mirror+file transport, whose policy output
    # does not contain the final HTTPS/HTTP archive URL. Validate the fixed,
    # root-owned list as well as the signed APT index instead of rejecting it
    # or trusting an arbitrary file transport.
    if re.search(r'mirror\+file:/etc/apt/apt-mirrors.txt\s+noble(?:-updates|-security)?/main', policy):
        mirror_file = Path('/etc/apt/apt-mirrors.txt')
        if mirror_file.is_symlink() or mirror_file.stat().st_uid != 0:
            raise Blocked('Ubuntu mirror list is not an owned system file')
        mirrors, _ = recorder.run('ubuntu-official-mirrors', ['/usr/bin/cat', mirror_file], env=env)
        official_ubuntu_mirrors(mirrors)
    elif not re.search(r'https?://(?:[a-z0-9-]+\.)*(?:archive|security)\.ubuntu\.com/ubuntu/?\s+noble(?:-updates|-security)?/main', policy):
        raise Blocked('libpulse0 origin is not an expected official Ubuntu Noble archive')
    recorder.run('ubuntu-libpulse-install', ['sudo', '-n', '/usr/bin/apt-get', 'install', '--yes', '--no-install-recommends',
                 'libpulse0=' + candidate.group(1)], env=env, timeout=180)
    recorder.run('ubuntu-libpulse-observed', ['/usr/bin/dpkg-query', '-W', '-f=${Package} ${Version} ${Architecture}\n', 'libpulse0'], env=env)
    after, code = recorder.run('emulator-host-ldd-after', ['/usr/bin/ldd', binary], env=probe_env, check=False)
    if code != 0 or '=> not found' in after:
        raise Blocked('Emulator still has unresolved host libraries after scoped provisioning')


def prepare(root, api, recorder):
    root = Path(root)
    if shutil.disk_usage(root).free < 15 * 2**30:
        raise Blocked('Runtime emulator requires at least 15 GiB free disk')
    tool = owned_root(root / 'toolchain')
    cache = tool / 'download-cache'
    provision(tool, cache, 'android')
    sdk = tool / 'tools/sdk'
    package_receipts = []
    for row in selected_rows(api):
        path = fetch(row, cache)
        if row['id'].startswith('system-images;'):
            destination = sdk / 'system-images' / ('android-' + str(api)) / 'default'
        else:
            destination = sdk
        extract_runtime_zip(path, destination)
        if row['id'] == 'cmdline-tools;19.0':
            # avdmanager infers the SDK root from cmdline-tools/<version>/bin.
            # A flat archive extraction incorrectly resolves one directory up.
            flat, stage = sdk / 'cmdline-tools', sdk / 'cmdline-tools-layout-stage'
            if stage.exists():
                raise Blocked('Stale command-line tools layout stage')
            flat.rename(stage); flat.mkdir(); stage.rename(flat / '19.0')
        package_receipts.append(installed_metadata(sdk, row))
    json_file(root / 'logs/installed-sdk-packages.json', package_receipts)
    env = tool_env(tool)
    android_user = root / 'android-user'
    android_user.mkdir(mode=0o700)
    emulator_user, xdg = android_user / 'emulator', android_user / 'xdg'
    emulator_user.mkdir(mode=0o700); xdg.mkdir(mode=0o700)
    avds = root / 'avds'; avds.mkdir()
    env.update(ANDROID_SDK_ROOT=str(sdk), ANDROID_HOME=str(sdk), ANDROID_USER_HOME=str(android_user),
               ANDROID_AVD_HOME=str(avds), ADB_VENDOR_KEYS=str(android_user / 'adbkey'),
               ANDROID_EMULATOR_HOME=str(emulator_user), XDG_RUNTIME_DIR=str(xdg),
               ADB_SERVER_PORT='5039', ANDROID_ADB_SERVER_PORT='5039', QT_QPA_PLATFORM='offscreen')
    adb = sdk / 'platform-tools/adb'
    recorder.run('adb-version', [adb, 'version'], env=env)
    host_libraries(sdk / 'emulator/emulator', recorder, env)
    recorder.run('emulator-version', [sdk / 'emulator/emulator', '-version'], env=env)
    recorder.run('avdmanager-list', [sdk / 'cmdline-tools/19.0/bin/avdmanager', 'list', 'device'], env=env)
    recorder.run('adb-ephemeral-key', [adb, 'keygen', android_user / 'adbkey'], env=env)
    for file in android_user.glob('adbkey*'):
        file.chmod(0o600)
    name = 'FlowDrop_API_' + str(api)
    recorder.run('create-owned-avd', [sdk / 'cmdline-tools/19.0/bin/avdmanager', 'create', 'avd', '--force', '--name', name,
        '--package', 'system-images;android-' + str(api) + ';default;x86_64', '--path', avds / (name + '.avd'), '--device', 'pixel_2'],
        env=env, input='no\n')
    config = avds / (name + '.avd/config.ini')
    with config.open('a', encoding='utf-8') as output:
        output.write('\nhw.ramSize=2048\nhw.cpu.ncore=2\nhw.keyboard=yes\ndisk.dataPartition.size=2G\nhw.gpu.enabled=yes\nhw.gpu.mode=swiftshader\n')
    return {'tool': tool, 'sdk': sdk, 'adb': adb, 'emulator': sdk / 'emulator/emulator', 'env': env, 'avd': name}
