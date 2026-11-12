import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,mkdir,rm,readFile,writeFile,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import http from 'node:http';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {randomBytes,createHash} from 'node:crypto';
import {createInterface} from 'node:readline';
import {advertiseFlowDrop} from '../scripts/discovery.mjs';
const root=process.cwd(),tools='/workspace/flowdrop-build',jar=tools+'/downloads/json-test.jar',compiled=tools+'/peer-tests';await mkdir(compiled,{recursive:true});
const javac=spawnSync('java',['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',jar,'-d',compiled,'android/src/app/flowdrop/mobile/TransferClient.java','android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','tests/PeerHostHarness.java'],{encoding:'utf8'});assert.equal(javac.status,0,javac.stderr);
const localCapabilities=new Map();
const folder=await mkdtemp(path.join(tmpdir(),'flowdrop-peers-')),children=[],adverts=[],servers=[],report=[];
report.push=(...messages)=>{messages.forEach(m=>console.log('PASS: '+m));return Array.prototype.push.apply(report,messages);};
async function phone(name){const child=spawn('java',['-Xmx96m','-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.PeerHostHarness',path.join(folder,name),name],{stdio:['pipe','pipe','inherit']});children.push(child);const lines=createInterface({input:child.stdout})[Symbol.asyncIterator]();const next=async()=>{const line=await lines.next();assert.equal(line.done,false);const value=JSON.parse(line.value);assert.ok(!value.error,value.error);return value;};const {url,localToken}=await next();localCapabilities.set(url,localToken);return {url,command:async command=>{child.stdin.write(JSON.stringify(command)+'\n');return next();}};}
async function json(url,body,token){const r=await fetch(url,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(localCapabilities.get(new URL(url).origin+'/')?{'X-Local-Token':localCapabilities.get(new URL(url).origin+'/')}:{}),...(token?{'X-Desktop-Token':token}:{})},body:body?JSON.stringify(body):undefined});const value=await r.json();assert.ok(r.ok,JSON.stringify(value));return value;}
async function session(url,length=1024*1024+17){const bytes=randomBytes(length),s=await json(url+'api/transfers',{files:[{name:'Ảnh từ Wi-Fi.bin',size:bytes.length},{name:'rỗng.txt',size:0}]});for(let i=0;i<s.files.length;i++){const r=await fetch(url+'api/transfers/'+s.code+'/files/'+s.files[i].id,{method:'PUT',headers:{'X-Upload-Token':s.token},body:i===0?bytes:Buffer.alloc(0)});assert.equal(r.status,200);}await fetch(url+'api/transfers/'+s.code+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}});return {s,bytes};}
const hash=b=>createHash('sha256').update(b).digest('hex');
try{
 const desktop=spawn(process.execPath,['scripts/dev.mjs','--host','0.0.0.0'],{env:{...process.env,PORT:'0',FLOWDROP_DATA_DIR:path.join(folder,'windows')},stdio:['ignore','pipe','inherit']});children.push(desktop);
 const win=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Windows host timeout')),15000);desktop.stdout.on('data',b=>{const m=b.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]+'/');}});});
 const [a,b]=await Promise.all([phone('Android-A'),phone('Android-B')]);
 const cfg=await json(a.url+'api/config');adverts.push(advertiseFlowDrop({port:Number(new URL(a.url).port),deviceName:'Android-A',deviceId:cfg.deviceId,platform:'android'}));
 const settings=await json(win+'api/desktop/settings'),token=settings.token,save=path.join(folder,'saved');await json(win+'api/desktop/settings',{directory:save,autoSave:true},token);
 let peers=[];for(let i=0;i<120;i++){peers=(await json(win+'api/desktop/peers',{rescan:true},token)).peers;if(peers.some(p=>p.id===cfg.deviceId))break;await new Promise(r=>setTimeout(r,100));}
 assert.equal(peers.filter(p=>p.id===cfg.deviceId).length,1,'Windows did not discover Android advertisement');const ownConfig=await json(win+'api/config');assert.ok(!peers.some(p=>p.id===ownConfig.deviceId));
 // Real desktop selection endpoint routes to a discovered device; no address or code input by receiver.
 const first=await session(win,8*1024*1024+17);const offered=await json(win+'api/desktop/send-offer',{peerId:cfg.deviceId,code:first.s.code},token);
 const pending=(await a.command({action:'list'})).offers;assert.equal(pending.length,1);assert.equal(pending[0].count,2);
 assert.equal(await readdir(save).catch(()=>[]).then(x=>x.length),0,'Offer wrote a file before consent');
 const accepted=(await a.command({action:'answer',id:pending[0].id,accept:true})).accepted;
 await assert.rejects(a.command({action:'finish',id:accepted.id}));
 const before=(await json(win+'api/desktop/peers',{},token)).sessions.find(s=>s.id===offered.sessionId);assert.notEqual(before.state,'completed');
 let receivingDone=false;const receiving=a.command({action:'receive',offer:accepted,delay:20}).finally(()=>receivingDone=true);let sawProgress=false,lastBytes=0;
 while(!receivingDone){const state=(await json(win+'api/desktop/peers',{},token)).sessions.find(s=>s.id===offered.sessionId);assert.ok(state.bytes>=lastBytes,'Progress moved backwards');lastBytes=state.bytes;if(state.state==='transferring'&&state.bytes>0&&state.bytes<state.size)sawProgress=true;await new Promise(r=>setTimeout(r,100));}
 const receivedPaths=(await receiving).files;assert.equal(hash(await readFile(receivedPaths[0])),hash(first.bytes));assert.ok(sawProgress,'Windows sender never saw Android receiver progress');
 for(let i=0;i<40;i++){const state=(await json(win+'api/desktop/peers',{},token)).sessions.find(s=>s.id===offered.sessionId);if(state.state==='completed'){assert.equal(state.filesDone,2);assert.equal(state.bytes,first.bytes.length);break;}await new Promise(r=>setTimeout(r,100));if(i===39)assert.fail('Sender did not learn receiver completion');}
 report.push('Sender sees pending, live increasing receiver bytes, and completion only after all committed files; premature completion rejected');
 report.push('Windows discovers Android once, selects peer, sends offer; Android accepts and downloads exact bytes');
 const codeShare=await session(a.url);const byCode=await json(win+'api/desktop/receive',{code:codeShare.s.code.slice(0,4)+' '+codeShare.s.code.slice(4)},token);assert.equal(hash(await readFile(byCode.files[0].path)),hash(codeShare.bytes));assert.equal((await readFile(byCode.files[1].path)).length,0);assert.ok((await json(win+'api/desktop/peers',{},token)).sessions.some(s=>s.code===codeShare.s.code&&s.state==='completed'));for(const file of byCode.files)await rm(file.path);report.push('Global code receive finds the Android host without selecting it, saves exact bytes and empty file, and tracks completion');
 const second=await session(a.url);await a.command({action:'send',target:win,code:second.s.code});let inbox=(await json(win+'api/desktop/peers',{},token)).offers;assert.equal(inbox.length,1);assert.equal(await readdir(save).catch(()=>[]).then(x=>x.length),0);
 const saved=await json(win+'api/desktop/answer-offer',{id:inbox[0].id,accept:true},token);assert.equal(saved.files.length,2);assert.equal(hash(await readFile(saved.files[0].path)),hash(second.bytes));assert.equal((await readFile(saved.files[1].path)).length,0);report.push('Android native client sends offer; Windows consent streams into configured folder, exact SHA-256 and empty file');
 for(let i=0;i<40;i++){const list=(await a.command({action:'sessions'})).sessions;const state=list.find(s=>s.direction==='send'&&s.code===second.s.code);if(state?.state==='completed'){assert.equal(state.filesDone,2);break;}await new Promise(r=>setTimeout(r,100));if(i===39)assert.fail('Android sender did not see Windows save confirmation');}
 await a.command({action:'send',target:b.url,code:second.s.code});const incoming=(await b.command({action:'list'})).offers[0];assert.ok(incoming);await b.command({action:'answer',id:incoming.id,accept:false});assert.equal((await b.command({action:'list'})).offers.length,0);report.push('Android to Android request and rejection');
 await a.command({action:'send',target:b.url,code:second.s.code});const again=(await b.command({action:'list'})).offers[0],received=(await b.command({action:'answer',id:again.id,accept:true})).accepted;const phoneSaved=await b.command({action:'receive',offer:received});assert.equal(hash(await readFile(phoneSaved.files[0])),hash(second.bytes));report.push('Android to Android consent and exact file bytes');
 const broken=await session(a.url);await a.command({action:'send',target:b.url,code:broken.s.code});const doomed=(await b.command({action:'list'})).offers[0],doomedOffer=(await b.command({action:'answer',id:doomed.id,accept:true})).accepted;await assert.rejects(b.command({action:'receive',offer:doomedOffer,failAfter:65536}));
 for(let i=0;i<40;i++){const state=(await a.command({action:'sessions'})).sessions.find(s=>s.direction==='send'&&s.code===broken.s.code);if(state?.state==='failed'){assert.ok(state.filesDone<2);break;}await new Promise(r=>setTimeout(r,100));if(i===39)assert.fail('Sender did not see failed receive');}report.push('Android sender learns peer failure; interrupted session never reports complete');
 // Exercise actual Windows disk writes over a deliberately slow HTTP source.
 const slowBytes=randomBytes(4*1024*1024+17),slowId=randomUUID(),emptyId=randomUUID();let cutStream=false;
 const slow=http.createServer(async(req,res)=>{
  if(req.url==='/api/config'){res.end(JSON.stringify({name:'FlowDrop',deviceId:'slow-peer',deviceName:'Thiết bị chậm'}));return;}
  if(req.url==='/api/transfers/ABCDEFGH'){res.end(JSON.stringify({code:'ABCDEFGH',files:[{id:slowId,name:'slow.bin',size:slowBytes.length},{id:emptyId,name:'slow-empty.txt',size:0}]}));return;}
  if(req.url==='/api/transfers/ABCDEFGH/files/'+emptyId){res.writeHead(200,{'Content-Length':'0'});res.end();return;}
  if(req.url==='/api/transfers/ABCDEFGH/files/'+slowId){res.writeHead(200,{'Content-Length':String(slowBytes.length)});for(let offset=0;offset<slowBytes.length;offset+=65536){if(res.destroyed)return;if(cutStream&&offset>=131072){res.destroy();return;}if(!res.write(slowBytes.subarray(offset,offset+65536)))await new Promise(resolve=>{const done=()=>{res.off('drain',done);res.off('close',done);resolve();};res.once('drain',done);res.once('close',done);});await new Promise(r=>setTimeout(r,25));}res.end();return;}
  res.writeHead(404);res.end();
 });servers.push(slow);await new Promise(r=>slow.listen(0,'127.0.0.1',r));
 const localConfig=await json(win+'api/config'),secret=randomUUID();
 let slowOffer=await json(win+'api/offers',{port:slow.address().port,deviceId:'slow-peer',code:'ABCDEFGH',offerKey:localConfig.offerKey,statusToken:secret});
 assert.equal((await fetch(win+'api/offers/status',{method:'POST',body:JSON.stringify({id:slowOffer.id,token:'wrong'})})).status,403);
 let saveDone=false;const slowSave=json(win+'api/desktop/answer-offer',{id:slowOffer.id,accept:true},token).finally(()=>saveDone=true);let sawWindowsProgress=false;
 while(!saveDone){const state=(await json(win+'api/desktop/peers',{},token)).sessions.find(s=>s.id===slowOffer.id);if(state.state==='transferring'&&state.bytes>0&&state.bytes<state.size){sawWindowsProgress=true;assert.ok(state.filesDone<2);}await new Promise(r=>setTimeout(r,80));}
 const slowResult=await slowSave;assert.ok(sawWindowsProgress,'Windows receiver did not report streamed progress');assert.equal(hash(await readFile(slowResult.files[0].path)),hash(slowBytes));let slowStatus=await json(win+'api/offers/status',{id:slowOffer.id,token:secret});assert.equal(slowStatus.state,'completed');assert.equal(slowStatus.filesDone,2);
 cutStream=true;slowOffer=await json(win+'api/offers',{port:slow.address().port,deviceId:'slow-peer',code:'ABCDEFGH',offerKey:localConfig.offerKey,statusToken:randomUUID()});
 // Use a fresh directory so the receipt cache cannot skip the interrupted download.
 await json(win+'api/desktop/settings',{directory:path.join(folder,'interrupted-save'),autoSave:true},token);
 await assert.rejects(json(win+'api/desktop/answer-offer',{id:slowOffer.id,accept:true},token));const failure=(await json(win+'api/desktop/peers',{},token)).sessions.find(s=>s.id===slowOffer.id);assert.equal(failure.state,'failed');assert.ok(failure.filesDone<2);assert.deepEqual(await readdir(path.join(folder,'interrupted-save')),[]);report.push('Windows receiver publishes live byte progress, waits for permanent commit before completion, and reports stream interruption with partial-file cleanup');
 const invalid={deviceId:cfg.deviceId,port:Number(new URL(a.url).port),code:second.s.code,offerKey:'wrong'};
 assert.equal((await fetch(win+'api/offers',{method:'POST',body:JSON.stringify(invalid)})).status,400);
 assert.equal((await fetch(a.url+'api/offers',{method:'POST',body:JSON.stringify(invalid)})).status,403);
 assert.equal((await fetch(win+'api/desktop/answer-offer',{method:'POST',body:'{}'})).status,403);
 for(const url of [win,a.url])assert.equal((await fetch(url+'api/offers',{method:'POST',headers:{Origin:'https://foreign.test'},body:JSON.stringify(invalid)})).status,403);report.push('Invalid offer capability, remote consent and foreign-origin requests blocked');
 await adverts[0].stop();for(let i=0;i<50;i++){peers=(await json(win+'api/desktop/peers',{},token)).peers;if(!peers.some(p=>p.id===cfg.deviceId))break;await new Promise(r=>setTimeout(r,100));}assert.ok(!peers.some(p=>p.id===cfg.deviceId),'Stopped Android remained in peer list');report.push('Goodbye removes offline device automatically');
 await writeFile(tools+'/peer-verification-1.9.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{for(const server of servers){server.closeAllConnections();await new Promise(r=>server.close(r));}for(const advert of adverts)await advert.stop();for(const child of children)child.kill();await Promise.all(children.map(c=>new Promise(r=>c.exitCode!==null?r():c.once('exit',r))));await rm(folder,{recursive:true,force:true});}
