"""Inspect actual APK/PE/installer bytes. No installation or production signing."""
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

from .paths import Blocked, archive_name, digest, fresh_child

PRODUCTION_CERT = '65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f'
ANDROID_NS = '{http://schemas.android.com/apk/res/android}'
PRIVATE = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{40,}|gh[pousr]_[A-Za-z0-9]{30,}')


def reject_secret_bytes(data, secrets=()):
    if PRIVATE.search(data) or any(value and value.encode() in data for value in secrets):
        raise Blocked('Sensitive material detected in output; refusing export')


def apk_identity(badging):
    package = re.search(r"^package: name='([^']+)' versionCode='([^']*)' versionName='([^']*)'", badging, re.M)
    sdk = re.search(r"^(?:minSdkVersion|sdkVersion):'(\d+)'", badging, re.M)
    target = re.search(r"^targetSdkVersion:'(\d+)'", badging, re.M)
    if not package or not sdk or not target:
        raise Blocked('Compiled APK metadata is incomplete')
    return {'package': package[1], 'version_code': package[2], 'version_name': package[3],
            'min_sdk': int(sdk[1]), 'target_sdk': int(target[1]),
            'permissions': sorted(set(re.findall(r"^uses-permission(?:-sdk-\d+)?: name='([^']+)'", badging, re.M)))}


def certificate_fingerprint(output):
    found = re.findall(r'Signer #\d+ certificate SHA-256 digest:\s*([a-fA-F0-9]{64})', output)
    if len(found) != 1:
        raise Blocked('Expected exactly one APK signing certificate')
    return found[0].lower()


