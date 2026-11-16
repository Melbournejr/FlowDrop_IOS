"""Safety and honesty checks for the black-box tool, not native LAN proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib

FILE = Path(__file__).resolve().parents[2] / 'tools/physical-lan/flowdrop_lan.py'
spec = importlib.util.spec_from_file_location('flowdrop_lan_tool', FILE)
lan = importlib.util.module_from_spec(spec); spec.loader.exec_module(lan)


class PhysicalLanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'synthetic'

    def create(self):
        return lan.prepare(self.root, free_bytes=2**40)

    def test_generated_files_are_real_exact_size_and_independently_hashed(self):
        doc = self.create()
        self.assertEqual(doc['file_count'], 110)
        for row in doc['files']:
            data = (self.root / doc['payload_folder'] / row['path']).read_bytes()
            self.assertEqual(row['size'], len(data))
            self.assertEqual(row['sha256'], hashlib.sha256(data).hexdigest())
        for directory in doc['empty_directories']:
            self.assertEqual(list((self.root / doc['payload_folder'] / directory).iterdir()), [])
        self.assertEqual(doc['transport_status'], 'NOT VERIFIED')

    def test_png_has_valid_chunks_crc_and_two_rows(self):
        data = lan.png(); pos = 8; image = b''
        while pos < len(data):
            size = struct.unpack('>I', data[pos:pos+4])[0]; kind = data[pos+4:pos+8]
            body = data[pos+8:pos+8+size]; crc = struct.unpack('>I', data[pos+8+size:pos+12+size])[0]
            self.assertEqual(zlib.crc32(kind + body), crc)
            if kind == b'IDAT':
                image += body
            pos += 12 + size
        self.assertEqual(len(zlib.decompress(image)), 14)
        self.assertTrue(lan.avi().startswith(b'RIFF'))
        self.assertIn(b'AVI ', lan.avi())
        self.assertIn(b'startxref', lan.pdf())

    def test_existing_directory_is_never_overwritten(self):
        self.root.mkdir(); marker = self.root / 'personal.txt'; marker.write_text('keep')
        with self.assertRaises(ValueError):
            self.create()
        self.assertEqual(marker.read_text(), 'keep')

    def test_large_profiles_need_explicit_opt_in_and_disk_guard(self):
        with self.assertRaises(ValueError):
            lan.prepare(self.root, 'zip64', free_bytes=2**40)
        with self.assertRaises(ValueError):
            lan.prepare(self.root, 'zip64', True, free_bytes=1024)
        self.assertFalse(self.root.exists())
        self.assertGreater(lan.PROFILES['zip64'], 2**32)

    def test_traversal_absolute_drive_and_reserved_names_rejected(self):
        for name in ['../personal', '/root', 'a//b', 'a/./b', 'C:/secret', 'a\\b', 'a/NUL.txt', 'Con', 'a/COM1.bin', 'trail.']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                lan.safe_relative(name)
        self.assertEqual(str(lan.safe_relative('Tiếng Việt/中文 😀.txt')), 'Tiếng Việt/中文 😀.txt')

    def test_compare_reads_only_manifest_paths_in_selected_folder(self):
        doc = self.create(); destination = self.parent / 'received'
        shutil.copytree(self.root / doc['payload_folder'], destination)
        personal = destination / 'not-a-test.txt'; personal.write_text('never scan or export')
        result = lan.compare(self.root, destination)
        self.assertEqual(result['status'], 'PASS')
        self.assertNotIn('not-a-test', json.dumps(result))
        self.assertEqual(personal.read_text(), 'never scan or export')

    def test_missing_truncated_and_changed_destination_fail(self):
        doc = self.create(); destination = self.parent / 'received'
        shutil.copytree(self.root / doc['payload_folder'], destination)
        first = destination / doc['files'][1]['path']; first.write_bytes(b'wrong')
        self.assertEqual(lan.compare(self.root, destination)['status'], 'FAIL')
        first.unlink()
        self.assertEqual(lan.compare(self.root, destination)['status'], 'FAIL')

    def test_missing_empty_directory_fails(self):
        doc = self.create(); destination = self.parent / 'received'
        shutil.copytree(self.root / doc['payload_folder'], destination)
        (destination / doc['empty_directories'][0]).rmdir()
        self.assertEqual(lan.compare(self.root, destination)['status'], 'FAIL')

    def test_name_map_may_not_merge_files_or_escape(self):
        doc = self.create(); mapping = self.parent / 'names.json'
        mapping.write_text(json.dumps({doc['files'][0]['path']: '../personal'}))
        with self.assertRaises(ValueError):
            lan.compare(self.root, self.root / doc['payload_folder'], mapping)
        mapping.write_text(json.dumps({doc['files'][0]['path']: doc['files'][1]['path']}))
        with self.assertRaises(ValueError):
            lan.compare(self.root, self.root / doc['payload_folder'], mapping)

    def test_new_report_never_claims_native_or_physical_pass(self):
        self.create(); result = lan.report(self.root)
        self.assertEqual(result['status'], 'NOT VERIFIED')
        self.assertEqual(result['native_e2e'], 'NOT VERIFIED')
        self.assertEqual(result['physical_wifi'], 'NOT VERIFIED')

    def test_hash_match_and_timing_are_not_physical_lan_proof(self):
        doc = self.create(); lan.start(self.root, 'Windows-to-Android', 'blackbox-production-1.13.0', 'physical-wifi')
        lan.stop(self.root); lan.compare(self.root, self.root / doc['payload_folder'])
        result = lan.report(self.root)
        self.assertEqual(result['file_integrity'], 'PASS')
        self.assertEqual(result['status'], 'NOT VERIFIED')
        self.assertEqual(result['physical_wifi'], 'NOT VERIFIED')
        self.assertGreater(result['measured_operator_interval_rate']['Mbps_decimal'], 0)
        self.assertAlmostEqual(result['measured_operator_interval_rate']['Mbps_decimal'], result['measured_operator_interval_rate']['MB_per_second_decimal'] * 8)

    def test_source_changes_cannot_start_timing(self):
        doc = self.create(); (self.root / doc['payload_folder'] / doc['files'][1]['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            lan.start(self.root, 'Windows-to-Windows', 'test-artifact', 'isolated-virtual')
        self.assertFalse((self.root / 'timing-start.json').exists())

    def test_manifest_cannot_change_after_start(self):
        self.create(); lan.start(self.root, 'Windows-to-Windows', 'test-artifact', 'isolated-virtual')
        path = self.root / 'source-manifest.json'; doc = lan.read_json(path); doc['profile'] = 'changed'; lan.write_json(path, doc)
        with self.assertRaises(ValueError):
            lan.report(self.root)

    def test_timing_cannot_be_silently_restarted_or_stopped_twice(self):
        self.create(); lan.start(self.root, 'Android-to-Windows', 'blackbox-production-1.13.0', 'physical-wifi')
        with self.assertRaises(ValueError):
            lan.start(self.root, 'Android-to-Windows', 'blackbox-production-1.13.0', 'physical-wifi')
        lan.stop(self.root)
        with self.assertRaises(ValueError):
            lan.stop(self.root)

    def test_adb_rejects_personal_directory_and_bad_serial_before_execution(self):
        self.create()
        with patch.object(lan.subprocess, 'run') as child:
            for serial, remote in [('serial;bad', '/sdcard/Download/FlowDrop'), ('safe', '/sdcard/DCIM/Camera')]:
                with self.assertRaises(ValueError):
                    lan.adb_hash(self.root, FILE, serial, remote)
            child.assert_not_called()

    def test_evidence_checksum_inventory_matches_only_allowed_reports(self):
        self.create(); (self.root / 'private-token.log').write_text('do not collect')
        lan.report(self.root)
        records = lan.read_json(self.root / 'evidence-manifest.json')['files']
        self.assertNotIn('private-token.log', {r['path'] for r in records})
        for row in records:
            self.assertEqual(row['sha256'], hashlib.sha256((self.root / row['path']).read_bytes()).hexdigest())

    def test_manifest_path_tampering_is_rejected(self):
        self.create(); file = self.root / 'source-manifest.json'; doc = lan.read_json(file)
        doc['files'][0]['path'] = '../personal.txt'; lan.write_json(file, doc)
        with self.assertRaises(ValueError):
            lan.manifest(self.root)

    def test_linked_parent_is_rejected_on_real_filesystem(self):
        target = self.parent / 'personal'; target.mkdir(); (target / 'keep.txt').write_text('keep')
        link = self.parent / 'link'
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True)
        else:
            link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            lan.prepare(link / 'test-child')
        self.assertEqual((target / 'keep.txt').read_text(), 'keep')
        self.assertFalse((target / 'test-child').exists())

    def test_copied_timing_cannot_use_another_computer_clock(self):
        self.create(); lan.start(self.root, 'Windows-to-Windows', 'test-artifact', 'isolated-virtual')
        with patch.object(lan.platform, 'node', return_value='a-different-test-computer'):
            with self.assertRaises(ValueError):
                lan.stop(self.root)

    def test_incomplete_fake_pass_comparison_cannot_enter_report(self):
        doc = self.create()
        lan.write_json(self.root / 'comparison.json', {'run_id': doc['run_id'], 'status': 'PASS', 'files': []})
        with self.assertRaises(ValueError):
            lan.report(self.root)

    def test_high_resolution_timing_survives_an_unchanged_coarse_monotonic_tick(self):
        self.create()
        with patch.object(lan.time, 'monotonic_ns', return_value=1000):
            lan.start(self.root, 'Windows-to-Windows', 'test-artifact', 'isolated-virtual')
            result = lan.stop(self.root)
        self.assertGreater(result['elapsed_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
