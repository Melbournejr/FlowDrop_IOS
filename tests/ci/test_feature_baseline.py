"""Feature source policy: authorization must remain explicit and byte exact."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import feature_baseline as policy


class FeatureBaselineTests(unittest.TestCase):
    def test_new_source_is_pinned_and_existing_identity_checks_run(self):
        result = policy.verify_feature()
        self.assertEqual(result['feature_version'], '1.14.0')
        self.assertGreater(result['feature_files_checked'], 0)
        self.assertIn('intentionally differs', result['production_source_equivalence'])

    def test_approval_cannot_change_historical_proof_or_accept_unpinned_bytes(self):
        name = 'worker/index.js'
        row = policy.approved()[name]
        with self.assertRaises(RuntimeError):
            policy.expected_sha(name, '0' * 64)
        self.assertEqual(policy.expected_sha('unmodified.fixture', 'original'), 'original')
        with patch.object(policy, 'approved', return_value={name: dict(row, sha256='0' * 64)}):
            with self.assertRaisesRegex(RuntimeError, 'Feature source bytes changed'):
                policy.verify_feature()

    def test_policy_rejects_traversal_ios_signing_and_publisher_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'manifest.json'
            for name in ['../escape', 'ios/App.swift', 'security/key-inventory.json', '.github/workflows/publisher.yml']:
                file.write_text(json.dumps({'schema': 1, 'base': policy.BASE, 'version': '1.14.0',
                                            'files': [{'path': name, 'sha256': '0' * 64}]}))
                policy.approved.cache_clear()
                try:
                    with patch.object(policy, 'MANIFEST', file), self.assertRaises(RuntimeError):
                        policy.approved()
                finally:
                    policy.approved.cache_clear()


if __name__ == '__main__':
    unittest.main()
