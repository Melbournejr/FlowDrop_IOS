// Layer A only: production Node engine + Java TransferServer under JVM, HTTP loopback.
// This is neither native Windows/Android E2E nor physical Wi-Fi evidence.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,statfs} from 'node:fs/promises';
import path from 'node:path';
import net from 'node:net';
import {once} from 'node:events';
import {createHarness,javaCommand,root,waitForHost} from './helpers/harness.mjs';
import {request,localRequest} from './helpers/protocol-http.mjs';

const full=process.argv.includes('--full');
const harness=await createHarness('cross-platform-2d2');
const report={phase:'2D.2',layer:'A: automated production-engine protocol verification',network:'loopback HTTP, isolated Linux job',
 source_commit:process.env.FLOWDROP_REVIEWED_HEAD||null,checkout_commit:process.env.FLOWDROP_CHECKOUT_COMMIT||null,
 artifact_sha256:null,artifact_scope:'Source engines; no native installer is executed',
 native_cross_platform_e2e:'BLOCKED',physical_wifi:'NOT VERIFIED',cases:[],status:'NOT VERIFIED'};
const block=Buffer.alloc(1024*1024);for(let i=0;i<block.length;i++)block[i]=i%251;
function body(size,hash){let left=size;return new ReadableStream({pull(controller){if(!left){controller.close();return;}const data=block.subarray(0,Math.min(left,block.length));if(hash)hash.update(data);controller.enqueue(data);left-=data.length;}});}
async function digest(stream){const hash=createHash('sha256');let size=0;for await(const bytes of stream){hash.update(bytes);size+=bytes.length;}return {size,sha256:hash.digest('hex')};}
async function json(response,status){assert.equal(response.status,status,'Unexpected engine status '+response.status);return response.json();}
async function create(host,files){return json(await localRequest(host,'/api/transfers',{method:'POST',body:JSON.stringify({files})}),201);}
async function put(host,session,index,data){const r=await request(host.origin+'/api/transfers/'+session.code+'/files/'+session.files[index].id,{method:'PUT',headers:{'X-Upload-Token':session.token,'Content-Length':String(session.files[index].size)},body:data});await json(r,200);}
async function complete(host,session){return json(await request(host.origin+'/api/transfers/'+session.code+'/complete',{method:'POST',headers:{'X-Upload-Token':session.token}}),200);}
async function revoke(host,session){if(!session)return;await json(await request(host.origin+'/api/transfers/'+session.code,{method:'DELETE',headers:{'X-Upload-Token':session.token}}),200);}
async function measure(id,sender,receiver,operation){const row={test_id:id,sender:sender.kind,receiver:receiver.kind,network:report.network,
 source_commit:report.source_commit,artifact_sha256:null,expected:'Source/destination SHA-256 and exact size agree; security assertions remain enabled',
 status:'NOT VERIFIED',exit_code:null,started_utc:new Date().toISOString(),evidence:'protocol-matrix.json'};
 const start=performance.now();report.cases.push(row);await harness.writeReport('protocol-matrix.json',report);
 try{row.actual=await operation();row.status='PASS';row.exit_code=0;}catch(error){row.status='FAIL';row.exit_code=1;row.error=error.name;throw error;}
 finally{row.elapsed_seconds=(performance.now()-start)/1000;if(row.actual?.size!==undefined){row.size=row.actual.size;row.MB_per_second=row.size/row.elapsed_seconds/1e6;row.Mbps=row.MB_per_second*8;row.rate_method='Full test interval including generation, source stage, relay, destination read/hash; not Wi-Fi throughput';}await harness.writeReport('protocol-matrix.json',report);}
}
async function relay(sender,receiver,size,name){let source,destination;try{
 source=await create(sender,[{name,size,type:'application/octet-stream'}]);const generated=createHash('sha256');
 await put(sender,source,0,body(size,generated));await complete(sender,source);const expected=generated.digest('hex');
 const outgoing=await request(sender.origin+'/api/transfers/'+source.code+'/files/'+source.files[0].id);assert.equal(outgoing.status,200);assert.equal(Number(outgoing.headers.get('content-length')),size);
 destination=await create(receiver,[{name,size,type:'application/octet-stream'}]);await put(receiver,destination,0,outgoing.body);await complete(receiver,destination);
 const incoming=await request(receiver.origin+'/api/transfers/'+destination.code+'/files/'+destination.files[0].id);assert.equal(incoming.status,200);
 const actual=await digest(incoming.body);assert.deepEqual(actual,{size,sha256:expected});
 const metadata=await json(await request(receiver.origin+'/api/transfers/'+destination.code),200);assert.equal(metadata.files[0].name,name);assert.equal(metadata.files[0].size,size);
 assert.ok(!JSON.stringify(metadata).includes(destination.token));
 return {size,source_sha256:expected,destination_sha256:actual.sha256,exact_name:metadata.files[0].name,files:1};
 }finally{await revoke(receiver,destination);await revoke(sender,source);}}
