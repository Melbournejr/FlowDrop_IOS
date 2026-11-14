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
from scripts.native_runtime_ci.sdk import extract_runtime_zip, host_libraries, official_ubuntu_mirrors, installed_metadata, selected_rows
from scripts.native_runtime_ci.finish import export
from scripts.native_runtime_ci.test_sources import windows_driver


class NativeRuntimeHarnessTests(unittest.TestCase):
    def test_emulator_adb_public_key_is_omitted_from_exported_boot_log(self):
        raw = 'INFO | androidboot.qemu.adb.pubkey=public-fixture-key runner@fixture\nINFO | Boot completed\n'
        result = sanitize(raw)
        self.assertNotIn('public-fixture-key', result)
        self.assertIn('Boot completed', result)

    def test_harness_has_no_unbound_global_helper_names(self):
        import builtins
        import symtable
        def unbound(source, filename):
            tree = symtable.symtable(source, filename, 'exec')
            known = {s.get_name() for s in tree.get_symbols() if s.is_imported() or s.is_assigned() or s.is_namespace()}
            known |= set(dir(builtins)) | {'__name__', '__file__', '__doc__', '__package__'}
            missing = []
            def walk(scope):
                missing.extend(s.get_name() for s in scope.get_symbols()
                               if s.is_global() and s.is_referenced() and s.get_name() not in known)
                for child in scope.get_children():
                    walk(child)
            walk(tree)
            return missing
        self.assertEqual(unbound('def f(): return missing_fixture_helper()', 'fixture.py'), ['missing_fixture_helper'])
        for path in (ROOT / 'scripts/native_runtime_ci').glob('*.py'):
            self.assertEqual(unbound(path.read_text(encoding='utf-8'), str(path)), [], str(path))

    def test_sdk_registration_preserves_pinned_revision_license_and_refuses_overwrite(self):
        import xml.etree.ElementTree as ET
        row = next(row for row in selected_rows(35) if row['id'] == 'emulator')
        with tempfile.TemporaryDirectory() as temp:
            sdk = Path(temp); (sdk / 'emulator').mkdir()
            (sdk / 'emulator/source.properties').write_text('Pkg.Revision=37.2.13\n')
            receipt = installed_metadata(sdk, row)
            package = sdk / 'emulator/package.xml'
            raw = package.read_bytes(); document = ET.fromstring(raw)
            local = document.find('localPackage')
            self.assertEqual(local.get('path'), 'emulator')
            self.assertEqual([local.findtext('revision/' + n) for n in ['major', 'minor', 'micro']], ['37', '2', '13'])
            self.assertIsNone(local.find('archives'))
            self.assertEqual(document.find('license').get('id'), local.find('uses-license').get('ref'))
            self.assertEqual(receipt['official_metadata_sha256'], row['metadata_sha256'])
            with self.assertRaises(FileExistsError):
                installed_metadata(sdk, row)
            self.assertEqual(package.read_bytes(), raw)
            with self.assertRaises(Blocked):
                installed_metadata(sdk, dict(row, metadata_sha256='0' * 64))

    def test_real_dialog_driver_retains_original_assertions_and_fixtures(self):
        import re
        for name in ['windows-native-smoke', 'windows-shell-smoke']:
            original = (ROOT / 'tests' / (name + '.cpp')).read_text(encoding='utf-8')
            compiled = windows_driver(name, original)
            self.assertIn('BM_CLICK', compiled)
            # No original check/wait line or fixture literal may disappear.
            for literal in re.findall(r'"([^"\n]+)"', original):
                self.assertIn(literal, compiled)
            self.assertGreaterEqual(compiled.count('check('), original.count('check('))
            self.assertEqual((ROOT / 'tests' / (name + '.cpp')).read_text(encoding='utf-8'), original)

    def test_dialog_driver_fails_closed_on_source_drift(self):
        with self.assertRaises(Blocked):
            windows_driver('windows-native-smoke', 'unreviewed new test source')
        with self.assertRaises(Blocked):
            windows_driver('other-helper', 'unreviewed test')

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
