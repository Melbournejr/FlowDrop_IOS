"""Actual Windows Preview coexistence on the owned, clean runtime VM only."""
import json
from pathlib import Path
import subprocess

from scripts import windows_preview as preview
from .common import Blocked, clean_env, sha256
from .http_probe import LiveHTTP


def verify(rec, downloads, manifest, install, data, profiles, original, wait, ps):
    import winreg
    target = install.with_name(preview.LABEL)
    private = data.with_name(preview.LABEL) / 'Data'
    state = private / 'desktop-state.json'
    links = {'desktop': profiles['desktop'].with_name(preview.LABEL + '.lnk'),
             'menu': profiles['menu'].with_name(preview.LABEL),
             'sendto': profiles['sendto'].with_name(preview.LABEL + '.lnk')}
    if target.exists() or private.parent.exists() or any(p.exists() for p in links.values()):
        raise Blocked('Preexisting Preview program/data/shortcuts; refusing to modify them')
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, preview.REGISTRY):
            raise Blocked('Preexisting Preview uninstall registration')
    except FileNotFoundError:
        pass
    setup = Path(downloads) / preview.SETUP
    assert sha256(setup) == manifest['windows_preview']['windows_installer']['sha256']
    rec.artifact['preview'] = sha256(setup)
    originals = {p: sha256(p) for p in [install / 'FlowDrop.exe', data / 'Data/runtime-user-data.txt', data / 'Data/device-id']}
    for path in profiles.values():
        if path.is_file():
            originals[path] = sha256(path)
        elif path.is_dir():
            originals.update({p: sha256(p) for p in path.rglob('*') if p.is_file()})
    before = original.json('GET', '/api/config')
    installed, process, client = False, None, None
    try:
        _, denied = rec.run('preview-refuses-original-install-directory', [setup, '/S', '/D=' + str(install)], timeout=120, check=False)
        assert denied == 2 and sha256(install / 'FlowDrop.exe') == originals[install / 'FlowDrop.exe'], 'Preview accepted original install directory'
        rec.run('install-windows-preview', [setup, '/S'], timeout=180)
        installed = True
        assert (target / preview.EXE).is_file() and not (target / 'FlowDrop.exe').exists()
        for item in manifest['windows_preview']['windows_payload']['inventory']:
            assert sha256(target / item['path']) == item['sha256'], 'Installed Preview payload differs'
        assert all(p.exists() for p in links.values())
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, preview.REGISTRY) as key:
            assert winreg.QueryValueEx(key, 'DisplayName')[0] == preview.LABEL
        shortcut = str(links['sendto']).replace("'", "''")
        info = json.loads(ps('preview-sendto-link', "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + shortcut + "'); @{TargetPath=$s.TargetPath;Arguments=$s.Arguments} | ConvertTo-Json")[0])
        assert Path(info['TargetPath']).resolve() == (target / preview.EXE).resolve() and info['Arguments'] == '--send-files'
        # Deliberately inherit the original data path: native Preview overrides it.
        env = clean_env(); env['FLOWDROP_DATA_DIR'] = str(data / 'Data')
        process = subprocess.Popen([str(target / preview.EXE)], cwd=target, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def ready():
            nonlocal client
            if process.poll() is not None:
                raise AssertionError('Preview native process exited before readiness')
            metadata = json.loads(state.read_text(encoding='utf-8'))
            client = LiveHTTP(rec, metadata['port'], metadata['token'])
            return client.json('GET', '/api/desktop/settings', headers={'X-Desktop-Token': client.capability})
        settings = wait(ready, 'Preview backend did not start')
        own = client.json('GET', '/api/config')
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]; user.FindWindowW.restype = wintypes.HWND
        original_window = user.FindWindowW('FlowDrop.NativeDesktop', None)
        preview_window = user.FindWindowW('FlowDrop Preview.NativeDesktop', None)
        assert original_window and preview_window and original_window != preview_window
        assert own['deviceId'] != before['deviceId'] and own['secure']['fingerprint'] != before['secure']['fingerprint']
        assert client.port != original.port and Path(settings['directory']).name == preview.LABEL
        assert Path(settings['directory']).resolve() != Path(original.json('GET', '/api/desktop/settings', headers={'X-Desktop-Token': original.capability})['directory']).resolve()
        rec.run('preview-second-instance', [target / preview.EXE], timeout=30)
        assert process.poll() is None and original.json('GET', '/api/config')['deviceId'] == before['deviceId']
        # A malicious/manual toggle cannot enable the production updater.
        assert client.desktop('/api/desktop/update/settings', {'automatic': True})['automatic'] is False
        assert client.desktop('/api/desktop/update/check')['phase'] == 'disabled'
        denied_update = client.json('POST', '/api/desktop/update/apply', headers={'X-Desktop-Token': client.capability}, expected=400)
        assert 'error' in denied_update
        rec.run('uninstall-only-windows-preview', [target / 'Uninstall.exe', '/S'], timeout=180, env=env)
        wait(lambda: process.poll() is not None and not target.exists(), 'Preview did not uninstall/stop')
        installed = False
        assert not any(p.exists() for p in links.values())
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, preview.REGISTRY):
                raise AssertionError('Preview uninstall registry retained')
        except FileNotFoundError:
            pass
        for file, digest in originals.items():
            assert file.is_file() and sha256(file) == digest, 'Preview changed original data/program/shortcut'
        assert original.json('GET', '/api/config')['deviceId'] == before['deviceId'], 'Preview stopped original backend'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop') as key:
            assert winreg.QueryValueEx(key, 'DisplayName')[0] == 'FlowDrop'
        return {'installed_together': True, 'distinct_process': preview.EXE, 'distinct_data': str(private),
                'distinct_device_identity': True, 'distinct_ports': [original.port, client.port], 'second_instance_scoped': True,
                'sendto_separate': True, 'updates_disabled': True, 'original_directory_rejected_exit': denied,
                'preview_uninstalled': True, 'original_preserved': len(originals), 'original_backend_still_running': True}
    finally:
        if installed and (target / 'Uninstall.exe').is_file():
            rec.run('cleanup-owned-windows-preview', [target / 'Uninstall.exe', '/S'], timeout=180, check=False)
        if process is not None and process.poll() is None:
            rec.run('cleanup-owned-preview-shutdown', [target / preview.EXE, '--shutdown'], timeout=30, check=False)
        # Preview data belongs to this fresh guarded VM; actual uninstall retains it.
        if private.parent.exists() and private.parent.name == preview.LABEL:
            import shutil
            shutil.rmtree(private.parent)
