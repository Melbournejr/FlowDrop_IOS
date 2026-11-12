import {networkInterfaces} from 'node:os';
import {createHash} from 'node:crypto';
import {createInterface} from 'node:readline';
import http from 'node:http';
import dgram from 'node:dgram';
import path from 'node:path';
import assert from 'node:assert/strict';
import {startLanDiscovery,LAN_PORT,LAN_GROUP} from '../scripts/lan-discovery.mjs';
import {createHarness,javaCommand} from './helpers/harness.mjs';
const iface=Object.values(networkInterfaces()).flat().find(a=>a?.family==='IPv4'&&!a.internal&&!a.address.startsWith('169.254.'));
const harness=await createHarness('lan'),folder=harness.directory,servers=[],report=[];let nodeLan,sender,classpath;
async function phone(name){const child=harness.spawn(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.LanHostHarness',path.join(folder,name),iface.address],{stdio:['pipe','pipe','inherit']});const lines=createInterface({input:child.stdout})[Symbol.asyncIterator]();const next=async()=>{const line=await lines.next();assert.equal(line.done,false);const value=JSON.parse(line.value);assert.ok(!value.error,value.error);return value;};const ready=await next();return {...ready,command:async body=>{child.stdin.write(JSON.stringify(body)+'\n');return next();}};}
async function server(config){const server=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(config));});servers.push(server);await new Promise(r=>server.listen(0,'0.0.0.0',r));return server;}
async function until(check,label){const end=Date.now()+16000;while(Date.now()<end){if(await check())return;await new Promise(r=>setTimeout(r,200));}throw new Error(label);}
try{
 assert.ok(iface,'No LAN IPv4 interface');
 ({classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/LanDiscovery.java','android/src/app/flowdrop/mobile/DeviceLabel.java','tests/LanHostHarness.java']));
 const node=await server({name:'FlowDrop',deviceId:'windows-test',deviceName:'Windows LAN',platform:'windows',version:'1.9.0'});
 nodeLan=startLanDiscovery({deviceId:'windows-test',deviceName:'Windows LAN',port:node.address().port,interfaces:()=>[iface]});
 const [a,b]=await Promise.all([phone('phone-a'),phone('phone-b')]);
 await until(async()=>{const ap=(await a.command({action:'peers'})).peers,bp=(await b.command({action:'peers'})).peers;return ap.some(p=>p.id===b.id)&&ap.some(p=>p.id==='windows-test')&&bp.some(p=>p.id===a.id)&&bp.some(p=>p.id==='windows-test')&&nodeLan.peers().some(p=>p.id===a.id)&&nodeLan.peers().some(p=>p.id===b.id);},'Peers did not discover every other platform without mDNS');
 for(const p of [a,b]){const peers=(await p.command({action:'peers'})).peers;assert.equal(peers.length,2);assert.ok(!peers.some(x=>x.id===p.id));for(const item of peers){const config=await(await fetch(item.url+'/api/config')).json();assert.equal(config.deviceId,item.id);assert.ok(item.port>0);}}
 assert.equal(nodeLan.peers().length,2);report.push('Two production Java LAN engines and Node Windows engine each find both other devices over real UDP/TCP without mDNS; same-name phones remain distinct; self is excluded');
 // Rename during an open upload: same host, device ID and transfer survive.
 const bytes=Buffer.alloc(8193,77),share=await(await fetch(a.url+'api/transfers',{method:'POST',headers:{'X-Local-Token':a.localToken},body:JSON.stringify({files:[{name:'Đổi tên khi đang gửi.bin',size:bytes.length}]})})).json();let uploadControl;
 const upload=fetch(a.url+'api/transfers/'+share.code+'/files/'+share.files[0].id,{method:'PUT',headers:{'X-Upload-Token':share.token},body:new ReadableStream({start(c){uploadControl=c;c.enqueue(bytes.subarray(0,4096));}}),duplex:'half'});
 await new Promise(r=>setTimeout(r,200));await a.command({action:'rename',name:'Điện thoại mới 📱'});uploadControl.enqueue(bytes.subarray(4096));uploadControl.close();assert.equal((await upload).status,200);
 assert.equal((await fetch(a.url+'api/transfers/'+share.code+'/complete',{method:'POST',headers:{'X-Upload-Token':share.token}})).status,200);
 const saved=Buffer.from(await(await fetch(a.url+'api/transfers/'+share.code+'/files/'+share.files[0].id)).arrayBuffer());assert.equal(createHash('sha256').update(saved).digest('hex'),createHash('sha256').update(bytes).digest('hex'));
 await until(async()=>nodeLan.peers().some(p=>p.id===a.id&&p.name==='Điện thoại mới 📱')&&(await b.command({action:'peers'})).peers.some(p=>p.id===a.id&&p.name==='Điện thoại mới 📱'),'Android rename did not propagate across platforms');
 assert.equal((await(await fetch(a.url+'api/config')).json()).deviceId,a.id);report.push('Android friendly name updates in Node/Java lists without changing device ID or interrupting an active upload; exact SHA-256 preserved');
 const fake=await server({name:'Different app',deviceId:'fake-app'});sender=dgram.createSocket('udp4');await new Promise(r=>sender.bind(0,'0.0.0.0',r));sender.setMulticastInterface(iface.address);sender.setMulticastLoopback(true);
 for(const id of ['fake-app','spoofed-device']){const packet=Buffer.from(JSON.stringify({app:'flowdrop',discovery:1,kind:'query',id,name:'Fake',platform:'android',port:fake.address().port}));for(let i=0;i<3;i++)await new Promise((resolve,reject)=>sender.send(packet,LAN_PORT,LAN_GROUP,e=>e?reject(e):resolve()));}
 await new Promise(r=>setTimeout(r,1200));for(const p of [a,b])assert.equal((await p.command({action:'peers'})).peers.length,2);assert.equal(nodeLan.peers().length,2);report.push('Non-FlowDrop HTTP server and mismatched device IDs never enter device lists');
 await b.command({action:'stop'});await until(async()=>!(await a.command({action:'peers'})).peers.some(p=>p.id===b.id)&&!nodeLan.peers().some(p=>p.id===b.id),'Goodbye did not remove stopped phone');
 await b.command({action:'start'});await until(async()=>(await a.command({action:'peers'})).peers.some(p=>p.id===b.id)&&nodeLan.peers().some(p=>p.id===b.id),'Restarted phone not rediscovered');report.push('Device removal and automatic rediscovery after restart; actual dynamically assigned HTTP ports confirmed');
 await harness.writeReport('lan-discovery-verification-1.9.json',report);console.log(JSON.stringify(report,null,2));
}finally{try{nodeLan?.stop();sender?.close();for(const server of servers){server.closeAllConnections();await new Promise(r=>server.close(r));}}finally{await harness.cleanup();}}
