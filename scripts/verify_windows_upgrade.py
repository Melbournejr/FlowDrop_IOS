"""Actual 1.13 -> 1.14 install-over test, only on a fresh GitHub-hosted Windows VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile

BASE_EXE_SHA='576c3aebfc07e82cdf7031d3d607c10cb951f3a348c3e60e2e1393caf4d1349c'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wait(test, seconds=90):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=test()
            if value:return value
        except (OSError,ValueError,KeyError):pass
        time.sleep(.25)
    raise AssertionError('Isolated upgrade operation timed out')

def main(root,candidate):
    if os.name!='nt' or os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Fresh hosted Windows VM required; never run on an owner PC')
    import winreg
    root=Path(root).resolve();assert not root.exists();root.mkdir()
    install=Path(os.environ['LOCALAPPDATA'])/'Programs/FlowDrop';data=Path(os.environ['LOCALAPPDATA'])/'FlowDrop/Data'
    assert not install.exists() and not data.parent.exists(),'Existing FlowDrop; refusing to touch it'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop'):raise AssertionError('Existing install registry')
    except FileNotFoundError:pass
    report={'status':'NOT VERIFIED','scope':'Actual Windows 1.13.0 production EXE -> freshly source-built 1.14.0 production-layout EXE; synthetic data only','steps':[],'productionAndroidUpgrade':'NOT VERIFIED; owner original signing key required'}
    def save(): (root/'upgrade-results.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,args,**kw):
        p=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,**kw)
        row={'name':name,'exit_code':p.returncode}
        if p.returncode and name in ['actual-windows-kit-validation','actual-windows-private-process-controls']:
            # Both commands are keyless: ValidateOnly or random synthetic inputs.
            # Owner signing deliberately suppresses raw child failures instead.
            from scripts.native_build_support import redact
            row['keylessDiagnostic']=redact((p.stdout+p.stderr).decode(errors='replace'))[-4096:]
        report['steps'].append(row);save();assert p.returncode==0,name;return p.stdout.decode(errors='replace')
    save();old=root/'FlowDrop-Setup-1.13.0-Windows-x64.exe'
    for attempt in range(3):
        try:
            with urllib.request.urlopen('https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Setup-1.13.0-Windows-x64.exe',timeout=40) as stream,old.open('wb') as out:
                size=0
                while chunk:=stream.read(1024*1024):
                    size+=len(chunk);assert size<=24521113;out.write(chunk)
            assert old.stat().st_size==24521113 and sha(old)==BASE_EXE_SHA;break
        except OSError:
            if attempt==2:raise
            time.sleep(2)
    proof=json.loads((candidate/'production-build-proof.json').read_text());new=candidate/'FlowDrop-Setup-1.14.0-Windows-x64.exe'
    assert sha(new)==proof['windows']['sha256'] and new.stat().st_size==proof['windows']['size']
    state=data/'desktop-state.json';process=None;token='';port=0
    def api(route,body=None):
        request=urllib.request.Request('http://127.0.0.1:'+str(port)+route,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Desktop-Token':token},method='GET' if body is None else 'POST')
        with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)
    def start(version):
        nonlocal process,token,port
        env=dict(os.environ,FLOWDROP_DISABLE_UPDATES='1');process=subprocess.Popen([str(install/'FlowDrop.exe')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        def ready():
            nonlocal token,port
            assert process.poll() is None,'Native app exited'
            value=json.loads(state.read_text());token=value['token'];port=value['port'];settings=api('/api/desktop/settings');token=settings['token'];config=api('/api/config');assert config['version']==version
            return config
        return wait(ready,120)
    def stop():
        run('native-shutdown',[install/'FlowDrop.exe','--shutdown']);wait(lambda:process.poll() is not None,40);time.sleep(.5)
    try:
        run('install-official-1.13.0',[old,'/S']);before=start('1.13.0')
        received=root/'Received synthetic';received.mkdir();marker=received/'kept-before-upgrade.bin';marker.write_bytes(b'FlowDrop synthetic received data\0'*1024)
        api('/api/desktop/settings',{'directory':str(received),'autoSave':False});api('/api/desktop/device-name',{'name':'Synthetic upgrade device'})
        stop()
        receipts=data/'receive-receipts.json';receipts.write_text(json.dumps({'synthetic-receipt':{'id':'00000000-0000-4000-8000-000000000001','name':marker.name,'path':str(marker),'size':marker.stat().st_size}}))
        preserved={p:sha(p) for p in [marker,data/'device-id',data/'device-settings.json',data/'receive-settings.json',receipts]}
        old_running=start('1.13.0');assert old_running['deviceId']==before['deviceId']
        run('install-production-layout-1.14.0-over-running-1.13.0',[new,'/S']);wait(lambda:process.poll() is not None,40);after=start('1.14.0')
        assert after['deviceId']==before['deviceId'] and after['deviceName']=='Synthetic upgrade device'
        settings=api('/api/desktop/settings');assert settings['directory']==str(received) and settings['autoSave'] is False
        assert all(p.is_file() and sha(p)==digest for p,digest in preserved.items())
        assert after.get('secure',{}).get('fingerprint'),'Pinned TLS identity was not created'
        identity=after['secure']['fingerprint'];stop();again=start('1.14.0');assert again['secure']['fingerprint']==identity;stop()
        report.update(status='PASS',sourceHead=proof['sourceHead'],candidateSha256=sha(new),baselineSha256=sha(old),preserved={'receivedFile':True,'settings':True,'receiptsHistory':True,'deviceName':True,'deviceUUID':True,'newTlsIdentityStableAcrossRestart':True},installDirectoryUnchanged=True)
        # Validate the exact owner kit on real Windows, without asking for keys.
        kit=root/'Signing kit with spaces'
        with zipfile.ZipFile(candidate/'FlowDrop-1.14.0-LOCAL-SIGNING-KIT.zip') as z:
            for member in z.infolist():
                assert not Path(member.filename).is_absolute() and '..' not in Path(member.filename).parts and ':' not in member.filename
            z.extractall(kit)
        text=run('actual-windows-kit-validation',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',kit/'Start-ReleaseSigning.ps1','-ValidateOnly'])
        assert 'PASS: kit checksums' in text
        test=Path(__file__).resolve().parents[1]/'tests/windows-signing-kit.ps1'
        text=run('actual-windows-private-process-controls',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',test,'-Kit',kit])
        assert 'PASS: synthetic private stdin/env' in text
        report['kitWindowsValidation']='PASS including private-process controls with synthetic values; original-key signing remains NOT VERIFIED';save()
        print('PASS: actual install-over preserves settings/receipts/files/UUID/name and creates persistent TLS identity. Android production upgrade NOT VERIFIED.')
    except Exception as error:
        report.update(status='FAIL',reason=type(error).__name__+': '+str(error));save();raise
    finally:
        if process is not None and process.poll() is None:
            subprocess.run([str(install/'FlowDrop.exe'),'--shutdown'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work-root',required=True);p.add_argument('--candidate',required=True);a=p.parse_args();main(Path(a.work_root),Path(a.candidate))
