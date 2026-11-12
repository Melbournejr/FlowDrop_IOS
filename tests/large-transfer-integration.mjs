// Real HTTP streaming between the Node desktop host and the Android Java host.
import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,rm,readFile,readdir,mkdir} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url)),tools=process.env.FLOWDROP_BUILD_TOOLS||'/workspace/flowdrop-build';
const folder=await mkdtemp(path.join(tmpdir(),'flowdrop-large-')),jar=path.join(tools,'downloads/json-test.jar'),compiled=path.join(tools,'android-jvm-tests');await mkdir(compiled,{recursive:true});
const javac=spawnSync('java',['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-classpath',jar,'-d',compiled,path.join(root,'android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java'),path.join(root,'android/src/app/flowdrop/mobile/CodeLookup.java'),path.join(root,'tests/HostHarness.java')],{encoding:'utf8'});assert.equal(javac.status,0,javac.stderr);
const node=spawn(process.execPath,['scripts/dev.mjs'],{cwd:root,env:{...process.env,PORT:'0',FLOWDROP_DESKTOP:'1',FLOWDROP_DESKTOP_NATIVE:'1',FLOWDROP_DATA_DIR:path.join(folder,'node'),FLOWDROP_DEFAULT_RECEIVE_DIR:path.join(folder,'saved')},stdio:['ignore','pipe','pipe']});
const java=spawn('java',['-Xmx96m','-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.HostHarness',path.join(folder,'android'),path.join(root,'web')],{stdio:['ignore','pipe','pipe']});
const children=[node,java];
function origin(child){return new Promise((resolve,reject)=>{let log='';const t=setTimeout(()=>reject(new Error('Host startup timeout '+log)),15000);child.stderr.on('data',b=>log+=b);child.on('exit',c=>{clearTimeout(t);reject(new Error('Host exit '+c+' '+log));});child.stdout.on('data',b=>{const m=b.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(t);resolve(m[0]);}});});}
const sum=async body=>{const hash=createHash('sha256');let bytes=0;for await(const part of body){bytes+=part.length;hash.update(part);}return {bytes,sha256:hash.digest('hex')};};
const LENGTH=384*1024*1024+17,block=Buffer.alloc(1024*1024);for(let i=0;i<block.length;i++)block[i]=i%251;
const expected=createHash('sha256');for(let n=0;n<LENGTH;n+=block.length)expected.update(block.subarray(0,Math.min(block.length,LENGTH-n)));const digest=expected.digest('hex');
const generated=()=>{let remaining=LENGTH;return new ReadableStream({pull(c){if(!remaining){c.close();return;}const n=Math.min(block.length,remaining);c.enqueue(block.subarray(0,n));remaining-=n;}});};
const peak=async child=>{try{return Number((await readFile('/proc/'+child.pid+'/status','utf8')).match(/VmHWM:\s+(\d+)/)[1])*1024;}catch{return null;}};
async function create(base,files){const response=await fetch(base+'/api/transfers',{method:'POST',body:JSON.stringify({files})});assert.equal(response.status,201,await response.clone().text());return response.json();}
async function finish(base,s){const response=await fetch(base+'/api/transfers/'+s.code+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}});assert.equal(response.status,200,await response.text());}
async function put(base,s,index,body){const response=await fetch(base+'/api/transfers/'+s.code+'/files/'+s.files[index].id,{method:'PUT',headers:{'X-Upload-Token':s.token},body,duplex:'half'});assert.equal(response.status,200,await response.text());}
const results=[];
try{
 const [desktop,android]=await Promise.all(children.map(origin));
 for(const [name,base] of [['desktop',desktop],['android',android]]){
  const files=Array.from({length:101},(_,i)=>({name:'Tệp tiếng Việt '+i+'.txt',size:1})),session=await create(base,files);
  for(let i=0;i<files.length;i++)await put(base,session,i,Buffer.from([i%256]));await finish(base,session);
  const metadata=await(await fetch(base+'/api/transfers/'+session.code)).json();assert.equal(metadata.files.length,101);
  for(let i=0;i<101;i++)assert.deepEqual(Buffer.from(await(await fetch(base+'/api/transfers/'+session.code+'/files/'+session.files[i].id)).arrayBuffer()),Buffer.from([i%256]));
  results.push({host:name,files:101,passed:true});console.log(name+': 101 files uploaded, finalized and downloaded.');
 }
 const first=await create(desktop,[{name:'Video dung lượng lớn.bin',size:LENGTH}]);await put(desktop,first,0,generated());await finish(desktop,first);
 const response=await fetch(desktop+'/api/transfers/'+first.code+'/files/'+first.files[0].id);assert.equal(Number(response.headers.get('content-length')),LENGTH);
 const second=await create(android,[{name:'Video dung lượng lớn.bin',size:LENGTH}]);await put(android,second,0,response.body);await finish(android,second);
 const returned=await fetch(android+'/api/transfers/'+second.code+'/files/'+second.files[0].id);assert.deepEqual(await sum(returned.body),{bytes:LENGTH,sha256:digest});
 const third=await create(desktop,[{name:'Nhận từ Android.bin',size:LENGTH}]);const fromAndroid=await fetch(android+'/api/transfers/'+second.code+'/files/'+second.files[0].id);await put(desktop,third,0,fromAndroid.body);await finish(desktop,third);
 const settings=await(await fetch(desktop+'/api/desktop/settings')).json();const saved=await fetch(desktop+'/api/desktop/receive',{method:'POST',headers:{'X-Desktop-Token':settings.token},body:JSON.stringify({code:third.code})});assert.equal(saved.status,200,await saved.clone().text());const files=(await saved.json()).files;assert.deepEqual(await sum(createReadStream(files[0].path)),{bytes:LENGTH,sha256:digest});
 const memory=await Promise.all(children.map(peak));assert.ok(memory[0]<300*1024*1024,'Desktop buffered a large file: '+memory[0]);assert.ok(memory[1]<300*1024*1024,'Java host exceeded memory budget: '+memory[1]);
 results.push({directions:['Desktop → Android','Android → Desktop'],size:LENGTH,sha256:digest,permanentSave:true,peakRssBytes:{desktop:memory[0],android:memory[1]},passed:true});
 assert.ok(!(await readdir(path.join(folder,'node'))).some(n=>n.startsWith('.upload-')));
 console.log(JSON.stringify(results,null,2));await (await import('node:fs/promises')).writeFile(path.join(tools,'large-transfer-verification.json'),JSON.stringify(results,null,2));
}finally{for(const child of children)child.kill();await Promise.all(children.map(c=>new Promise(r=>c.exitCode!==null?r():c.once('exit',r))));await rm(folder,{recursive:true,force:true});}
