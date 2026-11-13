"""Build control tests only: fake credentials/processes, no SDK build or key use."""
import ast
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import native_build_support as support
sys.path.pop(0)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), REPO / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeBuildSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='flowdrop-build-control-')
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        self.placeholder = self.root / 'not-a-real-keystore.fixture'
        self.placeholder.write_text('opaque fixture; not a key or keystore')
        self.env = {
            support.KEYSTORE_ENV: str(self.placeholder),
            support.STORE_PASSWORD_ENV: 'synthetic-store-password',
            support.KEY_PASSWORD_ENV: 'synthetic-key-password',
            'FLOWDROP_BUILD_TOOLS': str(self.root),
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_signing_uses_environment_references_and_preserves_public_alias(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('must not read key data')):
            config = support.load_signing(self.repo, self.env)
        argv = config.arguments()
        self.assertEqual(argv[argv.index('--ks-key-alias') + 1], 'flowdrop')
        self.assertEqual(argv[argv.index('--ks-pass') + 1], 'env:' + support.STORE_PASSWORD_ENV)
        self.assertEqual(argv[argv.index('--key-pass') + 1], 'env:' + support.KEY_PASSWORD_ENV)
        for name in [support.STORE_PASSWORD_ENV, support.KEY_PASSWORD_ENV]:
            self.assertNotIn(self.env[name], repr(argv) + repr(config))

    def test_missing_credentials_fail_without_printing_other_secret_values(self):
        for name in support.SIGNING_ENV:
            with self.subTest(name=name):
                env = {k: v for k, v in self.env.items() if k != name}
                with self.assertRaises(support.BuildError) as error:
                    support.load_signing(self.repo, env)
                self.assertIn(name, str(error.exception))
                self.assertNotIn(self.env[support.STORE_PASSWORD_ENV], str(error.exception))

    def test_empty_or_multiline_passwords_fail_closed(self):
        for value in ['', 'synthetic\nvalue', 'synthetic\x00value']:
            with self.subTest(value_length=len(value)), self.assertRaises(support.BuildError):
                support.load_signing(self.repo, dict(self.env, **{support.STORE_PASSWORD_ENV: value}))

    def test_no_relative_in_checkout_missing_or_symlink_keystores(self):
        inside = self.repo / 'placeholder.fixture'
        inside.write_text('not a keystore')
        link = self.root / 'link.fixture'
        link.symlink_to(self.placeholder)
        for value in ['relative.fixture', str(inside), str(link), str(self.root / 'missing'), str(self.root)]:
            with self.subTest(case=Path(value).name), self.assertRaises(support.BuildError):
                support.load_signing(self.repo, dict(self.env, **{support.KEYSTORE_ENV: value}))

    def test_tool_root_requires_explicit_existing_absolute_path(self):
        for value in ['', 'relative', str(self.root / 'missing')]:
            with self.assertRaises(support.BuildError):
                support.require_tool_root({'FLOWDROP_BUILD_TOOLS': value})
        self.assertEqual(support.require_tool_root(self.env), self.root)

    def test_subprocess_failure_output_is_redacted_and_exit_retained(self):
        output = ' '.join(self.env[name] for name in support.SIGNING_ENV)
        stream = io.StringIO()
        with patch.object(support.subprocess, 'run', return_value=subprocess.CompletedProcess(['fake-tool'], 7, output)) as child:
            with redirect_stdout(stream), self.assertRaisesRegex(support.BuildError, 'exit code 7'):
                support.run_command(['fake-tool', '--public-argument'], signing=True, env=self.env)
        for name in support.SIGNING_ENV:
            self.assertNotIn(self.env[name], stream.getvalue())
        self.assertIn('[REDACTED]', stream.getvalue())
        self.assertFalse(child.call_args.kwargs['check'])
        self.assertEqual(child.call_args.kwargs['stdout'], subprocess.PIPE)
        self.assertEqual(child.call_args.kwargs['stderr'], subprocess.STDOUT)

    def test_only_signing_child_receives_credentials_without_mutating_parent_env(self):
        with patch.object(support.subprocess, 'run', return_value=subprocess.CompletedProcess(['fixture'], 0, '')) as child:
            with redirect_stdout(io.StringIO()):
                support.run_command(['fixture'], env=self.env)
                unsigned_env = child.call_args.kwargs['env']
                support.run_command(['fixture'], signing=True, env=self.env)
                signed_env = child.call_args.kwargs['env']
        for name in support.SIGNING_ENV:
            self.assertNotIn(name, unsigned_env)
            self.assertEqual(signed_env[name], self.env[name])
            self.assertIn(name, self.env)

    def test_inline_password_is_rejected_before_process_start(self):
        with patch.object(support.subprocess, 'run') as child:
            with self.assertRaisesRegex(support.BuildError, 'Inline signing passwords'):
                support.run_command(['fixture', '--ks-pass', 'pass:' + 'synthetic-fixture-value'])
        child.assert_not_called()

    def test_timeout_and_spawn_errors_do_not_echo_raw_commands_or_output(self):
        secret = self.env[support.STORE_PASSWORD_ENV]
        failures = [subprocess.TimeoutExpired(['fixture', secret], 1, output=secret), OSError(secret)]
        for failure in failures:
            stream = io.StringIO()
            with patch.object(support.subprocess, 'run', side_effect=failure), redirect_stdout(stream):
                with self.assertRaises(support.BuildError) as error:
                    support.run_command(['fixture'], signing=True, env=self.env)
            self.assertNotIn(secret, str(error.exception) + stream.getvalue())

    def test_importing_both_build_scripts_has_no_build_or_signing_side_effect(self):
        with patch.object(support.subprocess, 'run') as child, patch.object(Path, 'mkdir') as mkdir:
            load_script('build-installers')
            load_script('build-native-test-apk')
        child.assert_not_called()
        mkdir.assert_not_called()

    def test_missing_signing_env_is_rejected_before_app_build_directory_cleanup(self):
        module = load_script('build-installers')
        with patch.dict(os.environ, {}, clear=True), patch.object(module.shutil, 'rmtree') as cleanup:
            with self.assertRaises(support.BuildError):
                module.android()
        cleanup.assert_not_called()

    def test_windows_only_selection_needs_no_android_signing_credentials(self):
        module = load_script('build-installers')
        with patch.dict(os.environ, {'FLOWDROP_BUILD_TOOLS': str(self.root)}, clear=True):
            with patch.object(sys, 'argv', ['build-installers.py', '--only', 'windows']):
                with patch.object(module, 'windows') as windows, patch.object(module, 'android') as android:
                    self.assertEqual(module.main(), 0)
        windows.assert_called_once_with()
        android.assert_not_called()

    def test_instrumentation_missing_env_fails_before_any_build_process(self):
        module = load_script('build-native-test-apk')
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'argv', ['build-native-test-apk.py']):
            with patch.object(support.subprocess, 'run') as child, redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 1)
        child.assert_not_called()

    def test_only_apksigner_sign_calls_opt_in_to_signing_environment(self):
        selected = []
        for name in ['build-installers.py', 'build-native-test-apk.py']:
            tree = ast.parse((REPO / 'scripts' / name).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'run':
                    if any(k.arg == 'signing' and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
                        selected.append(name)
                        args = ast.unparse(node.args[0])
                        self.assertIn('apksigner.jar', args)
                        self.assertIn("'sign'", args)
        self.assertCountEqual(selected, ['build-installers.py', 'build-native-test-apk.py'])

    def test_original_icon_sha256_is_preserved(self):
        self.assertEqual(hashlib.sha256((REPO / 'desktop/windows/FlowDrop.ico').read_bytes()).hexdigest(),
                         'cce4d31a79b6350c73daa884e9493d6ebc70746ac8e7471c924e0ad1b767650e')


if __name__ == '__main__':
    unittest.main()
