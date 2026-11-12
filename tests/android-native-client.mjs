import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,mkdir,rm,readdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url)),tools=process.env.FLOWDROP_BUILD_TOOLS||'/workspace/flowdrop-build',jar=path.join(tools,'downloads/json-test.jar'),compiled=path.join(tools,'native-client-tests');await mkdir(compiled,{recursive:true});
const source=['android/src/app/flowdrop/mobile/TransferClient.java','android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','tests/NativeClientHarness.java','tests/NativeHostHarness.java'];
const javac=spawnSync('java',['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-classpath',jar,'-d',compiled,...source.map(s=>path.join(root,s))],{encoding:'utf8'});assert.equal(javac.status,0,javac.stderr);
const folder=await mkdtemp(path.join(tmpdir(),'flowdrop-native-')),desktopData=path.join(folder,'desktop'),androidData=path.join(folder,'android');
const desktop=spawn(process.execPath,['scripts/dev.mjs'],{cwd:root,env:{...process.env,PORT:'0',FLOWDROP_DATA_DIR:desktopData},stdio:['ignore','pipe','pipe']});
const android=spawn('java',['-Xmx96m','-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.NativeHostHarness',androidData],{stdio:['ignore','pipe','pipe']});const children=[desktop,android];
let phoneToken="";
function origin(child){return new Promise((resolve,reject)=>{let log='';const timer=setTimeout(()=>reject(new Error('Host startup timeout '+log)),15000);child.stderr.on('data',b=>log+=b);child.on('exit',c=>{clearTimeout(timer);reject(new Error('Host exit '+c+' '+log));});child.stdout.on('data',b=>{if(child===android)phoneToken=JSON.parse(b.toString().trim()).localToken;const m=b.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]+'/');}});});}
const report=[];
try{
 const [win,phone]=await Promise.all(children.map(origin));
 assert.equal((await fetch(phone)).headers.get('content-type'),'text/plain; charset=utf-8');assert.equal((await fetch(phone+'app.js')).status,404);assert.equal((await(await fetch(phone+'api/config')).json()).version,'1.13.0');
 for(const [name,base,bytes] of [['Windows 1.5 host',win,384*1024*1024+17],['Android 1.6 host',phone,4*1024*1024*1024+131089]]){
  console.log('Testing native Java client → '+name+'; large file '+bytes+' bytes.');
  const result=await new Promise((resolve,reject)=>{const client=spawn('java',['-Xmx96m','-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.NativeClientHarness',base,String(bytes)],{env:{...process.env,FLOWDROP_TEST_LOCAL_CAPABILITY:base===phone?phoneToken:''},stdio:['ignore','pipe','pipe']});let out='',err='';const timer=setTimeout(()=>{client.kill();reject(new Error('Native client timeout '+err));},600000);client.stdout.on('data',b=>out+=b);client.stderr.on('data',b=>err+=b);client.on('exit',code=>{clearTimeout(timer);code===0?resolve(JSON.parse(out.trim().split('\n').at(-1))):reject(new Error(err+out));});});
  report.push({host:name,...result});console.log(JSON.stringify(report.at(-1)));
 }
 for(const name of await readdir(desktopData))assert.ok(!name.startsWith('.upload-')&&!Buffer.from(name,'hex').toString().startsWith('transfers/'),'Desktop leaked cancelled/revoked data');
 assert.deepEqual((await readdir(androidData)).filter(n=>n!=='device-id'),[],'Android leaked cancelled/revoked data');
 await writeFile(path.join(tools,'android-native-client-verification.json'),JSON.stringify(report,null,2));
}finally{for(const child of children)child.kill();await Promise.all(children.map(c=>new Promise(r=>c.exitCode!==null?r():c.once('exit',r))));await rm(folder,{recursive:true,force:true});}
