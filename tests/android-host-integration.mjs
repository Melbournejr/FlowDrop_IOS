import {readFile,writeFile,readdir} from 'node:fs/promises';
import path from 'node:path';
import net from 'node:net';
import assert from 'node:assert/strict';
import {createHash,randomBytes} from 'node:crypto';
import {createHarness,javaCommand,root,waitForHost} from './helpers/harness.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const harness=await createHarness('android-host'),data=path.join(harness.directory,'data');
try{
 const {classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/CodeLookup.java','tests/HostHarness.java']);
 const child=harness.spawn(javaCommand,['-cp',classpath,'app.flowdrop.mobile.HostHarness',data,path.join(root,'web')],{stdio:['ignore','pipe','pipe']});
 const {origin,token:localToken}=await waitForHost(child,'android',{timeoutMs:10000});
 const request=(p,options={})=>fetch(origin+p,{...options,headers:{'X-Local-Token':localToken,...options.headers}});
 const create=async(files)=>{const r=await request('/api/transfers',{method:'POST',body:JSON.stringify({files})});assert.equal(r.status,201,await r.clone().text());return r.json();};
 const upload=async(session,index,bytes,chunked=false)=>{
  let body=bytes;if(chunked)body=new ReadableStream({start(c){c.enqueue(bytes.subarray(0,11));c.enqueue(bytes.subarray(11));c.close();}});
  const r=await request('/api/transfers/'+session.code+'/files/'+session.files[index].id,{method:'PUT',headers:{'X-Upload-Token':session.token},body,...(chunked?{duplex:'half'}:{})});assert.equal(r.status,200,await r.text());
 };
 const finish=async s=>{assert.equal((await request('/api/transfers/'+s.code+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}})).status,200);};
 const config=await (await request('/api/config')).json();assert.equal(config.name,'FlowDrop');assert.equal(config.platform,'android');assert.equal(config.version,'1.13.0');
 for(const asset of ['/','/app.js','/style.css','/favicon.svg','/manifest.webmanifest','/assets/fonts/BeVietnamPro-Regular.ttf'])assert.equal((await request(asset)).status,200,asset);
 for(const [direction,bytes,chunked] of [['A → B',randomBytes(1024*1024),false],['B → A',randomBytes(8193),true]]){
  const s=await create([{name:'Từ '+direction+' — tài liệu.bin',size:bytes.length},{name:'rỗng.txt',size:0}]);const base='/api/transfers/'+s.code;
  assert.equal((await request(base)).status,409);assert.equal((await request(base+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}})).status,409);
  await upload(s,0,bytes,chunked);await upload(s,1,new Uint8Array());await finish(s);
  const metadata=await (await request(base,{headers:{'User-Agent':'Other Android phone'}})).json();assert.equal(metadata.token,undefined);assert.equal(metadata.files.length,2);
  const download=await request(base+'/files/'+s.files[0].id);assert.equal(hash(Buffer.from(await download.arrayBuffer())),hash(bytes));assert.match(download.headers.get('Content-Disposition'),/filename\*=UTF-8/);assert.equal((await (await request(base+'/files/'+s.files[1].id)).arrayBuffer()).byteLength,0);
  assert.equal((await request(base,{method:'DELETE'})).status,403);assert.equal((await request(base+'/files/'+s.files[0].id,{method:'PUT',headers:{'X-Upload-Token':s.token},body:bytes})).status,403);
  assert.equal((await request(base,{method:'DELETE',headers:{'X-Upload-Token':s.token}})).status,200);assert.equal((await request(base)).status,404);
  console.log('Android Java host:',direction,'exact SHA-256, empty file, access controls and revoke passed.');
 }
 for(const files of [[],[{name:'bad\nname',size:1}],[{name:'wrong',size:'1'}],[{name:'fraction',size:1.5}],[{name:'overflow',size:Number.MAX_SAFE_INTEGER+1}]])assert.equal((await request('/api/transfers',{method:'POST',body:JSON.stringify({files})})).status,400);
 assert.equal((await request('/api/transfers',{method:'POST',headers:{Origin:'http://foreign.test'},body:JSON.stringify({files:[{name:'x',size:1}]})})).status,403);
 assert.equal((await request('/api/transfers',{method:'POST',body:'x'.repeat(8*1024*1024+1)})).status,413);
 const partial=await create([{name:'incomplete.bin',size:20}]);
 const raw=await new Promise((resolve,reject)=>{const socket=net.createConnection({host:'127.0.0.1',port:new URL(origin).port});let text='';socket.on('connect',()=>socket.end('PUT /api/transfers/'+partial.code+'/files/'+partial.files[0].id+' HTTP/1.1\r\nHost: '+new URL(origin).host+'\r\nX-Upload-Token: '+partial.token+'\r\nContent-Length: 20\r\n\r\nshort'));socket.on('data',b=>text+=b);socket.on('end',()=>resolve(text));socket.on('error',reject);socket.setTimeout(5000,()=>{socket.destroy();reject(new Error('Partial upload test timeout'));});});
 assert.match(raw,/HTTP\/1\.1 400/);assert.ok(!(await readdir(path.join(data,partial.code))).some(name=>name.includes('.upload-')));
 assert.equal((await request('/api/transfers/'+partial.code+'/complete',{method:'POST',headers:{'X-Upload-Token':partial.token}})).status,409);
 const expiring=await create([{name:'expired.txt',size:0}]);const metaPath=path.join(data,expiring.code,'meta.json'),meta=JSON.parse(await readFile(metaPath,'utf8'));meta.expiresAt=Date.now()-1;await writeFile(metaPath,JSON.stringify(meta));assert.equal((await request('/api/transfers/'+expiring.code)).status,410);assert.equal((await request('/api/transfers/'+expiring.code)).status,404);
 console.log('Android Java host integration passed: both directions, assets/config, Content-Length and chunked uploads, 1 MiB, Unicode names, protocol bounds, partial cleanup, expiry, origin and token checks.');
}finally{await harness.cleanup();}
