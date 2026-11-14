"""Build-control regression fixtures; never build/install or use production keys."""
import io
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
import importlib.util
import os
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
import subprocess
import json
import hashlib
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from native_build_ci.paths import Blocked, owned_root, child_path, safe_extract_tar, safe_extract_zip
from native_build_ci.toolchain import fetch
from native_build_ci.verify import apk_identity, certificate_fingerprint, reject_secret_bytes, verify_apk, PRODUCTION_CERT
from native_build_ci.artifacts import check_export
from native_build_ci.runner import Journal, StepFailed
from native_build_ci.finish import prepare_logs
import native_build_support as support
sys.path.pop(0)


class NativePipelineTests(unittest.TestCase):
    def load_builder(self, filename):
        repo = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('fixture_builder', repo / 'scripts' / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_failed_app_build_cannot_leave_previous_apk_as_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, tools = root / 'source', root / 'tools'
            (source / 'artifacts').mkdir(parents=True)
            tools.mkdir()
            for name in ['aapt2', 'zipalign']:
                (tools / name).write_text('fixture, not executed')
            key = root / 'placeholder.fixture'
            key.write_text('not a key')
            old = source / 'artifacts/FlowDrop-1.13.0-Android.apk'
            old.write_text('stale fixture')
            module = self.load_builder('build-installers.py')
            module.ROOT, module.OUT, module.BT = source, source / 'artifacts', tools
            env = {support.KEYSTORE_ENV: str(key), support.STORE_PASSWORD_ENV: 'synthetic-store', support.KEY_PASSWORD_ENV: 'synthetic-key'}
            with patch.dict(os.environ, env, clear=True), patch.object(module, 'run', side_effect=support.BuildError('fixture compile failure')):
                with self.assertRaises(support.BuildError):
                    module.android()
            self.assertFalse(old.exists(), 'A failed build must not retain a previous APK')

    def test_instrumentation_rebuild_discards_old_classes_and_dex(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, tools = root / 'source', root / 'tools'
            (source / 'android/build/classes').mkdir(parents=True)
            old = tools / 'native-instrumentation/classes/Old.class'
            old.parent.mkdir(parents=True)
            old.write_text('old fixture class')
            key = root / 'placeholder.fixture'
            key.write_text('not a key')
            module = self.load_builder('build-native-test-apk.py')
            module.r = source
            env = {support.KEYSTORE_ENV: str(key), support.STORE_PASSWORD_ENV: 'synthetic-store', support.KEY_PASSWORD_ENV: 'synthetic-key', 'FLOWDROP_BUILD_TOOLS': str(tools)}
            with patch.dict(os.environ, env, clear=True), patch.object(sys, 'argv', ['fixture.py']), redirect_stderr(io.StringIO()):
                with patch.object(module, 'run', side_effect=support.BuildError('fixture compile failure')):
                    self.assertEqual(module.main(), 1)
            self.assertFalse(old.exists(), 'Instrumentation cannot reuse stale classes')

    def test_verification_mode_rejects_keystore_outside_test_secret_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = owned_root(Path(temp) / 'work')
            source = root / 'source'
            source.mkdir()
            key = Path(temp) / 'not-production-but-wrong-purpose.fixture'
            key.write_text('not a key')
            env = {support.KEYSTORE_ENV: str(key), support.STORE_PASSWORD_ENV: 'synthetic-store', support.KEY_PASSWORD_ENV: 'synthetic-key', 'FLOWDROP_NATIVE_WORK_ROOT': str(root)}
            with patch.dict(os.environ, env, clear=True), self.assertRaises(support.BuildError):
                support.load_signing(source)

    def test_pinned_java_path_wins_over_untrusted_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = owned_root(Path(temp) / 'work')
            java = root / 'jdk/bin/java'
            java.parent.mkdir(parents=True)
            java.write_text('fixture, not executed')
            env = {'FLOWDROP_NATIVE_WORK_ROOT': str(root), 'FLOWDROP_BUILD_JAVA': str(java), 'PATH': str(root / 'untrusted-bin')}
            with patch.object(support.subprocess, 'run', return_value=subprocess.CompletedProcess(['fixture'], 0, '')) as child:
                with redirect_stdout(io.StringIO()):
                    support.run_command(['java', '-version'], env=env)
            self.assertEqual(child.call_args.args[0][0], str(java))

    def test_tar_hardlinked_compiler_preserves_executable_permissions(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as out:
            entry = tarfile.TarInfo('usr/bin/compiler-real')
            body = b'fixture compiler bytes; not executed'
            entry.size, entry.mode = len(body), 0o755
            out.addfile(entry, io.BytesIO(body))
            link = tarfile.TarInfo('usr/bin/compiler-alias')
            link.type, link.linkname, link.mode = tarfile.LNKTYPE, entry.name, 0o755
            out.addfile(link)
        archive.seek(0)
        with tempfile.TemporaryDirectory() as temp, tarfile.open(fileobj=archive) as source:
            safe_extract_tar(source, Path(temp) / 'tools')
            self.assertEqual(stat.S_IMODE((Path(temp) / 'tools/usr/bin/compiler-alias').stat().st_mode), 0o755)

    def test_owned_cleanup_paths_refuse_outside_and_symlink_destinations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = owned_root(Path(temp) / 'build')
            outside = Path(temp) / 'outside'
            outside.mkdir()
            (root / 'escape').symlink_to(outside)
            for name in [outside, root, root / 'escape/file']:
                with self.assertRaises(Blocked):
                    child_path(root, name)

    def test_compiled_android_metadata_supports_sdk35_and_legacy_badging(self):
        for field in ['minSdkVersion', 'sdkVersion']:
            result = apk_identity("package: name='app.flowdrop.mobile' versionCode='14' versionName='1.13.0'\n" + field + ":'29'\ntargetSdkVersion:'35'\n")
            self.assertEqual((result['package'], result['version_code'], result['version_name'], result['min_sdk'], result['target_sdk']),
                             ('app.flowdrop.mobile', '14', '1.13.0', 29, 35))
        with self.assertRaises(Blocked):
            apk_identity("package: name='app.flowdrop.mobile' versionCode='14' versionName='1.13.0'")

    def test_production_certificate_and_multiple_signers_are_rejected(self):
        with self.assertRaises(Blocked):
            verify_apk('not-opened.apk', '.', '.', None, PRODUCTION_CERT)
        with self.assertRaises(Blocked):
            certificate_fingerprint('Signer #1 certificate SHA-256 digest: ' + 'a' * 64 + '\nSigner #2 certificate SHA-256 digest: ' + 'b' * 64)

    def test_zip_traversal_and_symlink_are_rejected_before_extracting_any_file(self):
        for dangerous in ['../outside', '/outside', 'link']:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / 'fixture.zip'
                with zipfile.ZipFile(archive, 'w') as out:
                    out.writestr('safe.txt', 'must not be extracted')
                    entry = zipfile.ZipInfo(dangerous)
                    if dangerous == 'link':
                        entry.create_system, entry.external_attr = 3, (stat.S_IFLNK | 0o777) << 16
                    out.writestr(entry, '../outside')
                with self.assertRaises(Blocked):
                    safe_extract_zip(archive, root / 'tools')
                self.assertFalse((root / 'tools/safe.txt').exists())

    def test_tar_absolute_symlink_escape_is_rejected_before_writing(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as out:
            link = tarfile.TarInfo('usr/bin/link')
            link.type, link.linkname = tarfile.SYMTYPE, '/etc/passwd'
            out.addfile(link)
        archive.seek(0)
        with tempfile.TemporaryDirectory() as temp, tarfile.open(fileobj=archive) as source:
            with self.assertRaises(Blocked):
                safe_extract_tar(source, Path(temp) / 'tools', debian=True)

    def test_wrong_download_checksum_fails_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            (cache / 'fixture.zip').write_bytes(b'bad checksum fixture')
            row = {'id': 'fixture', 'filename': 'fixture.zip', 'size': 20, 'sha256': '0' * 64, 'url': 'https://example.invalid/fixture.zip'}
            with patch('native_build_ci.toolchain.subprocess.run') as child, self.assertRaises(Blocked):
                fetch(row, cache)
            child.assert_not_called()

    def test_artifact_extra_keystore_and_tampered_checksum_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {'FlowDrop-1.13.0-Android-TEST-ONLY.apk': b'unit fixture only',
                     'FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk': b'unit fixture only',
                     'artifact-manifest.json': json.dumps({'status': 'PASS', 'role': 'android', 'builder_steps': [{'exit_code': 0}]}).encode()}
            for name, data in files.items():
                (root / name).write_bytes(data)
            sums = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in files.items())
            (root / 'SHA256SUMS.txt').write_text(sums)
            self.assertEqual(check_export(root, 'android')['role'], 'android')  # Checksum fixture; not an APK verification claim.
            extra = root / 'forbidden.jks'
            extra.write_bytes(b'not a real keystore')
            with self.assertRaises(Blocked):
                check_export(root, 'android')
            extra.unlink()
            (root / 'FlowDrop-1.13.0-Android-TEST-ONLY.apk').write_text('tampered fixture')
            with self.assertRaises(Blocked):
                check_export(root, 'android')

    def test_private_key_marker_and_exact_temporary_password_are_never_exported(self):
        for body in [b'-----BEGIN PRIVATE KEY-----fixture', b'fixture-specific-password']:
            with self.assertRaises(Blocked):
                reject_secret_bytes(body, ['fixture-specific-password'])

    def test_build_journal_retains_actual_failed_child_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = owned_root(Path(temp) / 'work')
            journal = Journal(root, dict(os.environ))
            with redirect_stdout(io.StringIO()), self.assertRaises(StepFailed):
                journal.run('real-child-failure', [sys.executable, '-c', 'raise SystemExit(7)'])
            record = json.loads((root / 'logs/commands.json').read_text())[0]
            self.assertEqual(record['exit_code'], 7)
            self.assertEqual(record['status'], 'FAIL')

    def test_failed_log_screening_cannot_leave_a_publishable_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = owned_root(Path(temp) / 'work')
            (root / 'logs').mkdir()
            # Deliberately synthetic token syntax; no real credential is used.
            (root / 'logs/rejected.log').write_text('ghp_' + '0' * 36)
            with self.assertRaises(Blocked):
                prepare_logs(root)
            self.assertFalse((root / 'safe-logs').exists(), 'Rejected evidence must not be available to artifact upload')


if __name__ == '__main__':
    unittest.main()
