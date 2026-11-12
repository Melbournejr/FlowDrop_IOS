// Real HTTP streaming between the Node desktop host and the Android Java host.
import {readFile,readdir} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createHarness,javaCommand,localFetch,root,waitForHost} from './helpers/harness.mjs';
const sum=async body=>{const hash=createHash('sha256');let bytes=0;for await(const part of body){bytes+=part.length;hash.update(part);}return {bytes,sha256:hash.digest('hex')};};
const LENGTH=384*1024*1024+17,block=Buffer.alloc(1024*1024);for(let i=0;i<block.length;i++)block[i]=i%251;
const expected=createHash('sha256');for(let n=0;n<LENGTH;n+=block.length)expected.update(block.subarray(0,Math.min(block.length,LENGTH-n)));const digest=expected.digest('hex');
const generated=()=>{let remaining=LENGTH;return new ReadableStream({pull(c){if(!remaining){c.close();return;}const n=Math.min(block.length,remaining);c.enqueue(block.subarray(0,n));remaining-=n;}});};
const peak=async child=>{try{return Number((await readFile('/proc/'+child.pid+'/status','utf8')).match(/VmHWM:\s+(\d+)/)[1])*1024;}catch{return null;}};
async function create(host,files){const response=await localFetch(host,'/api/transfers',{method:'POST',body:JSON.stringify({files})});assert.equal(response.status,201,await response.clone().text());return response.json();}
async function finish(host,s){const response=await fetch(host.origin+'/api/transfers/'+s.code+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}});assert.equal(response.status,200,await response.text());}
async function put(host,s,index,body){const response=await fetch(host.origin+'/api/transfers/'+s.code+'/files/'+s.files[index].id,{method:'PUT',headers:{'X-Upload-Token':s.token},body,duplex:'half'});assert.equal(response.status,200,await response.text());}
const results=[];
const harness=await createHarness('large'),folder=harness.directory;
try{
 // Each source is a separate compiler argument; compilation is inside cleanup scope.
 const {classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/CodeLookup.java','tests/HostHarness.java']);
 const node=harness.spawn(process.execPath,['scripts/dev.mjs'],{env:{...process.env,PORT:'0',FLOWDROP_DESKTOP:'1',FLOWDROP_DESKTOP_NATIVE:'1',FLOWDROP_DISABLE_UPDATES:'1',FLOWDROP_DATA_DIR:path.join(folder,'node'),FLOWDROP_DEFAULT_RECEIVE_DIR:path.join(folder,'saved')},stdio:['ignore','pipe','pipe']});
 const java=harness.spawn(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.HostHarness',path.join(folder,'android'),path.join(root,'web')],{stdio:['ignore','pipe','pipe']});
 const children=[node,java];
 const [desktop,android]=await Promise.all([waitForHost(node,'desktop'),waitForHost(java,'android')]);
 for(const [name,host] of [['desktop',desktop],['android',android]]){
  const body=JSON.stringify({files:[{name:'denied.txt',size:0}]}),wrongHeader=host.header==='X-Desktop-Token'?'X-Local-Token':'X-Desktop-Token';
  for(const headers of [{},{[host.header]:'wrong'},{[wrongHeader]:host.token}])assert.equal((await fetch(host.origin+'/api/transfers',{method:'POST',body,headers})).status,403,name+' must reject a missing, wrong or wrong-kind capability');
  const config=await(await fetch(host.origin+'/api/config')).json();assert.ok(!JSON.stringify(config).includes(host.token),'Discovery must not disclose the local capability');
  console.log(name+': missing, wrong and wrong-kind local capabilities rejected; token absent from config.');
  const base=host.origin,files=Array.from({length:101},(_,i)=>({name:'Tệp tiếng Việt '+i+'.txt',size:1})),session=await create(host,files);
  for(let i=0;i<files.length;i++)await put(host,session,i,Buffer.from([i%256]));await finish(host,session);
  const metadata=await(await fetch(base+'/api/transfers/'+session.code)).json();assert.equal(metadata.files.length,101);
  for(let i=0;i<101;i++)assert.deepEqual(Buffer.from(await(await fetch(base+'/api/transfers/'+session.code+'/files/'+session.files[i].id)).arrayBuffer()),Buffer.from([i%256]));
  results.push({host:name,files:101,passed:true});console.log(name+': 101 files uploaded, finalized and downloaded.');
 }
 const first=await create(desktop,[{name:'Video dung lượng lớn.bin',size:LENGTH}]);await put(desktop,first,0,generated());await finish(desktop,first);
 const response=await fetch(desktop.origin+'/api/transfers/'+first.code+'/files/'+first.files[0].id);assert.equal(Number(response.headers.get('content-length')),LENGTH);
 const second=await create(android,[{name:'Video dung lượng lớn.bin',size:LENGTH}]);await put(android,second,0,response.body);await finish(android,second);
 const returned=await fetch(android.origin+'/api/transfers/'+second.code+'/files/'+second.files[0].id);assert.deepEqual(await sum(returned.body),{bytes:LENGTH,sha256:digest});
 const third=await create(desktop,[{name:'Nhận từ Android.bin',size:LENGTH}]);const fromAndroid=await fetch(android.origin+'/api/transfers/'+second.code+'/files/'+second.files[0].id);await put(desktop,third,0,fromAndroid.body);await finish(desktop,third);
 for(const headers of [{},{'X-Desktop-Token':'wrong'}]){
  assert.equal((await fetch(desktop.origin+'/api/desktop/settings',{headers})).status,403);
  assert.equal((await fetch(desktop.origin+'/api/desktop/receive',{method:'POST',headers,body:JSON.stringify({code:third.code})})).status,403);
 }
 const settings=await(await localFetch(desktop,'/api/desktop/settings')).json();assert.equal(settings.token,desktop.token,'Settings must use the capability received on the private startup pipe');
 const saved=await localFetch(desktop,'/api/desktop/receive',{method:'POST',body:JSON.stringify({code:third.code})});assert.equal(saved.status,200,await saved.clone().text());const files=(await saved.json()).files;assert.deepEqual(await sum(createReadStream(files[0].path)),{bytes:LENGTH,sha256:digest});
 const memory=await Promise.all(children.map(peak));assert.ok(memory.every(n=>Number.isFinite(n)&&n>0),'Peak RSS measurement is required; this test currently needs Linux /proc');assert.ok(memory[0]<300*1024*1024,'Desktop buffered a large file: '+memory[0]);assert.ok(memory[1]<300*1024*1024,'Java host exceeded memory budget: '+memory[1]);
 results.push({directions:['Desktop → Android','Android → Desktop'],size:LENGTH,sha256:digest,permanentSave:true,peakRssBytes:{desktop:memory[0],android:memory[1]},passed:true});
 assert.ok(!(await readdir(path.join(folder,'node'))).some(n=>n.startsWith('.upload-')));
 console.log(JSON.stringify(results,null,2));await harness.writeReport('large-transfer-verification.json',results);
}finally{await harness.cleanup();}
