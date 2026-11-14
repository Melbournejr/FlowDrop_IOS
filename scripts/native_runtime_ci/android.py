"""Real Android Emulator runtime checks. ADB targets only this owned emulator."""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from scripts.native_build_ci.verify import verify_apk
from .common import Blocked, Recorder, REPO, clean_env, json_file, protected_source, sanitize, sha256, verify_export
from .definitions import ANDROID, INSTRUMENTATIONS
from .sdk import prepare


def instrumentation_result(output, code):
    match = re.search(r'^INSTRUMENTATION_RESULT: result=(\{.*\})$', output, re.M)
    terminal = re.findall(r'^INSTRUMENTATION_CODE:\s*(-?\d+)', output, re.M)
    if code != 0 or not match or terminal != ['-1']:
        raise AssertionError('Instrumentation did not finish successfully (process exit=' + str(code) + ', result=' + str(terminal) + ')')
    result = json.loads(match[1])
    if result.get('passed') is not True:
        raise AssertionError('Instrumentation returned no true assertion result')
    return result


def forwarded_config(port):
    """ADB forwards bytes, not HTTP origins; preserve the app's actual Host.

    The production allowedHost check remains enabled. Using the host-side
    ephemeral tunnel port as Host would correctly be rejected by the app.
    """
    connection = http.client.HTTPConnection('127.0.0.1', int(port), timeout=3)
    try:
        connection.request('GET', '/api/config', headers={'Host': '127.0.0.1:5173'})
        response = connection.getresponse()
        if response.status != 200:
            raise AssertionError('Actual forwarded config response=' + str(response.status))
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise AssertionError('Config response exceeded bound')
        return json.loads(raw)
    finally:
        connection.close()