def verify_apk(path, source, root, journal, expected_cert, instrumentation=False, secrets=()):
    path, source, root = Path(path), Path(source), Path(root)
    if expected_cert == PRODUCTION_CERT or not re.fullmatch('[0-9a-f]{64}', expected_cert):
        raise Blocked('Only a distinct test certificate is permitted')
    bt = root / 'tools/sdk/build-tools/android-15'
    java = root / 'jdk/bin/java'
    label = 'instrumentation' if instrumentation else 'app'
    signature = journal.run(label + '-signature', [java, '-jar', bt / 'lib/apksigner.jar', 'verify', '--verbose', '--print-certs', path])
    actual_cert = certificate_fingerprint(signature)
    if actual_cert != expected_cert:
        raise Blocked('APK certificate does not match this run temporary key')
    journal.run(label + '-zipalign', [bt / 'zipalign', '-c', '-p', '4', path])
    badging = journal.run(label + '-badging', [bt / 'aapt2', 'dump', 'badging', path])
    actual = apk_identity(badging)
    manifest = ET.parse(source / ('tests/android-native-smoke/AndroidManifest.xml' if instrumentation else 'android/AndroidManifest.xml')).getroot()
    expected_package = 'app.flowdrop.mobile.test' if instrumentation else 'app.flowdrop.mobile'
    if actual['package'] != expected_package or actual['min_sdk'] != 29 or actual['target_sdk'] != 35:
        raise Blocked('APK package or SDK levels changed')
    if not instrumentation and (actual['version_code'] != '14' or actual['version_name'] != '1.13.0'):
        raise Blocked('APK production version metadata changed')
    permissions = sorted(n.attrib[ANDROID_NS + 'name'] for n in manifest if n.tag.startswith('uses-permission'))
    if actual['permissions'] != permissions:
        raise Blocked('Compiled APK permissions differ from source baseline')
    xmltree = journal.run(label + '-manifest-tree', [bt / 'aapt2', 'dump', 'xmltree', path, '--file', 'AndroidManifest.xml'])
    if instrumentation:
        for item in manifest.findall('instrumentation'):
            if item.attrib[ANDROID_NS + 'name'] not in xmltree or 'app.flowdrop.mobile' not in xmltree:
                raise Blocked('Missing compiled instrumentation declaration')
    inventory = []
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise Blocked('APK ZIP CRC mismatch')
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise Blocked('Duplicate APK member')
        for info in archive.infolist():
            name = archive_name(info.filename)
            allowed = str(name) in ['AndroidManifest.xml', 'resources.arsc'] or re.fullmatch(r'classes\d*\.dex', str(name)) or str(name).startswith('META-INF/')
            if not instrumentation:
                allowed = allowed or str(name).startswith('res/') or str(name).startswith('assets/fonts/')
            if not allowed or info.file_size > 64 * 2**20:
                raise Blocked('Unexpected APK payload member')
            data = archive.read(info)
            reject_secret_bytes(data, secrets)
            if str(name).endswith('.dex'):
                if data[:4] != b'dex\n' or len(data) < 112 or hashlib.sha1(data[32:]).digest() != data[12:32] or zlib.adler32(data[12:]) & 0xffffffff != struct.unpack_from('<I', data, 8)[0]:
                    raise Blocked('Invalid DEX header/checksum')
            if str(name).startswith('assets/fonts/'):
                original = source / 'web' / str(name)
                if not original.is_file() or original.read_bytes() != data:
                    raise Blocked('APK font/license bytes changed')
            inventory.append({'path': str(name), 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        if 'AndroidManifest.xml' not in names or 'classes.dex' not in names:
            raise Blocked('APK required manifest/DEX missing')
        if not instrumentation:
            required = ['resources.arsc', 'res/drawable/ic_launcher.xml', 'assets/fonts/OFL.txt'] + ['assets/fonts/BeVietnamPro-' + n + '.ttf' for n in ['Regular', 'Medium', 'Bold']]
            if not set(required).issubset(names):
                raise Blocked('Required app resources/fonts absent')
    return {'status': 'PASS', 'type': label, 'identity': actual, 'test_certificate_sha256': actual_cert,
            'production_signing_equivalence': 'NOT VERIFIED; intentionally different test certificate',
            'size': path.stat().st_size, 'sha256': digest(path), 'inventory': inventory}


def pe_info(data):
    if len(data) < 256 or data[:2] != b'MZ':
        raise Blocked('Not a PE executable')
    pe = struct.unpack_from('<I', data, 60)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        raise Blocked('Invalid PE header')
    machine, sections = struct.unpack_from('<HH', data, pe + 4)
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    optional = pe + 24
    if optional + optional_size > len(data) or optional_size < 96:
        raise Blocked('Invalid PE optional header')
    magic = struct.unpack_from('<H', data, optional)[0]
    if magic not in (0x10b, 0x20b):
        raise Blocked('Unknown PE format')
    subsystem = struct.unpack_from('<H', data, optional + 68)[0]
    directory = optional + (112 if magic == 0x20b else 96)
    cert = struct.unpack_from('<II', data, directory + 4 * 8)
    resource_rva, resource_size = struct.unpack_from('<II', data, directory + 2 * 8)
    section_table = optional + optional_size
    mappings = []
    if sections > 100 or section_table + sections * 40 > len(data):
        raise Blocked('Invalid PE section table')
    for index in range(sections):
        offset = section_table + index * 40
        virtual_size, rva, raw_size, raw_offset = struct.unpack_from('<IIII', data, offset + 8)
        if raw_offset + raw_size > len(data):
            raise Blocked('PE section escapes file')
        mappings.append((rva, max(virtual_size, raw_size), raw_offset, raw_size))
    def file_offset(rva, size):
        for start, span, raw, raw_size in mappings:
            if start <= rva and rva + size <= start + span and rva - start + size <= raw_size:
                return raw + rva - start
        raise Blocked('PE resource RVA escapes section')
    resources = []
    if resource_rva and resource_size:
        base = file_offset(resource_rva, resource_size)
        visited = set()
        def walk(relative, path):
            if relative in visited or len(path) > 3 or relative + 16 > resource_size:
                raise Blocked('Invalid PE resource tree')
            visited.add(relative)
            named, ids = struct.unpack_from('<HH', data, base + relative + 12)
            if named + ids > 4096 or relative + 16 + (named + ids) * 8 > resource_size:
                raise Blocked('PE resource directory overflow')
            for index in range(named + ids):
                key, child = struct.unpack_from('<II', data, base + relative + 16 + index * 8)
                name = key & 0xffff if not key & 0x80000000 else 'named'
                current = path + [name]
                if child & 0x80000000:
                    walk(child & 0x7fffffff, current)
                else:
                    if child + 16 > resource_size:
                        raise Blocked('PE resource data entry overflow')
                    rva, size = struct.unpack_from('<II', data, base + child)
                    offset = file_offset(rva, size)
                    resources.append((current, data[offset:offset + size]))
        walk(0, [])
    return {'machine': machine, 'optional_magic': magic, 'subsystem': subsystem,
            'authenticode_directory': list(cert), 'resources': resources}


def verify_windows_payload(payload, source):
    payload, source = Path(payload), Path(source)
    raw = (payload / 'FlowDrop.exe').read_bytes()
    image = pe_info(raw)
    if image['machine'] != 0x8664 or image['optional_magic'] != 0x20b or image['subsystem'] != 2:
        raise Blocked('FlowDrop.exe must be x64 Windows GUI')
    if image['authenticode_directory'] != [0, 0]:
        raise Blocked('Unexpected Authenticode identity')
    versions = [value for path, value in image['resources'] if path[0] == 16]
    signature = struct.pack('<I', 0xFEEF04BD)
    if not versions or not all(signature in value for value in versions):
        raise Blocked('PE version resource missing')
    for value in versions:
        offset = value.index(signature)
        if struct.unpack_from('<IIII', value, offset + 8) != (0x0001000d, 0, 0x0001000d, 0):
            raise Blocked('PE version differs from 1.13.0.0')
    icon = (source / 'desktop/windows/FlowDrop.ico').read_bytes()
    count = struct.unpack_from('<H', icon, 4)[0]
    expected_icons = []
    for index in range(count):
        size, offset = struct.unpack_from('<II', icon, 6 + index * 16 + 8)
        expected_icons.append(hashlib.sha256(icon[offset:offset + size]).hexdigest())
    actual_icons = [hashlib.sha256(value).hexdigest() for path, value in image['resources'] if path[0] == 3]
    if sorted(actual_icons) != sorted(expected_icons) or not any(path[0] == 14 for path, _ in image['resources']):
        raise Blocked('Compiled Windows icon differs from original')
    expected_manifest = (source / 'desktop/windows/FlowDrop.manifest').read_bytes().rstrip(b'\0')
    if not any(path[0] == 24 and value.rstrip(b'\0') == expected_manifest for path, value in image['resources']):
        raise Blocked('Compiled Windows manifest changed')
    pin = json.loads((source / 'desktop/windows/runtime.json').read_text())
    if digest(payload / 'runtime/node.exe') != pin['executableSha256']:
        raise Blocked('Windows Node runtime pin mismatch')
    for name in ['runtime/LICENSE', 'nlohmann-json-license-and-source.hpp', 'Huong-dan.md', 'package.json', 'FlowDrop.vbs', 'Stop-FlowDrop.vbs', 'Allow-LAN.ps1']:
        if not (payload / name).is_file():
            raise Blocked('Payload license/startup/documentation absent')
    for folder in ['web', 'worker']:
        for file in (source / folder).rglob('*'):
            if file.is_file() and (not (payload / file.relative_to(source)).is_file() or file.read_bytes() != (payload / file.relative_to(source)).read_bytes()):
                raise Blocked('Windows web/worker/font payload changed')
    expected_scripts = ['request-security.mjs','device-name.mjs','dev.mjs','stop.mjs','discovery.mjs','desktop-storage.mjs','local-bucket.mjs','peer-offers.mjs','lan-discovery.mjs','folder-jobs.mjs','folder-zip.mjs','folder-receive.mjs','code-lookup.mjs','secure-update.mjs','release-config.mjs']
    for name in expected_scripts:
        if (payload / 'scripts' / name).read_bytes() != (source / 'scripts' / name).read_bytes():
            raise Blocked('Required LAN/folder/security script changed')
    lock = json.loads((source / 'package-lock.json').read_text())['packages']
    packages = []
    for name, record in lock.items():
        if not name:
            continue
        actual = json.loads((payload / name / 'package.json').read_text())
        if actual['version'] != record['version']:
            raise Blocked('Payload npm dependency differs from lock')
        packages.append({'name': actual['name'], 'version': actual['version'], 'license': actual.get('license')})
    inventory = []
    for file in sorted(payload.rglob('*')):
        if file.is_symlink():
            # NSIS dereferences npm's internal .bin link; verify those bytes too.
            if not file.resolve().is_relative_to(payload) or not file.is_file():
                raise Blocked('External payload symlink')
        if file.is_file():
            name = file.relative_to(payload)
            if file.suffix.lower() in ['.jks', '.keystore', '.p12', '.pfx', '.key', '.o', '.class', '.apk'] or any(part in ['.git', '.npm', 'test-secrets', '.cache'] for part in name.parts):
                raise Blocked('Build/cache/signing material in Windows payload')
            reject_secret_bytes(file.read_bytes())
            inventory.append({'path': name.as_posix(), 'size': file.stat().st_size, 'sha256': digest(file)})
    return {'status': 'PASS', 'machine': 'AMD64', 'subsystem': 'WINDOWS_GUI', 'version': '1.13.0.0',
            'icon_png_count': len(actual_icons), 'node_version': pin['nodeVersion'],
            'node_sha256': pin['executableSha256'], 'npm_packages': packages, 'inventory': inventory}


def inspect_installer(installer, root, journal):
    installer, root = Path(installer), Path(root)
    bootstrap = pe_info(installer.read_bytes())
    # The baseline NSIS bootstrap is x86; its installed FlowDrop.exe is x64.
    if bootstrap['machine'] != 0x14c or bootstrap['subsystem'] != 2 or bootstrap['authenticode_directory'] != [0, 0]:
        raise Blocked('NSIS bootstrap architecture/subsystem/signature changed')
    # Debian's /usr/bin/7z is a wrapper with an absolute /usr/lib path.
    # Execute the authenticated relocated binary, not that host-dependent wrapper.
    seven = root / 'tools/mingw/usr/lib/7zip/7z'
    listing = journal.run('nsis-list', [seven, 'l', '-slt', installer])
    body = listing.split('----------', 1)[-1]
    members = re.findall(r'^Path = (.+)$', body, re.M)
    if not members:
        raise Blocked('NSIS payload listing empty')
    if len(members) != len(set(members)):
        raise Blocked('Duplicate NSIS member')
    for member in members:
        archive_name(member.replace('\\', '/'))
    destination = fresh_child(root, root / 'installer-inspection')
    journal.run('nsis-extract', [seven, 'x', '-y', '-o' + str(destination), installer])
    app = list(destination.rglob('FlowDrop.exe'))
    if len(app) != 1:
        raise Blocked('NSIS must contain exactly one native application')
    extracted = app[0].parent
    plugins = {'$PLUGINSDIR/modern-wizard.bmp', '$PLUGINSDIR/nsDialogs.dll', '$PLUGINSDIR/System.dll'}
    for plugin in plugins:
        data = (destination / plugin).read_bytes()
        if not any(candidate.is_file() and candidate.stat().st_size == len(data) and digest(candidate) == hashlib.sha256(data).hexdigest()
                   for candidate in (root / 'tools/nsis/usr/share/nsis').rglob('*')):
            raise Blocked('NSIS plugin differs from authenticated distribution')
    return extracted, {'status': 'PASS', 'nsis_bootstrap_machine': 'I386 (baseline)',
                       'installed_application_machine': 'AMD64', 'members': members,
                       'size': installer.stat().st_size, 'sha256': digest(installer)}


def verify_installer(installer, payload, root, journal):
    payload = Path(payload)
    extracted, report = inspect_installer(installer, root, journal)
    expected = {'$PLUGINSDIR/modern-wizard.bmp', '$PLUGINSDIR/nsDialogs.dll', '$PLUGINSDIR/System.dll'}
    for original in payload.rglob('*'):
        if original.is_file():
            target = extracted / original.relative_to(payload)
            if not target.is_file() or digest(target) != digest(original):
                raise Blocked('Installer payload differs from freshly built payload')
            expected.add(original.relative_to(payload).as_posix())
    if set(report.pop('members')) != expected:
        raise Blocked('Unexpected or missing installer payload members')
    report['payload_files_verified'] = len(expected) - 3
    return report
