"""Isolated Android Preview overlay. Never rewrite the checkout or production APK."""
import hashlib
import os
import re
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

from scripts.native_build_ci.paths import fresh_child, write_json

PACKAGE = 'app.flowdrop.preview'
APK_NAME = 'FlowDrop-Preview-1.14.0-Android-TEST-ONLY.apk'
LABEL = 'FlowDrop Preview'
NS = '{http://schemas.android.com/apk/res/android}'
REMOVED_PERMISSIONS = {'android.permission.REQUEST_INSTALL_PACKAGES',
                      'android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION',
                      'android.permission.RECEIVE_BOOT_COMPLETED'}

# Preview has no release channel or PackageInstaller entry point. The original
# updater (including signer/RSA checks) remains byte-for-byte in production.
UPDATER = '''package app.flowdrop.preview;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.widget.Toast;
public final class AppUpdates {
  public static boolean automatic(Context c){return false;}
  public static boolean installing(){return false;}
  public static synchronized boolean reserveTransfer(){return true;}
  public static String status(Context c){return "FlowDrop Preview · Không tự động cập nhật. Cài bản Preview mới bằng APK riêng.";}
  public static void configure(Context c,boolean enabled){}
  public static void schedule(Context c){}
  public static void resume(Activity a){}
  public static void manual(Activity a){Toast.makeText(a,status(a),Toast.LENGTH_LONG).show();}
  public static boolean check(Context c){return false;}
  public static void offer(Activity a,boolean manual){}
  public static synchronized void install(Context c,boolean manual){}
  public static void installResult(Context c,int status,Intent confirmation,String error){}
}
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Preview source anchor changed; refusing ambiguous overlay')
    return text.replace(old, new)


def prepare(source, root):
    source, root = Path(source).resolve(), Path(root).resolve()
    if source == root or source == root / 'preview-source':
        raise RuntimeError('Preview requires a separate working source')
    output = fresh_child(root, root / 'preview-source')
    for folder in ['android', 'web/assets/fonts']:
        shutil.copytree(source / folder, output / folder, ignore=shutil.ignore_patterns('build'))
    for file in ['scripts/build-installers.py', 'scripts/native_build_support.py', 'desktop/windows/installer.nsi']:
        target = output / file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / file, target)
    manifest = output / 'android/AndroidManifest.xml'
    tree = ET.parse(manifest)
    if tree.getroot().get('package') != 'app.flowdrop.mobile':
        raise RuntimeError('Preview overlay expects original production package')
    ET.register_namespace('android', NS[1:-1])
    tree.getroot().set('package', PACKAGE)
    for permission in list(tree.getroot().findall('uses-permission')):
        if permission.get(NS + 'name') in REMOVED_PERMISSIONS:
            tree.getroot().remove(permission)
    application = tree.getroot().find('application')
    application.set(NS + 'label', LABEL)
    commit = os.environ.get('FLOWDROP_REVIEWED_HEAD', '')
    ET.SubElement(application, 'meta-data', {NS + 'name': 'flowdrop.preview.commit', NS + 'value': commit if re.fullmatch(r'[a-f0-9]{40}', commit) else 'source'})
    for item in list(application):
        if item.get(NS + 'name') in ['.UpdateJobService', '.UpdateInstallReceiver']:
            application.remove(item)
    tree.write(manifest, encoding='utf-8', xml_declaration=True)
    java = output / 'android/src/app/flowdrop/mobile'
    for file in java.glob('*.java'):
        text = file.read_text(encoding='utf-8').replace('app.flowdrop.mobile', PACKAGE)
        if file.name in ['ReceiveFiles.java', 'FolderReceive.java', 'MainActivity.java']:
            text = text.replace('Download/FlowDrop', 'Download/FlowDrop Preview').replace('DCIM/FlowDrop', 'DCIM/FlowDrop Preview').replace('Album/FlowDrop', 'Album/FlowDrop Preview').replace('Album FlowDrop', 'Album FlowDrop Preview')
        if file.name == 'MainActivity.java':
            text = replace_once(text, 'label("FlowDrop.",22', 'label("FlowDrop Preview",22')
            text = replace_once(text, 'updates.setChecked(AppUpdates.automatic(this));', 'updates.setChecked(false);updates.setEnabled(false);')
        if file.name == 'HostService.java':
            text = replace_once(text, 'null,device,5173)', 'null,device,5175)')
            text = replace_once(text, 'final String device=shortName.toString()', 'final String device="Preview · "+shortName.toString()')
            text = text.replace('"FlowDrop đang chia sẻ', '"FlowDrop Preview đang chia sẻ')
        if file.name == 'AppUpdates.java':
            text = UPDATER
        file.write_text(text, encoding='utf-8')
    java.rename(java.with_name('preview'))
    inventory = [{'path': file.relative_to(output).as_posix(),
                  'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
                 for file in sorted(output.rglob('*')) if file.is_file()]
    proof = {'package': PACKAGE, 'label': LABEL, 'updates': 'disabled; no production feed/installer entry points',
             'download_directory': 'Download/FlowDrop Preview', 'media_directory': 'DCIM/FlowDrop Preview',
             'preferred_http_port': 5175, 'source_overlay': inventory}
    write_json(root / 'logs/preview-source.json', proof)
    return output, proof


def build(source, root, journal, signing, fingerprint):
    from scripts.native_build_ci.verify import verify_apk
    output, proof = prepare(source, root)
    journal.run('build-preview-from-source', [sys.executable, output / 'scripts/build-installers.py', '--only', 'android'],
                env=signing, cwd=output, timeout=1200)
    apk = output / 'artifacts/FlowDrop-1.14.0-Android.apk'
    result = verify_apk(apk, output, root, journal, fingerprint, preview=True,
                        secrets=[signing['FLOWDROP_ANDROID_STORE_PASSWORD'], signing['FLOWDROP_ANDROID_KEY_PASSWORD']])
    return apk, {'overlay': proof, **result}
