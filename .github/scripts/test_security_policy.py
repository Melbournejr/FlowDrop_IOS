import tempfile
import unittest
from pathlib import Path
from audit_workflows import audit_file, audit_workflow

SHA = "a" * 40
SAFE = f"""name: test
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{SHA}
        with:
          persist-credentials: false
      - uses: github/codeql-action/analyze@{SHA}
"""


class SecurityPolicyTests(unittest.TestCase):
    def test_pinned_actions_with_read_token_pass(self):
        self.assertEqual(audit_workflow(SAFE), [])

    def test_moving_tags_and_persisted_tokens_are_rejected(self):
        self.assertTrue(audit_workflow(SAFE.replace(SHA, "v6")))
        self.assertTrue(audit_workflow(SAFE.replace("persist-credentials: false", "persist-credentials: true")))

    def test_privileged_triggers_and_broad_tokens_are_rejected(self):
        self.assertTrue(audit_workflow(SAFE.replace("pull_request:", "pull_request_target:")))
        self.assertTrue(audit_workflow(SAFE.replace("permissions:\n  contents: read", "permissions: write-all")))
        self.assertTrue(audit_workflow(SAFE.replace("contents: read", "contents: write")))

    def test_private_keys_and_tokens_are_rejected_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "credential.txt"
            path.write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----\nnot-a-real-key\n")
            self.assertIn("private key material detected", audit_file(path))
            path.write_text("ghp" + "_" + "A" * 36)
            self.assertIn("GitHub credential pattern detected", audit_file(path))
            path.write_bytes(b"-----BEGIN " + b"PUBLIC KEY-----\npublic-only\n")
            self.assertEqual(audit_file(path), [])
            key = Path(folder) / "signing.jks"
            key.write_text("fixture")
            self.assertIn("credential or signing file must not be tracked", audit_file(key))


if __name__ == "__main__":
    unittest.main()
