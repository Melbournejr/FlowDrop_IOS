"""Preview isolation fixtures; OS coexistence is separately required on emulator."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts import android_preview as preview
from scripts.native_build_ci.paths import owned_root, Blocked
from scripts.native_build_ci.artifacts import check_export, NAMES

REPO = Path(__file__).resolve().parents[2]


class PreviewTests(unittest.TestCase):
    def test_overlay_leaves_original_sources_and_signing_pins_unchanged(self):
        paths = list((REPO / 'android').rglob('*.java')) + [REPO / 'android/AndroidManifest.xml']
        original = {p: p.read_bytes() for p in paths}
        with tempfile.TemporaryDirectory() as temp:
            output, proof = preview.prepare(REPO, owned_root(Path(temp) / 'build'))
            manifest = ET.parse(output / 'android/AndroidManifest.xml').getroot()
            self.assertEqual(manifest.get('package'), 'app.flowdrop.preview')
            self.assertEqual(manifest.find('application').get(preview.NS + 'label'), 'FlowDrop Preview')
            self.assertEqual(manifest.get(preview.NS + 'versionName'), '1.14.0')
            self.assertEqual(manifest.get(preview.NS + 'versionCode'), '15')
            original_manifest = ET.fromstring(original[REPO / 'android/AndroidManifest.xml'])
            permissions = {p.get(preview.NS + 'name') for p in manifest.findall('uses-permission')}
            expected = {p.get(preview.NS + 'name') for p in original_manifest.findall('uses-permission')} - preview.REMOVED_PERMISSIONS
            self.assertEqual(permissions, expected)
            components = [p.get(preview.NS + 'name') for p in manifest.find('application')]
            self.assertNotIn('.UpdateJobService', components)
            self.assertNotIn('.UpdateInstallReceiver', components)
            src = output / 'android/src/app/flowdrop/preview'
            for p in src.glob('*.java'):
                self.assertNotIn('app.flowdrop.mobile', p.read_text())
            for name in ['DeviceSecurity.java', 'RequestSecurity.java', 'ReleaseConfig.java', 'TransferServer.java']:
                expected = original[REPO / 'android/src/app/flowdrop/mobile' / name].decode().replace('app.flowdrop.mobile', preview.PACKAGE)
                self.assertEqual((src / name).read_text(), expected)
            for name in ['ReceiveFiles.java', 'FolderReceive.java']:
                text = (src / name).read_text()
                self.assertNotIn('Download/FlowDrop"', text)
                self.assertNotIn('Download/FlowDrop/', text)
                self.assertIn('Download/FlowDrop Preview', text)
            updater = (src / 'AppUpdates.java').read_text()
            for forbidden in ['ReleaseConfig.FEED', 'openConnection', 'PackageInstaller', 'scheduler.schedule', 'PUBLIC_KEY']:
                self.assertNotIn(forbidden, updater)
            for row in proof['source_overlay']:
                self.assertEqual(hashlib.sha256((output / row['path']).read_bytes()).hexdigest(), row['sha256'])
        for p, data in original.items():
            self.assertEqual(p.read_bytes(), data)

    def test_changed_preview_anchor_fails_instead_of_silently_building_wrong_variant(self):
        with self.assertRaises(RuntimeError):
            preview.replace_once('renamed source', 'required anchor', 'replacement')
        with self.assertRaises(RuntimeError):
            preview.replace_once('twice twice', 'twice', 'replacement')

    def test_export_rejects_undeclared_or_misidentified_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in NAMES['android'] | {preview.APK_NAME}:
                (root / name).write_bytes(b'synthetic fixture')
            manifest = {'status': 'PASS', 'role': 'android', 'builder_steps': [{'exit_code': 0}]}
            def write():
                (root / 'artifact-manifest.json').write_text(json.dumps(manifest))
                (root / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                    for p in sorted(root.iterdir()) if p.name != 'SHA256SUMS.txt'))
            write()
            with self.assertRaises(Blocked):
                check_export(root, 'android')
            manifest['preview'] = {'status': 'PASS', 'identity': {'package': 'app.flowdrop.mobile'}, 'overlay': {'label': preview.LABEL}}
            write()
            with self.assertRaises(Blocked):
                check_export(root, 'android')
            manifest['preview']['identity']['package'] = preview.PACKAGE
            manifest['preview']['sha256'] = hashlib.sha256((root / preview.APK_NAME).read_bytes()).hexdigest()
            write()
            self.assertEqual(check_export(root, 'android')['preview']['identity']['package'], preview.PACKAGE)
            (root / preview.APK_NAME).write_bytes(b'tampered')
            with self.assertRaises(Blocked):
                check_export(root, 'android')


if __name__ == '__main__':
    unittest.main()
