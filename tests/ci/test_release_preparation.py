import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]

class ReleasePreparationTests(unittest.TestCase):
    def builder(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        try:
            spec=importlib.util.spec_from_file_location('release_builder_fixture',ROOT/'scripts/build-installers.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        finally:sys.path.pop(0)

    def test_mock_unsigned_control_never_reads_keystore_or_overwrites_signed_output(self):
        builder=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';bt=root/'tools';out=source/'artifacts';out.mkdir(parents=True);signed=out/'FlowDrop-1.14.0-Android.apk';signed.write_bytes(b'preexisting public fixture')
            (source/'android/res').mkdir(parents=True);(source/'android/src').mkdir();(source/'web/assets/fonts').mkdir(parents=True);(source/'web/assets/fonts/OFL.txt').write_text('fixture license');bt.mkdir();(bt/'aapt2').touch();(bt/'zipalign').touch()
            calls=[]
            def tool(args,**kw):
                args=[str(x) for x in args];calls.append(args)
                if 'link' in args:
                    with zipfile.ZipFile(args[args.index('-o')+1],'w') as z:z.writestr('AndroidManifest.xml',b'fixture only')
                if 'com.android.tools.r8.D8' in args:Path(args[args.index('--output')+1],'classes.dex').write_bytes(b'not real dex; mock control only')
                if '-f' in args:
                    import shutil
                    shutil.copyfile(args[-2],args[-1])
            with patch.object(builder,'ROOT',source),patch.object(builder,'OUT',out),patch.object(builder,'BT',bt),patch.object(builder,'JAR',root/'fixture.jar'),patch.object(builder,'load_signing',side_effect=AssertionError('Must not read any signing configuration')),patch.object(builder,'run',side_effect=tool),patch.dict(os.environ,{},clear=True):
                builder.android(True)
            self.assertEqual(signed.read_bytes(),b'preexisting public fixture');self.assertTrue((out/'FlowDrop-1.14.0-Android-UNSIGNED.apk').is_file());self.assertFalse(any('sign' in row for row in calls))

    def test_new_workflow_has_no_publish_permissions_or_production_secret_references(self):
        text=(ROOT/'.github/workflows/native-release-preparation.yml').read_text()
        for forbidden in ['contents: write','id-token: write','pull_request_target','secrets.','continue-on-error','gh release','git push']:
            self.assertNotIn(forbidden,text)
        self.assertIn('contents: read',text);self.assertIn('verify_windows_upgrade',text)

    def test_original_identity_and_experimental_default_are_retained(self):
        import xml.etree.ElementTree as ET
        m=ET.parse(ROOT/'android/AndroidManifest.xml').getroot();ns='{http://schemas.android.com/apk/res/android}'
        self.assertEqual(m.get('package'),'app.flowdrop.mobile');self.assertEqual(m.get(ns+'versionName'),'1.14.0');self.assertEqual(m.get(ns+'versionCode'),'15')
        self.assertIn('mode="auto"',(ROOT/'android/src/app/flowdrop/mobile/TurboLink.java').read_text())
        self.assertIn('Turbo đang thử nghiệm',(ROOT/'android/src/app/flowdrop/mobile/MainActivity.java').read_text())

if __name__=='__main__':unittest.main()
