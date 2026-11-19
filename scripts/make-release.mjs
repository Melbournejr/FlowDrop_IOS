// Offline release assembly only. Never uploads, publishes or changes the live feed.
import {parseArgs} from 'node:util';
import {readFile,writeFile,mkdtemp,rename,rm,realpath,stat,mkdir} from 'node:fs/promises';
import {spawnSync,execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {APP_VERSION,UPDATE_PUBLIC_KEY} from './release-config.mjs';
import {verifyRelease} from './secure-update.mjs';
import {sha,checkApkContents,checkProductionSigner,signedEnvelope} from './release-support.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
async function main(){
 const {values}=parseArgs({options:{key:{type:'string'},out:{type:'string'},input:{type:'string'},proof:{type:'string'},notes:{type:'string'},java:{type:'string'},apksigner:{type:'string'},'skip-bundle':{type:'boolean',default:false}}});
 const publicEnv={...process.env};for(const name of Object.keys(publicEnv))if(/TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH|JAVA_TOOL_OPTIONS|JDK_JAVA_OPTIONS|_JAVA_OPTIONS|NODE_OPTIONS|CLASSPATH/i.test(name))delete publicEnv[name];
 if(!values.key||!values.proof||!values.java||!values.apksigner||!values.out)throw Error('Required: --key --proof --java --apksigner --out; run Start-ReleaseSigning.ps1');
 if(APP_VERSION!=='1.14.0')throw Error('Unexpected release version');
 const input=path.resolve(values.input||'artifacts'),out=path.resolve(values.out),keyPath=await realpath(values.key),relative=path.relative(root,keyPath);
 if(!relative.startsWith('..'+path.sep)&&relative!=='..'&&!path.isAbsolute(relative))throw Error('Private key must be outside the checkout/signing kit');
 try{await stat(out);throw Error('Output directory already exists');}catch(e){if(e.code!=='ENOENT')throw e;}
 const proof=JSON.parse(await readFile(values.proof)),platforms={},files=new Map();
 for(const [platform,name] of [['windows',`FlowDrop-Setup-${APP_VERSION}-Windows-x64.exe`],['android',`FlowDrop-${APP_VERSION}-Android.apk`]]){
  const bytes=await readFile(path.join(input,name));if(!bytes.length||bytes.length>1024*1024*1024)throw Error('Invalid installer size');
  if(platform==='android')checkApkContents(bytes,proof.android);else if(bytes.subarray(0,2).toString()!=='MZ'||sha(bytes)!==proof.windows.sha256||bytes.length!==proof.windows.size)throw Error('Windows candidate differs from the verified source build');
  files.set(name,bytes);platforms[platform]={version:APP_VERSION,url:`https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v${APP_VERSION}/${name}`,size:bytes.length,sha256:sha(bytes),...(platform==='android'?{versionCode:15}:{})};
 }
 const verification=spawnSync(path.resolve(values.java),['-jar',path.resolve(values.apksigner),'verify','--verbose','--print-certs',path.join(input,`FlowDrop-${APP_VERSION}-Android.apk`)],{env:publicEnv,encoding:'utf8',timeout:120000,maxBuffer:1024*1024});
 if(verification.status!==0)throw Error('APK signature verification failed');checkProductionSigner(verification.stdout);
 const notes=await readFile(values.notes||path.join(root,'docs/releases/Release-notes-1.14.0.md'),'utf8');
 if(!notes.includes('pinned TLS')||!notes.includes('thử nghiệm'))throw Error('Release notes are missing the 1.14 security/experimental status');
 const payload=JSON.stringify({schema:1,app:'FlowDrop',notes:'FlowDrop 1.14.0: pinned TLS và ghép thiết bị; sửa nhận mã/HMAC Android; Auto/LAN mặc định, Turbo thử nghiệm. Cài đè bằng chứng thư gốc, không gỡ app.',platforms});
 const privateBytes=await readFile(keyPath);let envelope;try{envelope=signedEnvelope(payload,privateBytes,process.env.FLOWDROP_UPDATE_KEY_PASSWORD);}finally{privateBytes.fill(0);}
 for(const platform of ['windows','android'])verifyRelease(envelope,UPDATE_PUBLIC_KEY,platform);
 files.set('latest.json',Buffer.from(JSON.stringify(envelope,null,2)+'\n'));files.set('Release-notes-1.14.0.md',Buffer.from(notes));
 files.set('SHA256SUMS-release.txt',Buffer.from([...files].map(([name,bytes])=>sha(bytes)+'  '+name).join('\n')+'\n'));
 await mkdir(path.dirname(out),{recursive:true});const stage=await mkdtemp(path.join(path.dirname(out),'.flowdrop-release-'));
 try{for(const [name,bytes] of files)await writeFile(path.join(stage,name),bytes,{flag:'wx'});await rename(stage,out);}finally{await rm(stage,{recursive:true,force:true});}
 if(!values['skip-bundle'])execFileSync(process.platform==='win32'?'python':'python3',['-c','import zipfile,sys,pathlib\np=pathlib.Path(sys.argv[1])\nwith zipfile.ZipFile(p/sys.argv[2],"w",zipfile.ZIP_DEFLATED) as z:\n for n in sys.argv[3:]: z.write(p/n,n)',out,'FlowDrop-GitHub-Release-1.14.0.zip',...files.keys()],{env:publicEnv,stdio:'pipe',timeout:120000});
 console.log(JSON.stringify({version:APP_VERSION,versionCode:15,output:out,signature:'verified against original pinned RSA key',apkCertificate:'verified against original 1.13.0 certificate',files:[...files.keys()],platforms},null,2));
}
main().catch(()=>{console.error('Release assembly failed: original key, APK certificate, tool or candidate checksum verification did not pass. No release was published.');process.exitCode=1;});
