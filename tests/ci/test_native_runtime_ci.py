"""Unit fixtures for runtime safety/control; never claimed as Windows/Android OS results."""
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.native_runtime_ci.common import Blocked, Recorder, child, own_root, sanitize
from scripts.native_runtime_ci.android import instrumentation_result
from scripts.native_runtime_ci.sdk import extract_runtime_zip, host_libraries, official_ubuntu_mirrors
from scripts.native_runtime_ci.finish import export


class NativeRuntimeHarnessTests(unittest.TestCase):
    def test_regional_official_mirrors_and_lookalike_rejection(self):
        valid = 'http://us-east-2.ec2.archive.ubuntu.com/ubuntu/\nhttp://azure.archive.ubuntu.com/ubuntu/\n'
        self.assertEqual(len(official_ubuntu_mirrors(valid)), 2)
        for value in ['https://archive.ubuntu.com.invalid/ubuntu', 'https://untrusted.example/ubuntu',
                      'https://archive.ubuntu.com/other', 'http://user:password@archive.ubuntu.com/ubuntu', '']:
            with self.assertRaises(Blocked):
                official_ubuntu_mirrors(value)

    def test_missing_unreviewed_host_library_cannot_install_packages(self):
        recorder = Mock()
        recorder.run.return_value = ('  lib-unreviewed.so.0 => not found\n', 0)
        with self.assertRaises(Blocked):
            host_libraries(Path('/fixture/emulator/emulator'), recorder, {})
        self.assertEqual(recorder.run.call_count, 1)

    def test_host_library_install_pins_observed_official_candidate(self):
        recorder = Mock()
        recorder.run.side_effect = [
            (' libpulse.so.0 => not found\n', 0), ('index authenticated', 0),
            (' Candidate: 1:16.1+dfsg1-2ubuntu10\n http://azure.archive.ubuntu.com/ubuntu noble/main amd64 Packages\n', 0),
            ('installed', 0), ('libpulse0 1:16.1+dfsg1-2ubuntu10 amd64', 0),
            (' libpulse.so.0 => /lib/x86_64-linux-gnu/libpulse.so.0\n', 0)]
        with patch('scripts.native_runtime_ci.sdk.Path.read_text', return_value='ID=ubuntu\nVERSION_ID="24.04"\n'):
            host_libraries(Path('/fixture/emulator/emulator'), recorder, {})
        command = recorder.run.call_args_list[3].args[1]
        self.assertIn('libpulse0=1:16.1+dfsg1-2ubuntu10', command)
        self.assertNotIn('--allow-unauthenticated', command)
        self.assertEqual(recorder.run.call_args_list[0].kwargs['env']['LD_LIBRARY_PATH'],
                         '/fixture/emulator/lib64' + os.pathsep + '/fixture/emulator/lib64/qt/lib')
        self.assertNotIn('LD_LIBRARY_PATH', recorder.run.call_args_list[3].kwargs['env'])

    def test_am_instrument_zero_process_exit_is_not_a_test_pass(self):
        for output, code in [('INSTRUMENTATION_CODE: 0', 0), ('INSTRUMENTATION_FAILED: process crashed', 0),
                             ('INSTRUMENTATION_RESULT: result={"passed":true}\nINSTRUMENTATION_CODE: -1', 7)]:
            with self.assertRaises(AssertionError):
                instrumentation_result(output, code)
        result = instrumentation_result('INSTRUMENTATION_RESULT: result={"passed":true,"sdk":35}\nINSTRUMENTATION_CODE: -1', 0)
        self.assertEqual(result['sdk'], 35)

    def test_failed_or_missing_case_cannot_become_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            source = {'reviewed_head': 'fixture-head', 'checkout': 'fixture-checkout'}
            rec = Recorder(Path(temp) / 'owned', 'unit-fixture', source)
            with rec.case('case-a', 'Deliberate fixture assertion must fail'):
                raise AssertionError('expected fixture failure')
            self.assertEqual(rec.finish(['case-a', 'case-b']), 1)
            self.assertEqual([row['status'] for row in rec.cases], ['FAIL', 'NOT VERIFIED'])

    def test_blocked_environment_is_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            rec = Recorder(Path(temp) / 'owned', 'unit-fixture', {'reviewed_head': 'head', 'checkout': 'checkout'})
            with rec.case('no-os', 'Require actual OS'):
                raise Blocked('No actual OS')
            self.assertEqual(rec.finish(['no-os']), 1)
            self.assertEqual(rec.cases[0]['status'], 'BLOCKED')

    def test_redaction_keeps_exit_codes_and_sha_evidence(self):
        data = '{"token":"synthetic-secret","code":"ABCDEFGH","exit_code":7,"sha256":"public-hash"}'
        value = json.loads(sanitize(data))
        self.assertEqual(value['exit_code'], 7)
        self.assertEqual(value['sha256'], 'public-hash')
        self.assertEqual(value['token'], '[REDACTED]')
        self.assertEqual(value['code'], '[REDACTED]')

    def test_cleanup_refuses_outside_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = own_root(Path(temp) / 'owned')
            outside = Path(temp) / 'unowned'; outside.mkdir()
            (root / 'link').symlink_to(outside)
            for path in [root, outside, root / 'link/file']:
                with self.assertRaises(Blocked):
                    child(root, path)

    def test_archive_traversal_or_link_prevents_all_extraction(self):
        for name in ['../outside', '/outside', 'link']:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / 'fixture.zip'
                with zipfile.ZipFile(archive, 'w') as output:
                    output.writestr('safe.txt', 'must not be written')
                    member = zipfile.ZipInfo(name)
                    if name == 'link':
                        member.create_system, member.external_attr = 3, (stat.S_IFLNK | 0o777) << 16
                    output.writestr(member, 'outside')
                with self.assertRaises(Exception):
                    extract_runtime_zip(archive, root / 'extract')
                self.assertFalse((root / 'extract/safe.txt').exists())

    def test_unreviewed_evidence_file_cannot_publish_partial_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = own_root(Path(temp) / 'owned')
            (root / 'logs').mkdir()
            (root / 'logs/state.jks').write_text('not an actual key')
            with self.assertRaises(Blocked):
                export(root)
            self.assertFalse((root / 'evidence-export').exists())

    def test_screened_export_manifest_matches_actual_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = own_root(Path(temp) / 'owned')
            (root / 'logs').mkdir()
            (root / 'logs/result.json').write_text('{"exit_code":0,"token":"synthetic-fixture"}')
            export(root)
            manifest = json.loads((root / 'evidence-export/evidence-manifest.json').read_text())
            self.assertEqual(manifest['files'][0]['path'], 'result.json')
            self.assertNotIn('synthetic-fixture', (root / 'evidence-export/result.json').read_text())
            self.assertEqual(json.loads((root / 'evidence-export/result.json').read_text())['exit_code'], 0)


if __name__ == '__main__':
    unittest.main()
