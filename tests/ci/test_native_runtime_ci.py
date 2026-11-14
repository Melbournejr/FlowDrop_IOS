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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.native_runtime_ci.common import Blocked, Recorder, child, own_root, sanitize
from scripts.native_runtime_ci.android import instrumentation_result
from scripts.native_runtime_ci.sdk import extract_runtime_zip
from scripts.native_runtime_ci.finish import export


class NativeRuntimeHarnessTests(unittest.TestCase):
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
