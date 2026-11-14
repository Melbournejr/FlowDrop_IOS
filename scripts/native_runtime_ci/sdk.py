"""Pinned official emulator tooling. No images, userdata or adb keys are artifacts."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from scripts.native_build_ci.paths import archive_name, owned_root
from scripts.native_build_ci.toolchain import fetch, provision, tool_env
from .common import Blocked, REPO, sha256


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


def prepare(root, api, recorder):
    root = Path(root)
    if shutil.disk_usage(root).free < 15 * 2**30:
        raise Blocked('Runtime emulator requires at least 15 GiB free disk')
    tool = owned_root(root / 'toolchain')
    cache = tool / 'download-cache'
    provision(tool, cache, 'android')
    sdk = tool / 'tools/sdk'
    for row in selected_rows(api):
        path = fetch(row, cache)
        if row['id'].startswith('system-images;'):
            destination = sdk / 'system-images' / ('android-' + str(api)) / 'default'
        else:
            destination = sdk
        extract_runtime_zip(path, destination)
    env = tool_env(tool)
    android_user = root / 'android-user'
    android_user.mkdir(mode=0o700)
    avds = root / 'avds'; avds.mkdir()
    env.update(ANDROID_SDK_ROOT=str(sdk), ANDROID_HOME=str(sdk), ANDROID_USER_HOME=str(android_user),
               ANDROID_AVD_HOME=str(avds), ADB_VENDOR_KEYS=str(android_user / 'adbkey'),
               ADB_SERVER_PORT='5039', ANDROID_ADB_SERVER_PORT='5039', QT_QPA_PLATFORM='offscreen')
    adb = sdk / 'platform-tools/adb'
    recorder.run('adb-version', [adb, 'version'], env=env)
    recorder.run('emulator-version', [sdk / 'emulator/emulator', '-version'], env=env)
    recorder.run('avdmanager-list', [sdk / 'cmdline-tools/bin/avdmanager', 'list', 'device'], env=env)
    recorder.run('adb-ephemeral-key', [adb, 'keygen', android_user / 'adbkey'], env=env)
    for file in android_user.glob('adbkey*'):
        file.chmod(0o600)
    name = 'FlowDrop_API_' + str(api)
    recorder.run('create-owned-avd', [sdk / 'cmdline-tools/bin/avdmanager', 'create', 'avd', '--force', '--name', name,
        '--package', 'system-images;android-' + str(api) + ';default;x86_64', '--path', avds / (name + '.avd'), '--device', 'pixel_2'],
        env=env, input='no\n')
    config = avds / (name + '.avd/config.ini')
    with config.open('a', encoding='utf-8') as output:
        output.write('\nhw.ramSize=2048\nhw.cpu.ncore=2\nhw.keyboard=yes\ndisk.dataPartition.size=2G\nhw.gpu.enabled=yes\nhw.gpu.mode=swiftshader\n')
    return {'tool': tool, 'sdk': sdk, 'adb': adb, 'emulator': sdk / 'emulator/emulator', 'env': env, 'avd': name}
