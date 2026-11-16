"""FlowDrop 1.13 black-box LAN checks. Standard library only; never installs or deletes apps/files."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import time
import uuid
import zipfile
import zlib

SCHEMA = 1
MARKER = '.flowdrop-lan-test.json'
STATUSES = {'PASS', 'FAIL', 'BLOCKED', 'NOT VERIFIED', 'SKIPPED'}
DIRECTIONS = ['Windows-to-Android', 'Android-to-Windows', 'Windows-to-Windows', 'Android-to-Android']
PROFILES = {'smoke': 0, '100m': 100 * 2**20, '1g': 2**30, 'zip64': 4 * 2**30 + 17}
BLOCK = bytes(i % 251 for i in range(65536))


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Invalid relative test path')
    parts = value.split('/')
    if any(p in ['', '.', '..'] or p.endswith((' ', '.')) or len(p.encode('utf-8')) > 240
           or re.search(r'[\x00-\x1f\x7f<>"|?*]', p) for p in parts):
        raise ValueError('Unsafe or nonportable test path')
    if any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p) for p in parts):
        raise ValueError('Windows reserved name')
    return PurePosixPath(value)


def no_links(path):
    path = Path(path).absolute()
    for node in [path, *path.parents]:
        if node.is_symlink() or (hasattr(node, 'is_junction') and node.is_junction()):
            raise ValueError('Refusing symlink/junction in selected path')
        if node.exists() and getattr(node.stat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Refusing Windows reparse point')
    return path


def beneath(root, name):
    root = no_links(root)
    target = root.joinpath(*safe_relative(name).parts)
    no_links(target)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escaped selected test directory')
    return target


def write_json(path, data):
    # Outputs are only inside a previously owned test workspace.
    path = no_links(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    path = no_links(path)
    if path.stat().st_size > 16 * 2**20:
        raise ValueError('Test JSON too large')
    return json.loads(path.read_text(encoding='utf-8'))


def workspace(value):
    root = no_links(value)
    marker = read_json(root / MARKER)
    if marker.get('schema') != SCHEMA or not re.fullmatch(r'[a-f0-9]{32}', marker.get('run_id', '')):
        raise ValueError('Not an owned FlowDrop LAN test workspace')
    return root, marker


def file_hash(path):
    path = no_links(path)
    before = path.stat()
    if not path.is_file() or before.st_nlink != 1:
        raise ValueError('Expected regular test file without hard links')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('File changed while calculating SHA-256')
    return {'size': after.st_size, 'sha256': digest.hexdigest()}


def pattern(path, size):
    digest = hashlib.sha256()
    with path.open('xb') as stream:
        left = size
        while left:
            chunk = BLOCK[:min(left, len(BLOCK))]
            stream.write(chunk)
            digest.update(chunk)
            left -= len(chunk)
    return {'size': size, 'sha256': digest.hexdigest()}


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\x00' + b'\x00\xff\x80' * 2) * 2)) + chunk(b'IEND', b''))


def pdf():
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>',
               b'<< /Length 0 >>\nstream\n\nendstream']
    output = bytearray(b'%PDF-1.4\n'); offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(output)); output += str(i).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    start = len(output); output += b'xref\n0 5\n0000000000 65535 f \n'
    for offset in offsets:
        output += ('%010d 00000 n \n' % offset).encode()
    return bytes(output) + b'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n' + str(start).encode() + b'\n%%EOF\n'


def avi():
    # Two 2x2 uncompressed RGB frames, one frame/sec, synthetic RIFF AVI.
    def chunk(kind, data):
        return kind + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')
    main = struct.pack('<14I', 1000000, 32, 0, 0, 2, 0, 1, 16, 2, 2, 0, 0, 0, 0)
    stream = struct.pack('<4s4sIHH8I4h', b'vids', b'DIB ', 0, 0, 0, 0, 1, 1, 0, 2, 16, 0xffffffff, 0, 0, 0, 2, 2)
    bitmap = struct.pack('<IiiHHIIiiII', 40, 2, 2, 1, 24, 0, 16, 0, 0, 0, 0)
    header = b'hdrl' + chunk(b'avih', main) + chunk(b'LIST', b'strl' + chunk(b'strh', stream) + chunk(b'strf', bitmap))
    frames = b'movi' + chunk(b'00db', bytes([0, 255, 128, 0, 255, 128, 0, 0]) * 2) * 2
    data = b'AVI ' + chunk(b'LIST', header) + chunk(b'LIST', frames)
    return chunk(b'RIFF', data)


def prepare(root, profile='smoke', allow_large=False, free_bytes=None):
    root = no_links(root)
    if root.exists() or not root.parent.is_dir():
        raise ValueError('Choose a NEW test folder under an existing parent; nothing is overwritten')
    extra = PROFILES[profile]
    if extra and not allow_large:
        raise ValueError('Large profile requires --allow-large after checking free space on BOTH devices')
    available = shutil.disk_usage(root.parent).free if free_bytes is None else free_bytes
    if available < extra * 2 + 512 * 2**20:
        raise ValueError('Insufficient disk for synthetic source plus working space; no files created')
    run_id = uuid.uuid4().hex
    root.mkdir(mode=0o700)
    marker = {'schema': SCHEMA, 'run_id': run_id, 'profile': profile, 'created_utc_epoch': time.time()}
    write_json(root / MARKER, marker)
    name = 'FlowDrop-LAN-' + run_id[:12]
    payload = root / name; payload.mkdir()
    prefix = 'FD-' + run_id[:8] + '-'
    # Keep the full generated path within legacy Win32 limits; no OS policy change.
    max_long = min(160, 240 - len(str(payload).encode('utf-16-le')) // 2 - len(prefix) - 12)
    if max_long < 40:
        raise ValueError('Select a shorter workspace path for the portable long-name fixture')
    records = []
    start = time.perf_counter()
    specs = [(prefix + 'empty.bin', 0), (prefix + '1KiB.bin', 1024), (prefix + '1MiB.bin', 2**20),
             ('Thư mục 测试 📂/' + prefix + 'Tiếng Việt 中文 😀 có khoảng trắng.txt', 1057),
             (prefix + 'long ' + 'a' * max_long + '.bin', 32769)]
    specs += [('Nhiều file/' + prefix + '%03d.txt' % i, i) for i in range(101)]
    if extra:
        specs.append((prefix + profile + '.bin', extra))
    for relative, size in specs:
        target = beneath(payload, relative); target.parent.mkdir(parents=True, exist_ok=True)
        records.append({'path': relative, **pattern(target, size)})
    for suffix, data in [('image.png', png()), ('video.avi', avi()), ('document.pdf', pdf())]:
        relative = prefix + suffix; target = beneath(payload, relative)
        with target.open('xb') as stream:
            stream.write(data)
        records.append({'path': relative, **file_hash(target)})
    relative = prefix + 'archive.zip'; target = beneath(payload, relative)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('Tài liệu 中文.txt', 'FlowDrop synthetic fixture\n')
        archive.writestr('Empty directory/', b'')
    records.append({'path': relative, **file_hash(target)})
    empty_dirs = ['Thư mục 测试 📂/Cấp hai/Thư mục rỗng', 'Empty folder']
    for relative in empty_dirs:
        beneath(payload, relative).mkdir(parents=True)
    manifest = {'schema': SCHEMA, 'run_id': run_id, 'profile': profile, 'payload_folder': name,
                'source_environment': environment(root), 'files': records, 'empty_directories': empty_dirs,
                'total_bytes': sum(f['size'] for f in records), 'file_count': len(records),
                'generation_seconds': time.perf_counter() - start,
                'transport_status': 'NOT VERIFIED', 'synthetic_data_only': True}
    write_json(root / 'source-manifest.json', manifest)
    return manifest


def environment(root):
    usage = shutil.disk_usage(no_links(root))
    return {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(),
            'python': platform.python_version(), 'free_disk_bytes': usage.free,
            'physical_wifi_status': 'NOT VERIFIED', 'firewall_changed': False,
            'production_app_changed': False}


def manifest(root):
    root, marker = workspace(root)
    doc = read_json(root / 'source-manifest.json')
    if doc.get('run_id') != marker['run_id'] or doc.get('schema') != SCHEMA:
        raise ValueError('Manifest does not belong to this workspace')
    timing = root / 'timing-start.json'
    if timing.exists() and read_json(timing).get('source_manifest_sha256') != file_hash(root / 'source-manifest.json')['sha256']:
        raise ValueError('Source manifest changed after timing started')
    safe_relative(doc['payload_folder'])
    if '/' in doc['payload_folder'] or doc['payload_folder'] != 'FlowDrop-LAN-' + marker['run_id'][:12]:
        raise ValueError('Wrong synthetic payload folder identity')
    seen = set()
    for entry in doc['files']:
        name = str(safe_relative(entry['path']))
        if name.casefold() in seen or not re.fullmatch('[0-9a-f]{64}', entry['sha256']) or not isinstance(entry['size'], int) or entry['size'] < 0:
            raise ValueError('Invalid/duplicate manifest entry')
        seen.add(name.casefold())
    if len(seen) != doc['file_count'] or sum(x['size'] for x in doc['files']) != doc['total_bytes']:
        raise ValueError('Manifest counts do not agree')
    for path in doc['empty_directories']:
        safe_relative(path)
    return root, doc


def compare(root, destination, name_map=None):
    root, doc = manifest(root); destination = no_links(destination)
    mapping = {} if name_map is None else read_json(name_map)
    expected = {f['path'] for f in doc['files']}
    if not isinstance(mapping, dict) or not set(mapping) <= expected:
        raise ValueError('Name map may only map explicit synthetic source files')
    targets = [str(safe_relative(mapping.get(f['path'], f['path']))) for f in doc['files']]
    if any(not PurePosixPath(p).name.startswith('FD-' + doc['run_id'][:8] + '-') for p in targets):
        raise ValueError('Mapped files must retain the unique synthetic run prefix')
    if len({p.casefold() for p in targets}) != len(targets):
        raise ValueError('Name map merges multiple source files into one destination')
    start = time.perf_counter(); rows = []
    for item, path in zip(doc['files'], targets):
        try:
            actual = file_hash(beneath(destination, path))
            ok = actual == {'size': item['size'], 'sha256': item['sha256']}
            rows.append({'path': item['path'], 'destination_relative': path, 'expected': item,
                         'actual': actual, 'status': 'PASS' if ok else 'FAIL'})
        except (OSError, ValueError):
            rows.append({'path': item['path'], 'destination_relative': path, 'status': 'FAIL',
                         'reason': 'Missing, inaccessible, changing, linked or unsafe destination'})
    directories = [{'path': p, 'status': 'PASS' if beneath(destination, p).is_dir() else 'FAIL'}
                   for p in doc['empty_directories']]
    result = {'schema': SCHEMA, 'run_id': doc['run_id'], 'layer': 'file-integrity-only',
              'status': 'PASS' if all(x['status'] == 'PASS' for x in rows + directories) else 'FAIL',
              'files': rows, 'empty_directories': directories, 'hashing_seconds': time.perf_counter() - start,
              'total_bytes': doc['total_bytes'], 'physical_lan_verification': 'NOT VERIFIED',
              'native_application_behavior': 'NOT VERIFIED', 'destination_environment': environment(destination)}
    write_json(root / 'comparison.json', result)
    return result


def start(root, direction, mode, network, artifact=None):
    root, doc = manifest(root)
    if (root / 'timing-start.json').exists():
        raise ValueError('Timing already exists: create another workspace for an independent run')
    # Recheck every generated source before operator sends it.
    for row in doc['files']:
        if file_hash(beneath(root / doc['payload_folder'], row['path'])) != {'size': row['size'], 'sha256': row['sha256']}:
            raise ValueError('Synthetic source changed before send')
    product = file_hash(artifact) if artifact else None
    record = {'run_id': doc['run_id'], 'direction': direction, 'mode': mode, 'network_operator_declared': network,
              'source_manifest_sha256': file_hash(root / 'source-manifest.json')['sha256'],
              'clock_origin_sha256': hashlib.sha256(platform.node().encode()).hexdigest(),
              'started_epoch': time.time(), 'started_monotonic_ns': time.perf_counter_ns(),
              'clock_method': 'High resolution perf_counter_ns; monotonic and process-shared on supported Python 3.12+',
              'artifact': product, 'artifact_provenance': 'locally measured SHA only; source commit NOT VERIFIED',
              'app_version': 'NOT VERIFIED; record actual UI/package evidence in checklist'}
    write_json(root / 'timing-start.json', record)
    return {'status': 'NOT VERIFIED', 'instruction': 'Send only the generated payload folder in FlowDrop. Run stop immediately after the receiver finishes.'}


def stop(root):
    root, _ = workspace(root); record = read_json(root / 'timing-start.json')
    if record.get('clock_origin_sha256') != hashlib.sha256(platform.node().encode()).hexdigest():
        raise ValueError('Stop timing on the same control computer that started it')
    if (root / 'timing-stop.json').exists():
        raise ValueError('Stop evidence already exists')
    seconds = (time.perf_counter_ns() - record['started_monotonic_ns']) / 1e9
    wall = time.time() - record['started_epoch']
    if seconds <= 0 or abs(wall - seconds) > 5:
        raise ValueError('Clock/reboot inconsistency; timing not verified')
    out = {'run_id': record['run_id'], 'elapsed_seconds': seconds,
           'method': 'Operator start/stop wall interval including UI and human overhead; NOT wire-only throughput',
           'transport_success': 'NOT VERIFIED'}
    write_json(root / 'timing-stop.json', out)
    return out


def adb_hash(root, executable, serial, remote_parent, purpose='destination'):
    root, doc = manifest(root)
    executable = no_links(executable)
    if not executable.is_file() or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', serial):
        raise ValueError('Select a trusted adb executable and one explicit device serial')
    allowed = ['/sdcard/Download/FlowDrop', '/storage/emulated/0/Download/FlowDrop']
    parent = str(PurePosixPath(remote_parent))
    if not any(parent.startswith(p + '/') for p in allowed) or PurePosixPath(parent).name != doc['payload_folder']:
        raise ValueError('ADB reads only the exact unique generated folder under Download/FlowDrop')
    safe_relative(parent.lstrip('/'))
    def run(*args):
        completed = subprocess.run([str(executable), '-s', serial, *args], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=300, check=True, encoding='utf-8')
        if len(completed.stdout) > 65536:
            raise ValueError('ADB response exceeds expected bound')
        return completed.stdout.strip()
    if run('get-state') != 'device':
        raise ValueError('ADB device not ready')
    sdk = int(run('shell', 'getprop ro.build.version.sdk'))
    rows = []
    # No logcat, profile, history, token, content provider or broad filesystem scan.
    for row in doc['files']:
        path = parent + '/' + row['path']; safe_relative(path.lstrip('/'))
        parts = PurePosixPath(path).parts
        checks = ['test ! -L ' + shlex.quote(str(PurePosixPath(*parts[:i]))) for i in range(2, len(parts) + 1)]
        command = ' && '.join(checks + ['toybox stat -c %s ' + shlex.quote(path), 'toybox sha256sum ' + shlex.quote(path)])
        try:
            lines = run('shell', command).splitlines()
            actual = {'size': int(lines[0]), 'sha256': lines[1].split()[0]}
            assert re.fullmatch(r'[a-f0-9]{64}', actual['sha256'])
            rows.append({'path': row['path'], 'expected': row, 'actual': actual,
                         'status': 'PASS' if actual == {'size': row['size'], 'sha256': row['sha256']} else 'FAIL'})
        except (ValueError, subprocess.SubprocessError, AssertionError, IndexError):
            rows.append({'path': row['path'], 'status': 'FAIL', 'reason': 'ADB missing/unsafe/mismatched synthetic file'})
    directories = []
    for relative in doc['empty_directories']:
        path = parent + '/' + relative
        try:
            command = 'test ! -L ' + shlex.quote(path) + ' && test -d ' + shlex.quote(path)
            run('shell', command); status = 'PASS'
        except subprocess.SubprocessError:
            status = 'FAIL'
        directories.append({'path': relative, 'status': status})
    result = {'run_id': doc['run_id'], 'status': 'PASS' if all(x['status'] == 'PASS' for x in rows + directories) else 'FAIL',
              'layer': 'ADB read-only file integrity', 'android_api': sdk, 'adb_executable': file_hash(executable),
              'device_serial_sha256': hashlib.sha256(serial.encode()).hexdigest(),
              'files': rows, 'empty_directories': directories, 'total_bytes': doc['total_bytes'],
              'physical_lan_verification': 'NOT VERIFIED', 'native_application_behavior': 'NOT VERIFIED'}
    write_json(root / ('android-source-comparison.json' if purpose == 'source' else 'comparison.json'), result)
    return result


def report(root):
    root, doc = manifest(root)
    result = {'schema': SCHEMA, 'run_id': doc['run_id'], 'phase': '2D.2-B', 'status': 'NOT VERIFIED',
              'source_manifest_sha256': file_hash(root / 'source-manifest.json')['sha256'],
              'file_integrity': 'NOT VERIFIED', 'physical_wifi': 'NOT VERIFIED',
              'native_e2e': 'NOT VERIFIED', 'cpu_peak_rss': 'NOT VERIFIED',
              'discovery_seconds': 'NOT VERIFIED', 'cleanup_seconds': 'NOT VERIFIED',
              'production_signing': 'NOT VERIFIED', 'resume': 'NOT DESIGNED; no resume protocol claimed',
              'instructions': 'Attach completed operator checklist and app/version/network evidence; a hash match alone is not physical LAN proof.'}
    for filename, key in [('comparison.json', 'comparison'), ('android-source-comparison.json', 'android_source'), ('timing-start.json', 'transfer_context'), ('timing-stop.json', 'timing')]:
        if (root / filename).exists():
            result[key] = read_json(root / filename)
    comparison = result.get('comparison')
    if comparison:
        if comparison.get('run_id') != doc['run_id'] or len(comparison.get('files', [])) != doc['file_count']:
            raise ValueError('Comparison does not match this run and full file inventory')
        if comparison['status'] == 'PASS':
            by_path = {r['path']: r for r in comparison['files']}
            if len(by_path) != doc['file_count'] or any(by_path.get(r['path'], {}).get('actual') != {'size': r['size'], 'sha256': r['sha256']} for r in doc['files']):
                raise ValueError('PASS comparison lacks exact source/destination byte evidence')
            if {r['path'] for r in comparison.get('empty_directories', []) if r['status'] == 'PASS'} != set(doc['empty_directories']):
                raise ValueError('PASS comparison lacks empty-directory evidence')
        result['file_integrity'] = comparison['status']
        if comparison['status'] == 'FAIL':
            result['status'] = 'FAIL'
    if comparison and comparison['status'] == 'PASS' and 'timing' in result:
        seconds = result['timing']['elapsed_seconds']
        result['measured_operator_interval_rate'] = {'MB_per_second_decimal': doc['total_bytes'] / seconds / 1e6,
                'Mbps_decimal': doc['total_bytes'] * 8 / seconds / 1e6,
                'scope': 'Manual end-to-end interval on the operator-declared network; not physical Wi-Fi benchmark certification'}
    write_json(root / 'report.json', result)
    # Export only tool-owned allowlisted reports; never dump environment/raw logs.
    inventory = []
    for name in [MARKER, 'source-manifest.json', 'comparison.json', 'android-source-comparison.json', 'timing-start.json', 'timing-stop.json', 'environment.json', 'network-environment.json', 'report.json']:
        path = root / name
        if path.exists():
            inventory.append({'path': name, **file_hash(path)})
    write_json(root / 'evidence-manifest.json', {'run_id': doc['run_id'], 'files': inventory})
    no_links(root / 'SHA256SUMS.txt').write_text(''.join(x['sha256'] + '  ' + x['path'] + '\n' for x in inventory)
                                      + file_hash(root / 'evidence-manifest.json')['sha256'] + '  evidence-manifest.json\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='A dedicated synthetic test workspace; prepare requires a new folder')
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare'); create.add_argument('--profile', choices=PROFILES, default='smoke'); create.add_argument('--allow-large', action='store_true')
    commands.add_parser('environment'); commands.add_parser('hash-source')
    timing = commands.add_parser('start'); timing.add_argument('--direction', choices=DIRECTIONS, required=True)
    timing.add_argument('--mode', choices=['blackbox-production-1.13.0', 'test-artifact'], required=True)
    timing.add_argument('--network', choices=['physical-wifi', 'physical-ethernet-wifi', 'isolated-virtual'], required=True)
    timing.add_argument('--artifact', type=Path)
    commands.add_parser('stop')
    compare_parser = commands.add_parser('compare'); compare_parser.add_argument('--received-dir', type=Path, required=True); compare_parser.add_argument('--name-map', type=Path)
    adb = commands.add_parser('adb-hash'); adb.add_argument('--adb', type=Path, required=True); adb.add_argument('--serial', required=True); adb.add_argument('--remote-dir', required=True); adb.add_argument('--purpose', choices=['source', 'destination'], default='destination')
    commands.add_parser('report')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            out = prepare(args.root, args.profile, args.allow_large)
        elif args.command == 'environment':
            root, _ = workspace(args.root); out = environment(root); write_json(root / 'environment.json', out)
        elif args.command == 'hash-source':
            root, doc = manifest(args.root)
            out = {'status': 'PASS' if all(file_hash(beneath(root / doc['payload_folder'], x['path'])) == {'size': x['size'], 'sha256': x['sha256']} for x in doc['files']) else 'FAIL'}
        elif args.command == 'start':
            out = start(args.root, args.direction, args.mode, args.network, args.artifact)
        elif args.command == 'stop':
            out = stop(args.root)
        elif args.command == 'compare':
            out = compare(args.root, args.received_dir, args.name_map)
        elif args.command == 'adb-hash':
            out = adb_hash(args.root, args.adb, args.serial, args.remote_dir, args.purpose)
        else:
            out = report(args.root)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1 if out.get('status') == 'FAIL' else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        # Never print external command stderr, argv, selected personal paths or environment values.
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(error).__name__,
                          'reason': 'Check owned workspace, synthetic manifest, safe paths, free space and explicit tool/device selection.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