def run(root, artifact, api):
    source = protected_source()
    rec = Recorder(root, 'android-api-' + str(api), source)
    tools, emulator, raw_emulator, installed, forwarding = None, None, None, False, None
    serial = 'emulator-5554'
    def adb(name, *args, check=True, timeout=120):
        if tools is None or not serial.startswith('emulator-'):
            raise Blocked('No owned emulator transport')
        return rec.run(name, [tools['adb'], '-P', '5039', '-s', serial, *args], env=tools['env'], timeout=timeout, check=check)
    def instr(name, component, extras=()):
        adb('force-stop-before-' + name, 'shell', 'am', 'force-stop', 'app.flowdrop.mobile')
        args = ['shell', 'am', 'instrument', '-w', '-r']
        for key, value in extras:
            args += ['-e', key, value]
        output, code = adb(name, *args, 'app.flowdrop.mobile.test/' + component, check=False, timeout=660)
        result = instrumentation_result(output, code)
        if result.get('sdk') != api:
            raise AssertionError('Instrumentation ran on unexpected API')
        json_file(rec.root / 'logs' / (name + '-result.json'), result)
        return result, code
    class VerifyJournal:
        def run(self, name, args, **kwargs):
            return rec.run(name, args, env=tools['env'], **kwargs)[0]
    try:
        with rec.case('A01-environment', ANDROID['A01-environment']) as row:
            if os.name != 'posix' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
                raise Blocked('Requires an isolated GitHub-hosted Linux runner, not a physical phone or JVM substitute')
            if not Path('/dev/kvm').exists():
                raise Blocked('Hardware acceleration unavailable: /dev/kvm absent')
            if not os.access('/dev/kvm', os.R_OK | os.W_OK):
                user = os.environ.get('USER', '')
                if not re.fullmatch('[A-Za-z0-9_-]+', user):
                    raise Blocked('Cannot safely identify runner user for narrow KVM ACL')
                rec.run('allow-owned-runner-kvm', ['sudo', '-n', 'setfacl', '-m', 'u:' + user + ':rw', '/dev/kvm'])
            if not os.access('/dev/kvm', os.R_OK | os.W_OK):
                raise Blocked('Runner cannot access KVM after scoped device ACL')
            if shutil.disk_usage(rec.root).free < 15 * 2**30:
                raise Blocked('Insufficient free disk for real emulator')
            row['actual'] = {'kvm_read_write': True, 'free_disk_bytes': shutil.disk_usage(rec.root).free, 'requested_api': api}
        if rec.cases[-1]['status'] != 'PASS':
            raise Blocked("A preceding required Android prerequisite did not complete")
        with rec.case('A02-provision', ANDROID['A02-provision']) as row:
            tools = prepare(rec.root, api, rec)
            out, code = rec.run('kvm-acceleration-check', [tools['emulator'], '-accel-check'], env=tools['env'], check=False)
            if code != 0:
                raise Blocked('Official emulator acceleration check failed: ' + str(code))
            row.update(exit_code=code, actual={'acceleration': out.strip(), 'toolchain_pins': 'RUNTIME-TOOLCHAIN-LOCK-2D1.json'})
        if tools is None or rec.cases[-1]['status'] != 'PASS':
            raise Blocked("A preceding required Android prerequisite did not complete")
        with rec.case('A03-boot', ANDROID['A03-boot']) as row:
            rec.run('start-dedicated-adb', [tools['adb'], '-P', '5039', 'start-server'], env=tools['env'])
            raw_emulator = (rec.root / 'emulator-output.raw').open('wb')
            command = [str(tools['emulator']), '-avd', tools['avd'], '-port', '5554', '-accel', 'on', '-no-window',
                       '-no-audio', '-no-boot-anim', '-no-snapshot', '-wipe-data', '-gpu', 'swiftshader']
            emulator = subprocess.Popen(command, env=tools['env'], stdout=raw_emulator, stderr=subprocess.STDOUT, start_new_session=True)
            json_file(rec.root / 'owned-emulator.json', {'pid': emulator.pid, 'purpose': 'Owned FlowDrop 2D1 emulator', 'executable_root': str(tools['emulator'].parent)})
            adb('wait-for-owned-device', 'wait-for-device', timeout=180)
            ready = False
            for attempt in range(180):
                if emulator.poll() is not None:
                    raise AssertionError('Owned emulator exited before Android boot completion')
                output, code = adb('boot-completed-' + str(attempt), 'shell', 'getprop', 'sys.boot_completed', check=False, timeout=15)
                if code == 0 and output.strip() == '1':
                    ready = True; break
                time.sleep(2)
            if not ready:
                raise Blocked('Android never completed boot within explicit readiness deadline')
            actual_api = int(adb('android-api', 'shell', 'getprop', 'ro.build.version.sdk')[0].strip())
            assert actual_api == api, 'Booted unexpected Android API'
            details = {name: adb('device-' + name, 'shell', 'getprop', prop)[0].strip() for name, prop in [
                ('release', 'ro.build.version.release'), ('fingerprint', 'ro.build.fingerprint'), ('abi', 'ro.product.cpu.abi')]}
            rec.os_version = 'Android API' + str(api) + ' ' + details['release'] + ' / ' + details['fingerprint']
            adb('wake-emulator', 'shell', 'input', 'keyevent', '82')
            row.update(exit_code=0, actual={'api': actual_api, 'serial': serial, 'device': details, 'boot_completed': True})
        if rec.cases[-1]['status'] != 'PASS':
            raise Blocked("A preceding required Android prerequisite did not complete")
        with rec.case('A04-provenance', ANDROID['A04-provenance']) as row:
            manifest = verify_export(artifact, 'android', source)
            apk = Path(artifact) / 'FlowDrop-1.13.0-Android-TEST-ONLY.apk'
            testapk = Path(artifact) / 'FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk'
            rec.artifact.update(app=sha256(apk), instrumentation=sha256(testapk))
            certificate = manifest['android']['test_certificate_sha256']
            app = verify_apk(apk, REPO, tools['tool'], VerifyJournal(), certificate)
            test = verify_apk(testapk, REPO, tools['tool'], VerifyJournal(), certificate, instrumentation=True)
            assert app['sha256'] == manifest['android']['sha256'] and test['sha256'] == manifest['instrumentation']['sha256']
            assert manifest['derived_test_harness']['original_tests_retained'] == 4
            assert manifest['derived_test_harness']['additional_runner'] == INSTRUMENTATIONS['A13-runtime-smoke']
            row.update(exit_code=0, actual={'app': app['identity'], 'test_package': test['identity']['package'], 'same_test_certificate_sha256': certificate})
        if rec.cases[-1]['status'] != 'PASS':
            raise Blocked("A preceding required Android prerequisite did not complete")
        with rec.case('A05-install', ANDROID['A05-install']) as row:
            for pkg in ['app.flowdrop.mobile', 'app.flowdrop.mobile.test']:
                existing, _ = adb('check-no-existing-' + pkg, 'shell', 'pm', 'path', pkg, check=False)
                if 'package:' in existing:
                    raise Blocked('Refusing installation over an existing app on emulator')
            adb('install-app', 'install', apk, timeout=180)
            installed = True
            adb('install-instrumentation', 'install', testapk, timeout=180)
            instr('prepare-isolated-application-settings', INSTRUMENTATIONS['A13-runtime-smoke'], [('mode', 'prepare')])
            row.update(exit_code=0, actual={'app_installed': True, 'test_installed': True, 'production_not_replaced': True})
        if not installed or rec.cases[-1]['status'] != 'PASS':
            raise Blocked("A preceding required Android prerequisite did not complete")
        with rec.case('A06-activity', ANDROID['A06-activity']) as row:
            adb('launch-main-activity', 'shell', 'am', 'start', '-W', '-n', 'app.flowdrop.mobile/.MainActivity')
            activity, _ = adb('initial-activity-state', 'shell', 'dumpsys', 'activity', 'activities')
            assert re.search(r'(?:mResumedActivity|topResumedActivity).*app\.flowdrop\.mobile/\.MainActivity', activity), 'MainActivity not actually resumed'
            focused = False
            for attempt in range(60):
                windows, _ = adb('initial-window-focus-' + str(attempt), 'shell', 'dumpsys', 'window')
                if re.search(r'mCurrentFocus=.*app\.flowdrop\.mobile/', windows):
                    focused = True; break
                time.sleep(.5)
            assert focused, 'App Activity does not own the focused Android window'
            adb('initial-screenshot-device', 'shell', 'screencap', '-p', '/sdcard/flowdrop-runtime-initial.png')
            adb('initial-screenshot-pull', 'pull', '/sdcard/flowdrop-runtime-initial.png', rec.root / 'logs/initial-activity.png')
            row.update(exit_code=0, actual={'main_activity_resumed': True, 'screenshot': 'logs/initial-activity.png'})
        with rec.case('A07-permissions', ANDROID['A07-permissions']) as row:
            if api >= 33:
                denied, _ = instr('notification-ui-deny', INSTRUMENTATIONS['A13-runtime-smoke'], [('mode', 'permissions'), ('decision', 'deny')])
                granted, _ = instr('notification-ui-grant', INSTRUMENTATIONS['A13-runtime-smoke'], [('mode', 'permissions'), ('decision', 'grant')])
                row['actual'] = {'deny': denied, 'grant': granted}
            else:
                result, _ = instr('notification-api-policy', INSTRUMENTATIONS['A13-runtime-smoke'], [('mode', 'permissions')])
                row['actual'] = result
            row['exit_code'] = 0
        with rec.case('A08-http', ANDROID['A08-http']) as row:
            adb('launch-for-http', 'shell', 'am', 'start', '-W', '-n', 'app.flowdrop.mobile/.MainActivity')
            forward, _ = adb('forward-loopback-backend', 'forward', 'tcp:0', 'tcp:5173')
            forwarding = int(forward.strip())
            config = None
            for _ in range(60):
                try:
                    config = forwarded_config(forwarding)
                    break
                except (OSError, http.client.HTTPException):
                    time.sleep(.5)
            assert config and config['name'] == 'FlowDrop' and config['version'] == '1.13.0'
            row['actual'] = {k: config.get(k) for k in ['name', 'version', 'platform', 'mode']}
            row['actual']['tunnel_preserves_host'] = '127.0.0.1:5173'
        for test_id, component in INSTRUMENTATIONS.items():
            with rec.case(test_id, ANDROID[test_id]) as row:
                name = test_id.lower()
                result, code = instr(name, component)
                row.update(exit_code=code, command_or_method='adb shell am instrument -w -r app.flowdrop.mobile.test/' + component,
                           actual=result, evidence_path='logs/' + name + '.log')
        with rec.case('A14-force-stop', ANDROID['A14-force-stop']) as row:
            adb('force-stop-app-lifecycle', 'shell', 'am', 'force-stop', 'app.flowdrop.mobile')
            pids, _ = adb('pid-after-force-stop', 'shell', 'pidof', 'app.flowdrop.mobile', check=False)
            assert not pids.strip(), 'App process survived force-stop'
            adb('restart-app-lifecycle', 'shell', 'am', 'start', '-W', '-n', 'app.flowdrop.mobile/.MainActivity')
            ready = None
            for _ in range(60):
                try:
                    ready = forwarded_config(forwarding)
                    break
                except (OSError, http.client.HTTPException):
                    time.sleep(.5)
            assert ready and ready['name'] == 'FlowDrop'
            row.update(exit_code=0, actual={'force_stop_observed': True, 'real_backend_restarted': True})
        with rec.case('A15-crash-anr', ANDROID['A15-crash-anr']) as row:
            raw, code = adb('app-logcat-source', 'logcat', '-d', '-v', 'threadtime', check=False, timeout=60)
            assert code == 0, 'Could not inspect actual Android logcat'
            lines = raw.splitlines()
            selected = set()
            for index, line in enumerate(lines):
                if 'app.flowdrop.mobile' in line or 'AndroidRuntime' in line:
                    selected.update(range(max(0, index - 2), min(len(lines), index + 8)))
            (rec.root / 'logs/android-app-logcat.log').write_text(sanitize('\n'.join(lines[i] for i in sorted(selected)), rec.secrets), encoding='utf-8')
            # Keep filtered app evidence only, not a whole device log dump.
            (rec.root / 'logs/app-logcat-source.log').unlink(missing_ok=True)
            assert 'Process: app.flowdrop.mobile' not in raw and 'ANR in app.flowdrop.mobile' not in raw, 'Android app crash/ANR detected'
            adb('final-activity-state', 'shell', 'dumpsys', 'activity', 'activities')
            adb('final-service-state', 'shell', 'dumpsys', 'activity', 'services', 'app.flowdrop.mobile')
            row.update(exit_code=0, actual={'app_crash': False, 'app_anr': False}, evidence_path='logs/android-app-logcat.log')
    except Exception as error:
        with rec.case('A-infrastructure-error', 'Runtime orchestration completes'):
            raise error
    finally:
        with rec.case('A16-uninstall', ANDROID['A16-uninstall']) as row:
            if tools is None or emulator is None or emulator.poll() is not None:
                raise Blocked('Emulator unavailable for uninstall/cleanup verification')
            if installed:
                adb('uninstall-test', 'uninstall', 'app.flowdrop.mobile.test', check=False)
                adb('uninstall-app', 'uninstall', 'app.flowdrop.mobile')
                paths, _ = adb('confirm-app-removed', 'shell', 'pm', 'path', 'app.flowdrop.mobile', check=False)
                assert 'package:' not in paths
                test_paths, _ = adb('confirm-test-removed', 'shell', 'pm', 'path', 'app.flowdrop.mobile.test', check=False)
                assert 'package:' not in test_paths
            else:
                raise Blocked('No installed test APK was available to uninstall')
            row.update(exit_code=0, actual={'test_app_removed': True, 'target_app_removed': True})
        if tools is not None:
            if forwarding is not None:
                adb('remove-owned-forward', 'forward', '--remove', 'tcp:' + str(forwarding), check=False)
            if emulator is not None and emulator.poll() is None:
                adb('stop-owned-emulator', 'emu', 'kill', check=False, timeout=30)
                try:
                    emulator.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    emulator.kill(); emulator.wait(timeout=15)
            rec.run('stop-owned-adb-server', [tools['adb'], '-P', '5039', 'kill-server'], env=tools['env'], check=False)
        if raw_emulator is not None:
            raw_emulator.close()
            log = rec.root / 'emulator-output.raw'
            content = log.read_bytes()[-8 * 2**20:].decode('utf-8', errors='replace')
            (rec.root / 'logs/emulator-boot.log').write_text(sanitize(content, rec.secrets), encoding='utf-8')
    return rec.finish(ANDROID)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True); parser.add_argument('--artifact', required=True)
    parser.add_argument('--api', type=int, choices=[29, 35], required=True)
    args = parser.parse_args()
    return run(args.work_root, args.artifact, args.api)


if __name__ == '__main__':
    raise SystemExit(main())
