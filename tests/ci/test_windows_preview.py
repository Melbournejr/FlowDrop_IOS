"""Windows Preview build isolation; real Windows proof is required in W22."""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

from scripts import windows_preview as preview
from scripts.native_build_ci.paths import owned_root, Blocked
from scripts.native_build_ci.artifacts import check_export, NAMES

REPO = Path(__file__).resolve().parents[2]


class WindowsPreviewTests(unittest.TestCase):
    def test_working_overlay_preserves_original_and_security_code(self):
        protected = ['desktop/windows/FlowDrop.cpp', 'desktop/windows/installer.nsi', 'scripts/secure-update.mjs', 'scripts/dev.mjs']
        before = {name: (REPO / name).read_bytes() for name in protected}
        with tempfile.TemporaryDirectory() as temp:
            # This is a source transformation fixture, not an npm/build test.
            # The toolkit job intentionally runs without npm ci; never depend on
            # a developer checkout's node_modules or change the real builder.
            fixture = Path(temp) / 'source'
            for folder in ['desktop/windows', 'web', 'worker', 'scripts']:
                shutil.copytree(REPO / folder, fixture / folder, ignore=shutil.ignore_patterns('__pycache__'))
            for name in ['package.json', 'package-lock.json', 'INSTALL.md', 'android/AndroidManifest.xml']:
                target = fixture / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / name, target)
            (fixture / 'node_modules').mkdir()
            (fixture / 'node_modules/fixture.txt').write_text('Synthetic overlay fixture; not an npm dependency')
            output, proof = preview.prepare(fixture, owned_root(Path(temp) / 'build'))
            cpp = (output / 'desktop/windows/FlowDrop.cpp').read_text(encoding='utf-8')
            nsi = (output / 'desktop/windows/installer.nsi').read_text(encoding='utf-8')
            self.assertIn('Local\\\\FlowDrop Preview.NativeDesktop.1', cpp)
            self.assertIn('L"FlowDrop Preview.NativeDesktop"', cpp)
            self.assertNotIn('/L"FlowDrop"', cpp)
            self.assertIn('EnableWindow(updateAutoCheck,FALSE)', cpp)
            self.assertIn('$LOCALAPPDATA\\Programs\\FlowDrop Preview', nsi)
            self.assertIn('$SENDTO\\FlowDrop Preview.lnk', nsi)
            self.assertIn('CurrentVersion\\Uninstall\\FlowDropPreview', nsi)
            self.assertIn('IfFileExists "$INSTDIR\\FlowDrop.exe" 0 +3\n SetErrorLevel 2\n Abort', nsi)
            self.assertIn('SetOutPath "$TEMP"\n RMDir /r "$INSTDIR"', nsi)
            self.assertNotIn('"$INSTDIR\\FlowDrop.exe$\\" --shutdown', nsi)
            stop = (output / 'scripts/stop.mjs').read_text(encoding='utf-8')
            self.assertNotIn('process.env.FLOWDROP_DATA_DIR', stop)
            self.assertIn("'FlowDrop Preview','Data'", stop)
            builder = (output / 'scripts/build-installers.py').read_text(encoding='utf-8')
            self.assertIn("TOOLS/'windows-preview-payload'", builder)
            self.assertIn("payload/'FlowDropPreview.exe'", builder)
            for name in ['device-security.mjs', 'device-vault.ps1', 'request-security.mjs', 'release-config.mjs', 'folder-receive.mjs']:
                self.assertEqual((output / 'scripts' / name).read_bytes(), (REPO / 'scripts' / name).read_bytes())
            self.assertEqual((output / 'desktop/windows/FlowDrop.ico').read_bytes(), (REPO / 'desktop/windows/FlowDrop.ico').read_bytes())
            for row in proof['source_overlay']:
                self.assertEqual(hashlib.sha256((output / row['path']).read_bytes()).hexdigest(), row['sha256'])
        for name, body in before.items():
            self.assertEqual((REPO / name).read_bytes(), body)

    def test_preview_updater_never_fetches_or_returns_an_installer(self):
        with tempfile.TemporaryDirectory() as temp:
            module = Path(temp) / 'preview-updater.mjs'
            module.write_text(preview.UPDATER, encoding='utf-8')
            source = '''import assert from 'node:assert/strict';
globalThis.fetch=()=>{throw Error('Preview attempted production network');};
const {DesktopUpdater}=await import(process.argv[1]);
const updater=new DesktopUpdater({enabled:true});await updater.start();
for(const state of [updater.snapshot(),await updater.configure(true),updater.check(true),updater.later(),updater.installFailed()]){
 assert.equal(state.automatic,false);assert.equal(state.canApply,false);assert.equal(state.phase,'disabled');}
assert.throws(()=>updater.accept());await assert.rejects(updater.prepareInstall());updater.resume();updater.close();
'''
            result = subprocess.run(['node', '--input-type=module', '-e', source, module.as_uri()], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_export_rejects_undeclared_preview_and_checks_its_own_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in NAMES['windows'] | {preview.SETUP}:
                (root / name).write_bytes(b'synthetic PE fixture, not a binary')
            manifest = {'status': 'PASS', 'role': 'windows', 'builder_steps': [{'exit_code': 0}]}
            def write():
                (root / 'artifact-manifest.json').write_text(json.dumps(manifest))
                (root / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                    for p in sorted(root.iterdir()) if p.name != 'SHA256SUMS.txt'))
            write()
            with self.assertRaises(Blocked):
                check_export(root, 'windows')
            manifest['windows_preview'] = {'status': 'PASS', 'overlay': {'executable': preview.EXE, 'label': preview.LABEL},
                'windows_installer': {'sha256': hashlib.sha256((root / preview.SETUP).read_bytes()).hexdigest()}}
            write()
            self.assertEqual(check_export(root, 'windows')['windows_preview']['overlay']['executable'], preview.EXE)
            manifest['windows_preview']['windows_installer']['sha256'] = '0' * 64
            write()
            with self.assertRaises(Blocked):
                check_export(root, 'windows')


if __name__ == '__main__':
    unittest.main()
