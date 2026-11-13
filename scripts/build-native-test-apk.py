"""Builds instrumentation only; never included in the production installer."""
from pathlib import Path
import zipfile,os,argparse
from native_build_support import BuildError, load_signing, require_tool_root, run_command, report_failure, fresh_build_directory
r=Path(__file__).resolve().parents[1]
def run(args,**kwargs):return run_command(args,**kwargs)
def main():
 argparse.ArgumentParser(description=__doc__).parse_args()
 try:
  signing=load_signing(r);tools=require_tool_root();bt=tools/'sdk/build-tools/android-15';jar=tools/'sdk/platforms/android-35/android.jar'
  if not (r/'android/build/classes').is_dir():raise BuildError('Compile Android app classes before the instrumentation APK')
  build=fresh_build_directory(tools/'native-instrumentation',tools)
  run([bt/'aapt2','link','-o',build/'resources.apk','-I',jar,'--manifest',r/'tests/android-native-smoke/AndroidManifest.xml'])
  classes=build/'classes';classes.mkdir(exist_ok=True);dex=build/'dex';dex.mkdir(exist_ok=True)
  run(['java','-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-bootclasspath',str(bt/'core-lambda-stubs.jar')+os.pathsep+str(jar),'-classpath',str(jar)+os.pathsep+str(r/'android/build/classes'),'-d',classes,*list((r/'tests/android-native-smoke').glob('*.java'))])
  run(['java','-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--release','--min-api','29','--lib',jar,'--classpath',r/'android/build/classes','--output',dex,*classes.rglob('*.class')])
  unsigned=build/'unsigned.apk'
  import shutil
  shutil.copyfile(build/'resources.apk',unsigned)
  with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as z:
   for p in dex.glob('*.dex'):z.write(p,p.name)
  run([bt/'zipalign','-f','-p','4',unsigned,build/'aligned.apk'])
  run(['java','-jar',bt/'lib/apksigner.jar','sign',*signing.arguments(),'--out',build/'FlowDrop-native-tests.apk',build/'aligned.apk'],signing=True)
  print('Native test APK:',build/'FlowDrop-native-tests.apk')
 except (BuildError,OSError,ValueError) as error:
  return report_failure(error)
 return 0

if __name__=='__main__':
 raise SystemExit(main())
