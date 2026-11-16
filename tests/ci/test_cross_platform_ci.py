"""Process control regressions for the Linux protocol job; not native E2E proof."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.cross_platform_ci.run import protocol_command
from scripts.native_runtime_ci.common import Recorder, clean_env


class CrossPlatformControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.rec = Recorder(Path(self.temp.name) / 'controlled', 'unit-only',
                            {'reviewed_head': 'fixture', 'checkout': 'fixture'})

    def test_actual_nonzero_exit_remains_failed_after_log_collection(self):
        with self.assertRaises(AssertionError):
            protocol_command(self.rec, [sys.executable, '-c', 'print("fixture");raise SystemExit(9)'], clean_env(), timeout=5)
        self.assertEqual(self.rec.commands[-1]['exit_code'], 9)
        self.assertEqual(self.rec.commands[-1]['raw_returncode'], 9)
        self.assertFalse(self.rec.commands[-1]['timeout'])

    def test_timeout_stops_the_owned_descendant_group(self):
        code = 'import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);print(p.pid,flush=True);time.sleep(60)'
        with self.assertRaises(AssertionError):
            protocol_command(self.rec, [sys.executable, '-c', code], clean_env(), timeout=0.3)
        self.assertEqual(self.rec.commands[-1]['exit_code'], 124)
        self.assertTrue(self.rec.commands[-1]['timeout'])
        pid = int((self.rec.root / 'logs/protocol-command.log').read_text().strip())
        for _ in range(50):
            status = Path('/proc') / str(pid) / 'stat'
            if not status.exists() or status.read_text().split(') ', 1)[1].startswith('Z'):
                break
            time.sleep(0.02)
        else:
            self.fail('Owned child remained running after timeout')

    def test_command_and_output_are_screened_for_explicit_ephemeral_secrets(self):
        secret = 'synthetic-unit-capability-2d2'; self.rec.secrets.append(secret)
        protocol_command(self.rec, [sys.executable, '-c', 'import sys; print(sys.argv[1])', secret], clean_env(), timeout=5)
        self.assertNotIn(secret, (self.rec.root / 'logs/protocol-command.log').read_text())
        self.assertNotIn(secret, str(self.rec.commands))
        self.assertEqual(self.rec.commands[-1]['exit_code'], 0)


if __name__ == '__main__':
    unittest.main()