async function many(sender,receiver){let source,destination;try{
 const payloads=Array.from({length:101},(_,i)=>Buffer.from('Dữ liệu tổng hợp 中文 😀 '+i));payloads[0]=Buffer.alloc(0);
 const files=payloads.map((b,i)=>({name:i===0?'Rỗng.bin':i===1?'Tiếng Việt 中文 😀 có khoảng trắng.txt':i===2?'Tên dài '+'a'.repeat(180)+'.txt':'file '+i+'.bin',size:b.length,type:'application/octet-stream'}));
 source=await create(sender,files);for(let i=0;i<files.length;i++)await put(sender,source,i,payloads[i]);await complete(sender,source);
 destination=await create(receiver,files);for(let i=0;i<files.length;i++){const data=await request(sender.origin+'/api/transfers/'+source.code+'/files/'+source.files[i].id);assert.equal(data.status,200);await put(receiver,destination,i,data.body);}await complete(receiver,destination);
 const hashes=[];for(let i=0;i<files.length;i++){const response=await request(receiver.origin+'/api/transfers/'+destination.code+'/files/'+destination.files[i].id);assert.equal(response.status,200);const actual=await digest(response.body),expected=createHash('sha256').update(payloads[i]).digest('hex');assert.equal(actual.sha256,expected);assert.equal(actual.size,files[i].size);hashes.push({name:files[i].name,size:actual.size,source_sha256:expected,destination_sha256:actual.sha256});}
 return {files:101,size:files.reduce((n,f)=>n+f.size,0),hashes,concurrency:'Single FlowDrop batch, streamed files serially as baseline; no simultaneous-upload feature claimed'};
 }finally{await revoke(receiver,destination);await revoke(sender,source);}}
async function denied(host){const files=JSON.stringify({files:[{name:'denied.bin',size:0}]});for(const headers of [{},{[host.header]:'incorrect'},{[host.header==='X-Local-Token'?'X-Desktop-Token':'X-Local-Token']:host.token}])assert.equal((await request(host.origin+'/api/transfers',{method:'POST',headers,body:files})).status,403);
 assert.equal((await localRequest(host,'/api/transfers',{method:'POST',headers:{Origin:'https://invalid.example'},body:files})).status,403);
 assert.equal((await localRequest(host,'/api/transfers',{method:'POST',body:JSON.stringify({files:[{name:'invalid.bin',size:-1}]})})).status,400);
 return {missing_capability:403,incorrect_capability:403,wrong_kind:403,foreign_origin:403,invalid_metadata:400};}
