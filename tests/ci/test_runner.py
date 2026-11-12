import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('native_ci', Path(__file__).with_name('run.py'))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class NativeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='flowdrop-ci-selftest-')
        self.root = ci.owned_root(Path(self.temporary.name) / 'work')

    def tearDown(self):
        self.temporary.cleanup()

    def execute(self, name, source, timeout=5, env=None):
        return ci.execute(name, [sys.executable, '-c', source], timeout, self.root, dict(os.environ) if env is None else env)

    def test_all_thirteen_existing_commands_are_present_once_without_skip_flags(self):
        entries = [item for group in ci.GROUPS.values() for item in group]
        existing = [name for name, _, _ in entries if name not in ['ci-runner-tests', 'asset-integrity']]
        self.assertEqual(len(existing), 13)
        self.assertEqual(len(set(existing)), 13)
        for _, argv, _ in entries:
            self.assertFalse(any('skip-pattern' in value or 'name-pattern' in value for value in argv))

    def test_real_nonzero_exit_code_is_not_replaced_by_log_collection_success(self):
        result = self.execute('exit-seven', 'print("fixture output"); raise SystemExit(7)')
        self.assertEqual(result['raw_returncode'], 7)
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(result['executed'])

    def test_a_signal_is_not_pass(self):
        result = self.execute('signal', 'import os,signal; os.kill(os.getpid(), signal.SIGTERM)')
        self.assertEqual(result['raw_returncode'], -signal.SIGTERM)
        self.assertEqual(result['exit_code'], 128 + signal.SIGTERM)
        self.assertEqual(result['status'], 'FAIL')

    def test_timeout_kills_the_process_group_and_stays_failed(self):
        result = self.execute('timeout', 'import time; print("started",flush=True); time.sleep(30)', timeout=0.1)
        self.assertTrue(result['timeout'])
        self.assertEqual(result['exit_code'], 124)
        self.assertEqual(result['status'], 'FAIL')

    def test_missing_executable_is_not_verified(self):
        result = ci.execute('missing', [str(self.root / 'no-such-tool')], 1, self.root, dict(os.environ))
        self.assertFalse(result['executed'])
        self.assertEqual(result['status'], 'NOT VERIFIED')
        self.assertEqual(result['exit_code'], 127)

    def test_environment_tokens_and_local_capabilities_are_removed_before_logging(self):
        secret = 'synthetic-environment-fixture-value'
        env = dict(os.environ, FLOWDROP_FIXTURE_TOKEN=secret)
        result = self.execute('redaction', 'import os,json; print(os.environ["FLOWDROP_FIXTURE_TOKEN"]); print(json.dumps({"localToken":"synthetic-local-capability"}))', env=env)
        self.assertEqual(result['exit_code'], 0)
        log = (self.root / 'logs/redaction.log').read_text()
        self.assertNotIn(secret, log)
        self.assertNotIn('synthetic-local-capability', log)
        self.assertIn('[REDACTED', log)

    def test_insufficient_resources_do_not_execute_or_pass_tests(self):
        with patch.object(ci, 'verify_jar'), patch.object(ci, 'resources', return_value={'supported': False}), patch.object(ci, 'execute') as execute:
            result = ci.run_group('zip64', self.root)
        execute.assert_not_called()
        self.assertEqual(result['status'], 'NOT VERIFIED')
        self.assertEqual(result['exit_code'], 78)
        self.assertTrue(all(item['status'] == 'NOT VERIFIED' for item in result['results']))
        self.assertTrue(all(item['exit_code'] is None for item in result['results']))

    def test_group_keeps_first_test_failure_even_when_later_commands_pass(self):
        plan = [('bad', [sys.executable, '-c', 'raise SystemExit(7)'], 5),
                ('good', [sys.executable, '-c', 'print("ok")'], 5)]
        with patch.dict(ci.GROUPS, fixture=plan), patch.object(ci, 'verify_jar'), patch.object(ci, 'resources', return_value={'supported': True}):
            result = ci.run_group('fixture', self.root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual([item['exit_code'] for item in result['results']], [7, 0])
        saved = json.loads((self.root / 'logs/results.json').read_text())
        self.assertEqual(saved['exit_code'], 7)

    def test_wrong_jar_checksum_stops_before_compilation(self):
        jar = self.root / 'tools/fixture.jar'
        jar.write_bytes(b'synthetic wrong jar fixture')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            ci.verify_jar(jar)

    def test_cleanup_refuses_unowned_directory_and_preserves_logs(self):
        outside = Path(self.temporary.name) / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('fixture')
        with self.assertRaises(ValueError):
            ci.cleanup(outside)
        (self.root / 'logs/keep.log').write_text('redacted evidence')
        ci.cleanup(self.root)
        self.assertTrue((outside / 'keep').is_file())
        self.assertTrue((self.root / 'logs/keep.log').is_file())
        self.assertFalse((self.root / 'scratch').exists())

    def test_cleanup_does_not_follow_a_scratch_symlink(self):
        outside = Path(self.temporary.name) / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('fixture')
        (self.root / 'scratch').rmdir()
        (self.root / 'scratch').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            ci.cleanup(self.root)
        self.assertTrue((outside / 'keep').is_file())


if __name__ == '__main__':
    unittest.main()
