"""Native Windows installation/process/backend/Explorer smoke on an isolated hosted VM."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from scripts.native_build_ci.verify import pe_info
from .common import Blocked, Recorder, REPO, clean_env, json_file, own_root, protected_source, sha256, verify_export
from .definitions import WINDOWS
from .http_probe import LiveHTTP


def wait(predicate, message, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            value = predicate()
            if value:
                return value
        except (OSError, ValueError, KeyError, ConnectionError):
            pass
        time.sleep(.2)
    raise AssertionError(message)


def dialog_evidence(stop, destination, secrets):
    """Observe actual OS file-dialog controls without operating them or changing assertions."""
    from ctypes import wintypes
    from .common import sanitize
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetDlgCtrlID.argtypes = [wintypes.HWND]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                       wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    def text(hwnd, classname=False):
        buffer = ctypes.create_unicode_buffer(1024)
        (user.GetClassNameW if classname else user.GetWindowTextW)(hwnd, buffer, len(buffer))
        return buffer.value
    history, previous = [], None
    try:
        while not stop.is_set():
            dialogs = []
            def window(hwnd, parameter):
                title = text(hwnd)
                if title not in ['Chọn file để gửi', 'Chọn thư mục để gửi', 'Đổi tên thiết bị']:
                    return True
                controls = []
                def child_window(child, unused):
                    if len(controls) >= 80:
                        return False
                    kind = text(child, True)
                    if not user.IsWindowVisible(child):
                        return True
                    value = text(child)
                    if kind in ['Edit', 'ComboBox']:
                        buffer, result = ctypes.create_unicode_buffer(2048), ctypes.c_size_t()
                        user.SendMessageTimeoutW(child, 13, len(buffer), ctypes.addressof(buffer), 2, 200, ctypes.byref(result))
                        value = buffer.value
                    rect = wintypes.RECT(); user.GetWindowRect(child, ctypes.byref(rect))
                    controls.append({'class': kind, 'id': user.GetDlgCtrlID(child), 'text': sanitize(value, secrets),
                                     'rect': [rect.left, rect.top, rect.right, rect.bottom]})
                    return True
                user.EnumChildWindows(hwnd, callback_type(child_window), 0)
                dialogs.append({'title': title, 'controls': controls})
                return True
            user.EnumWindows(callback_type(window), 0)
            if dialogs != previous and len(history) < 50:
                history.append({'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'dialogs': dialogs})
                json_file(destination, {'scope': 'Actual Windows file-dialog diagnostics; no UI operations', 'observations': history})
                previous = dialogs
            stop.wait(.5)
    except Exception as error:
        json_file(destination, {'scope': 'Dialog diagnostics failed; does not change test outcome', 'error': sanitize(error, secrets)})


def run(root, downloads, helpers):
    source = protected_source()
    rec = Recorder(root, 'windows', source)
    process, client, installed, initialized = None, None, False, False
    marker, marker_hash, preserved_files = None, None, {}
    install = Path(os.environ.get('LOCALAPPDATA', 'missing')) / 'Programs/FlowDrop'
    data = Path(os.environ.get('LOCALAPPDATA', 'missing')) / 'FlowDrop'
    state = data / 'Data/desktop-state.json'
    directory = rec.root / 'Dữ liệu nhận có khoảng trắng'
    profile_paths = {}
    def ps(name, script, **options):
        return rec.run(name, ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], **options)
    def app_alive():
        return process is not None and process.poll() is None
    def start():
        nonlocal process, client
        env = clean_env(); env['FLOWDROP_DISABLE_UPDATES'] = '1'
        process = subprocess.Popen([str(install / 'FlowDrop.exe')], cwd=install, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def ready():
            nonlocal client
            if not app_alive():
                raise AssertionError('Native app exited before backend became ready')
            metadata = json.loads(state.read_text(encoding='utf-8'))
            candidate = LiveHTTP(rec, metadata['port'], metadata['token'])
            settings = candidate.json('GET', '/api/desktop/settings', headers={'X-Desktop-Token': metadata['token']})
            client = LiveHTTP(rec, metadata['port'], settings['token'])
            return metadata
        return wait(ready, 'Actual native app/backend startup timed out')
    def stop():
        nonlocal process
        rec.run('native-shutdown-' + str(len(rec.commands)), [install / 'FlowDrop.exe', '--shutdown'], timeout=30)
        if process is not None:
            wait(lambda: process.poll() is not None, 'App process did not stop', 30)
        if client is not None:
            def offline():
                try:
                    client.json('GET', '/api/config'); return False
                except (OSError, http_error_types()):
                    return True
            wait(offline, 'Owned backend did not stop', 30)
    try:
        with rec.case('W01-environment', WINDOWS['W01-environment']) as row:
            if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
                raise Blocked('Requires a fresh GitHub-hosted Windows VM, not Linux/Wine or a user machine')
            import winreg
            folders = json.loads(ps('known-folders', "@([Environment]::GetFolderPath('Desktop'); [Environment]::GetFolderPath('StartMenu'); [Environment]::GetFolderPath('SendTo')) | ConvertTo-Json")[0])
            profile_paths.update(desktop=Path(folders[0]) / 'FlowDrop.lnk', menu=Path(folders[1]) / 'Programs/FlowDrop', sendto=Path(folders[2]) / 'FlowDrop.lnk')
            if install.exists() or data.exists() or any(p.exists() for p in profile_paths.values()):
                raise Blocked('Preexisting FlowDrop program/data/shortcut; refusing to modify it')
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop'):
                    raise Blocked('Existing FlowDrop uninstall registry; refusing install')
            except FileNotFoundError:
                pass
            rec.os_version = ps('windows-os-version', 'Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture | ConvertTo-Json')[0].strip()
            row['actual'] = {'os': json.loads(rec.os_version), 'preexisting_flowdrop': False}
            initialized = True
        if not initialized:
            raise Blocked("A preceding required Windows prerequisite did not complete")
        with rec.case('W02-provenance', WINDOWS['W02-provenance']) as row:
            manifest = verify_export(downloads, 'windows', source)
            installer = Path(downloads) / 'FlowDrop-Setup-1.13.0-Windows-x64-TEST-ONLY.exe'
            rec.artifact.update(installer=sha256(installer))
            proof = json.loads((Path(helpers) / 'helper-manifest.json').read_text(encoding='utf-8'))
            assert proof['source']['checkout_commit'] == source['checkout'], 'Helper source differs from app/runtime source'
            assert proof['status'] == 'PASS'
            assert len(proof['files']) == 2 and not proof['source']['uncommitted_paths']
            for helper in proof['files']:
                assert helper['name'] in ['FlowDrop-windows-native-smoke-TEST-ONLY.exe', 'FlowDrop-windows-shell-smoke-TEST-ONLY.exe']
                assert helper['source'] == 'tests/' + helper['name'].removeprefix('FlowDrop-').removesuffix('-TEST-ONLY.exe') + '.cpp'
                file = Path(helpers) / helper['name']
                assert sha256(file) == helper['sha256'] and sha256(REPO / helper['source']) == helper['source_sha256']
                expected_manifest = (REPO / 'desktop/windows/FlowDrop.manifest').read_bytes().rstrip(b'\0')
                assert any(path[0] == 24 and raw.rstrip(b'\0') == expected_manifest
                           for path, raw in pe_info(file.read_bytes())['resources']), 'Helper Common Controls activation manifest missing'
            row['actual'] = {'installer_sha256': rec.artifact['installer'], 'helper_files_verified': len(proof['files'])}
        if rec.cases[-1]['status'] != 'PASS':
            raise Blocked("A preceding required Windows prerequisite did not complete")
        with rec.case('W03-install', WINDOWS['W03-install']) as row:
            row['command_or_method'] = 'Verified TEST ONLY NSIS installer /S'
            rec.run('nsis-install', [installer, '/S'], timeout=180)
            wait(lambda: (install / 'FlowDrop.exe').is_file(), 'NSIS did not install native executable')
            installed = True
            row.update(exit_code=0, actual={'install_directory': str(install)})
        if not installed:
            raise Blocked("A preceding required Windows prerequisite did not complete")
        with rec.case('W04-payload', WINDOWS['W04-payload']) as row:
            for item in manifest['windows_payload']['inventory']:
                file = install / item['path']
                assert file.is_file() and sha256(file) == item['sha256'], 'Installed payload differs: ' + item['path']
            pe = pe_info((install / 'FlowDrop.exe').read_bytes())
            assert pe['machine'] == 0x8664 and pe['subsystem'] == 2
            row['actual'] = {'payload_files': len(manifest['windows_payload']['inventory']), 'machine': 'AMD64', 'subsystem': 'WINDOWS_GUI', 'node_sha256': sha256(install / 'runtime/node.exe')}
        if rec.cases[-1]['status'] != 'PASS':
            raise Blocked('Installed payload integrity failed; refusing application execution')
        (data / 'Data').mkdir(parents=True, exist_ok=True)
        marker = data / 'Data/runtime-user-data.txt'
        marker.write_text('FlowDrop 2D1 synthetic data preserved by uninstall', encoding='utf-8')
        marker_hash = sha256(marker)
        with rec.case('W05-start', WINDOWS['W05-start']) as row:
            metadata = start()
            actual = json.loads(ps('app-backend-processes', 'Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -in @(' + str(process.pid) + ',' + str(metadata['pid']) + ') } | Select-Object ProcessId,ParentProcessId,ExecutablePath | ConvertTo-Json')[0])
            assert any(p['ExecutablePath'] and Path(p['ExecutablePath']).resolve() == (install / 'runtime/node.exe').resolve() for p in actual)
            row['actual'] = {'processes': actual, 'app_pid': process.pid, 'backend_pid': metadata['pid']}
        if client is None:
            raise Blocked("A preceding required Windows prerequisite did not complete")
        with rec.case('W06-http', WINDOWS['W06-http']) as row:
            config = client.json('GET', '/api/config')
            assert (config['name'], config['version'], config['platform'], config['mode']) == ('FlowDrop', '1.13.0', 'windows', 'local')
            identity = config['deviceId']
            row['actual'] = {k: config[k] for k in ['name', 'version', 'platform', 'mode']}
        with rec.case('W07-window', WINDOWS['W07-window']) as row:
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]; user32.FindWindowW.restype = wintypes.HWND
            hwnd = wait(lambda: user32.FindWindowW('FlowDrop.NativeDesktop', None), 'Native HWND never appeared')
            user32.IsWindowVisible.argtypes = [wintypes.HWND]
            row['actual'] = {'native_hwnd_created': bool(hwnd), 'is_window_visible': bool(user32.IsWindowVisible(hwnd)),
                             'interactive_desktop': ps('desktop-capability', '[Environment]::UserInteractive; (Get-Process -Id $PID).SessionId')[0].strip(),
                             'scope': 'Actual HWND; legacy native test separately checks visible Explorer and native dialogs'}
        with rec.case('W08-single-instance', WINDOWS['W08-single-instance']) as row:
            original = process.pid
            rec.run('second-native-instance', [install / 'FlowDrop.exe'], timeout=20)
            assert app_alive() and process.pid == original
            row.update(exit_code=0, actual={'original_pid_preserved': True})
        with rec.case('W09-shortcuts', WINDOWS['W09-shortcuts']) as row:
            assert all(p.exists() for p in profile_paths.values()), 'Installer shortcut missing'
            link = str(profile_paths['sendto']).replace("'", "''")
            shortcut = json.loads(ps('sendto-shortcut', "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + link + "'); @{TargetPath=$s.TargetPath;Arguments=$s.Arguments} | ConvertTo-Json")[0])
            assert Path(shortcut['TargetPath']).resolve() == (install / 'FlowDrop.exe').resolve() and shortcut['Arguments'] == '--send-files'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop') as key:
                assert winreg.QueryValueEx(key, 'DisplayVersion')[0] == '1.13.0'
            row['actual'] = {'sendto': shortcut, 'desktop_and_startmenu': True, 'uninstall_registry': True}
        directory.mkdir()
        client.desktop('/api/desktop/settings', {'directory': str(directory), 'autoSave': True})
        with rec.case('W10-transfer-sha', WINDOWS['W10-transfer-sha']) as row:
            row['actual'] = client.transfer(directory, 1)
        with rec.case('W11-collision', WINDOWS['W11-collision']) as row:
            row['actual'] = client.transfer(directory, 2)
        preserved_files = dict(client.received)
        with rec.case('W12-cancel', WINDOWS['W12-cancel']) as row:
            row['actual'] = client.cancel()
        with rec.case('W13-disconnect', WINDOWS['W13-disconnect']) as row:
            row['actual'] = client.disconnect()
        with rec.case('W14-invalid', WINDOWS['W14-invalid']) as row:
            row['actual'] = client.invalid()
            row['actual']['reserved_folder'] = client.reserved_folder(directory)
        stop()
        for case_id, name in [('W15-legacy-native', 'windows-native-smoke'), ('W16-legacy-shell', 'windows-shell-smoke')]:
            with rec.case(case_id, WINDOWS[case_id]) as row:
                observer_stop = threading.Event()
                observer = threading.Thread(target=dialog_evidence, args=(observer_stop, rec.root / ('logs/' + name + '-dialogs.json'), rec.secrets), daemon=True)
                observer.start()
                try:
                    helper_env = clean_env(); helper_env['FLOWDROP_DISABLE_UPDATES'] = '1'
                    output, code = rec.run(name, [Path(helpers) / ('FlowDrop-' + name + '-TEST-ONLY.exe'), install / 'FlowDrop.exe'], timeout=600, env=helper_env)
                finally:
                    observer_stop.set(); observer.join(timeout=5)
                assert 'PASS:' in output
                row.update(exit_code=code, actual='Original compiled C++ smoke ran on Windows and completed all assertions', evidence_path='logs/' + name + '.log')
            # A failing helper must not leave an application instance affecting the next case.
            rec.run('stop-after-' + name, [install / 'FlowDrop.exe', '--shutdown'], timeout=30, check=False)
            time.sleep(1)
        with rec.case('W17-backend-failure', WINDOWS['W17-backend-failure']) as row:
            metadata = start()
            ps('stop-only-owned-backend', 'Stop-Process -Id ' + str(int(metadata['pid'])) + ' -Force')
            def no_backend():
                try:
                    client.json('GET', '/api/config'); return False
                except OSError:
                    return True
            wait(no_backend, 'Killed owned backend still served HTTP')
            row['actual'] = {'owned_backend_pid': metadata['pid'], 'http_unavailable': True}
        with rec.case('W18-close', WINDOWS['W18-close']) as row:
            stop(); row.update(exit_code=0, actual={'native_and_backend_stopped': True})
        with rec.case('W19-restart', WINDOWS['W19-restart']) as row:
            start(); assert client.json('GET', '/api/config')['deviceId'] == identity
            assert sha256(marker) == marker_hash
            assert len(preserved_files) >= 3, 'No successful receive available to verify restart preservation'
            for file, expected in preserved_files.items():
                assert sha256(file) == expected, 'Restart changed received file SHA-256'
            stop(); row['actual'] = {'app_and_backend_restarted': True, 'persistent_device_id': True, 'synthetic_user_data_sha256': marker_hash,
                                    'received_files_reverified': len(preserved_files)}
    except Exception as error:
        with rec.case('W-infrastructure-error', 'Runtime orchestration completes'):
            raise error
    finally:
        if installed:
            with rec.case('W20-uninstall', WINDOWS['W20-uninstall']) as row:
                rec.run('native-close-before-uninstall', [install / 'FlowDrop.exe', '--shutdown'], check=False, timeout=30)
                rec.run('nsis-uninstall', [install / 'Uninstall.exe', '/S'], timeout=180)
                wait(lambda: not install.exists(), 'Uninstall did not remove installed payload', 60)
                assert all(not p.exists() for p in profile_paths.values()), 'Shortcut remained after uninstall'
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop'):
                        raise AssertionError('Uninstall registry remained')
                except FileNotFoundError:
                    pass
                app_path = str(install / 'FlowDrop.exe').replace("'", "''")
                node_path = str(install / 'runtime/node.exe').replace("'", "''")
                residual = json.loads(ps('confirm-no-owned-processes-after-uninstall',
                    "$p=@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ($_.ExecutablePath -eq '" + app_path +
                    "' -or $_.ExecutablePath -eq '" + node_path + "') } | Select-Object ProcessId,ExecutablePath); ConvertTo-Json -InputObject $p")[0])
                assert residual == [], 'Owned application/backend process remained after uninstall'
                row.update(exit_code=0, actual={'install_removed': True, 'shortcuts_removed': True, 'registry_removed': True, 'owned_processes_remaining': 0})
            with rec.case('W21-preserve-data', WINDOWS['W21-preserve-data']) as row:
                assert marker is not None and marker.is_file() and sha256(marker) == marker_hash, 'Uninstall removed or changed user data beyond NSIS design'
                assert len(preserved_files) >= 3
                for file, expected in preserved_files.items():
                    assert sha256(file) == expected, 'Uninstall changed custom-directory received data'
                row['actual'] = {'synthetic_data_preserved': True, 'sha256': marker_hash, 'received_files_reverified': len(preserved_files)}
            if initialized and marker is not None and marker.is_file() and marker.read_text(encoding='utf-8') == 'FlowDrop 2D1 synthetic data preserved by uninstall':
                # Created only after an empty-profile guard; never delete preexisting user data.
                shutil.rmtree(data)
    return rec.finish(WINDOWS)


def http_error_types():
    import http.client
    return http.client.HTTPException


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True); parser.add_argument('--artifact', required=True); parser.add_argument('--helpers', required=True)
    args = parser.parse_args()
    return run(args.work_root, args.artifact, args.helpers)


if __name__ == '__main__':
    raise SystemExit(main())