async function disconnect(host,percent){let session;try{
 const size=8*2**20;session=await create(host,[{name:'interrupted.bin',size}]);const url=new URL(host.origin);const socket=net.connect(Number(url.port),'127.0.0.1');socket.on('error',()=>{});await once(socket,'connect');
 socket.write('PUT /api/transfers/'+session.code+'/files/'+session.files[0].id+' HTTP/1.1\r\nHost: '+url.host+'\r\nX-Upload-Token: '+session.token+'\r\nContent-Length: '+size+'\r\nConnection: close\r\n\r\n');
 socket.setTimeout(15000,()=>socket.destroy(new Error('Bounded interruption socket timeout')));socket.resume();
 let written=0;const target=size*percent/100;while(written<target){const chunk=block.subarray(0,Math.min(block.length,target-written));if(!socket.write(chunk))await once(socket,'drain');written+=chunk.length;}const closed=once(socket,'close');socket.end();await closed;
 const state=await request(host.origin+'/api/transfers/'+session.code);assert.equal(state.status,409);await state.arrayBuffer();
 const done=await request(host.origin+'/api/transfers/'+session.code+'/complete',{method:'POST',headers:{'X-Upload-Token':session.token}});assert.equal(done.status,409);await done.arrayBuffer();
 const data=await request(host.origin+'/api/transfers/'+session.code+'/files/'+session.files[0].id);assert.notEqual(data.status,200);await data.arrayBuffer();
 return {declared_size:size,bytes_written_to_socket:written,interruption_percent:percent,metadata_status:state.status,complete_status:done.status,file_status:data.status,no_false_completion:true};
 }finally{await revoke(host,session);}}

try{
 const {classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/CodeLookup.java','tests/HostHarness.java']);
 const fs=await statfs(harness.directory);if(full)assert.ok(Number(fs.bavail)*Number(fs.bsize)>=18*2**30,'Full engine matrix needs >=18GiB free disk; blocked rather than silently shrink test');
 const hosts=[];for(const [kind,index] of [['desktop',1],['android',1],['desktop',2],['android',2]]){
  const child=kind==='desktop'?harness.spawn(process.execPath,['scripts/dev.mjs','--host','127.0.0.1'],{env:{...process.env,PORT:'0',FLOWDROP_DESKTOP:'1',FLOWDROP_DESKTOP_NATIVE:'1',FLOWDROP_DISABLE_UPDATES:'1',FLOWDROP_DATA_DIR:path.join(harness.directory,kind+index),FLOWDROP_DEFAULT_RECEIVE_DIR:path.join(harness.directory,'saved'+index)},stdio:['ignore','pipe','pipe']}):harness.spawn(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.HostHarness',path.join(harness.directory,kind+index),path.join(root,'web')],{stdio:['ignore','pipe','pipe']});
  const host=await waitForHost(child,kind);host.kind=kind==='desktop'?'Windows Node engine on Linux':'Android Java engine on JVM';host.child=child;hosts.push(host);
 }
 const directions=[[hosts[0],hosts[1]],[hosts[1],hosts[0]],[hosts[0],hosts[2]],[hosts[1],hosts[3]]];
 for(let d=0;d<directions.length;d++){
  const [sender,receiver]=directions[d];
  for(const size of full?[0,1024,2**20,100*2**20,2**30,4*2**30+17]:[0,1024,2**20])await measure('A-D'+(d+1)+'-bytes-'+size,sender,receiver,()=>relay(sender,receiver,size,'Tệp 中文 😀 '+size+'.bin'));
  await measure('A-D'+(d+1)+'-batch-101',sender,receiver,()=>many(sender,receiver));
 }
 for(const [i,host] of hosts.slice(0,2).entries()){
  await measure('A-SEC-'+i,host,host,()=>denied(host));
  for(const percent of [25,50,75])await measure('A-DISCONNECT-'+i+'-'+percent,host,host,()=>disconnect(host,percent));
 }
 report.peak_rss_bytes={};for(let i=0;i<hosts.length;i++){const status=await readFile('/proc/'+hosts[i].child.pid+'/status','utf8');const rss=Number(status.match(/VmHWM:\s+(\d+)/)[1])*1024;assert.ok(rss>0&&rss<300*2**20,'Engine buffered data beyond 300MiB baseline');report.peak_rss_bytes[hosts[i].kind+' '+i]=rss;}
 report.status='PASS';report.exit_code=0;
}catch(error){report.status='FAIL';report.exit_code=1;report.error_type=error.name;process.exitCode=1;console.error('FAIL: protocol matrix; see sanitized matrix and command exit (no native/physical claim).');}
finally{await harness.writeReport('protocol-matrix.json',report);console.log(JSON.stringify({status:report.status,executed_cases:report.cases.length,passed_cases:report.cases.filter(c=>c.status==='PASS').length,full,native_e2e:'BLOCKED',physical_wifi:'NOT VERIFIED'}));await harness.cleanup();}
