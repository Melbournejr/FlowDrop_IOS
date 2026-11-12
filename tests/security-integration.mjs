import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir,networkInterfaces} from 'node:os';
import path from 'node:path';
import net from 'node:net';
import assert from 'node:assert/strict';
const tools='/workspace/flowdrop-build',jar=tools+'/downloads/json-test.jar',dir=await mkdtemp(path.join(tmpdir(),'flowdrop-security-')),children=[];
const compiled=path.join(dir,'java');await mkdir(compiled);
const build=spawnSync('java',['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',jar,'-d',compiled,'android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/TransferServer.java','tests/HostHarness.java'],{encoding:'utf8'});assert.equal(build.status,0,build.stderr);
function start(command,args,env={}){const child=spawn(command,args,{env:{...process.env,...env},stdio:['ignore','pipe','pipe']});children.push(child);return new Promise((resolve,reject)=>{let text='',errors='';const timeout=setTimeout(()=>reject(new Error('Startup timeout '+errors)),15000);child.stderr.on('data',b=>errors+=b);child.on('exit',c=>{clearTimeout(timeout);reject(new Error('Startup exit '+c+' '+errors));});child.stdout.on('data',b=>{text+=b;for(const line of text.split('\n'))try{let ready=JSON.parse(line.replace(/^FLOWDROP_READY /,''));if(ready.url||ready.port){clearTimeout(timeout);resolve({origin:ready.url?.replace(/\/$/,'')||'http://127.0.0.1:'+ready.port,token:ready.localToken||ready.token});return;}}catch{}});});}
async function raw(origin,head){const url=new URL(origin);return new Promise((resolve,reject)=>{const socket=net.createConnection({host:'127.0.0.1',port:url.port});let text='';socket.on('connect',()=>socket.write(head));socket.on('data',b=>text+=b);socket.on('end',()=>resolve(text));socket.on('close',()=>resolve(text));socket.on('error',reject);socket.setTimeout(15000,()=>{socket.destroy();reject(new Error('Request not terminated'));});});}
try{
 const [win,phone]=await Promise.all([start(process.execPath,['scripts/dev.mjs','--host','0.0.0.0'],{PORT:'0',FLOWDROP_DESKTOP:'1',FLOWDROP_DESKTOP_NATIVE:'1',FLOWDROP_DISABLE_UPDATES:'1',FLOWDROP_DATA_DIR:path.join(dir,'win')}),start('java',['-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.HostHarness',path.join(dir,'phone'),path.join(process.cwd(),'web')])]);
 assert.equal((await fetch(win.origin+'/api/desktop/settings')).status,403);
 assert.equal((await fetch(win.origin+'/api/desktop/settings',{headers:{'X-Desktop-Token':win.token}})).status,200);
 const iface=Object.values(networkInterfaces()).flat().find(i=>i?.family==='IPv4'&&!i.internal);
 for(const [name,peer,key] of [['Windows',win,'X-Desktop-Token'],['Android',phone,'X-Local-Token']]){
  const url=peer.origin+'/api/transfers',body=JSON.stringify({files:[{name:'file.txt',size:0}]});
  assert.equal((await fetch(url,{method:'POST',body})).status,403,name+' unauthorized session creation');
  assert.equal((await fetch(url,{method:'POST',body,headers:{[key]:'wrong'}})).status,403);
  const config=await(await fetch(peer.origin+'/api/config')).json();assert.equal(config.name,'FlowDrop');assert.ok(!JSON.stringify(config).includes(peer.token),'Capability exposed through discovery');
  const created=await fetch(url,{method:'POST',body,headers:{[key]:peer.token}});assert.equal(created.status,201,await created.clone().text());
  for(const headers of [{Origin:'https://evil.test'},{Origin:'null'},{'Sec-Fetch-Site':'cross-site'},{'Sec-Fetch-Site':'same-site'}])assert.equal((await fetch(peer.origin+'/api/config',{headers})).status,403,name+' browser guard '+JSON.stringify(headers));
  if(iface){const remote='http://'+iface.address+':'+new URL(peer.origin).port;assert.equal((await fetch(remote+'/api/transfers',{method:'POST',body,headers:{[key]:peer.token}})).status,403,name+' remote creation with known local token');}
  assert.match(await raw(peer.origin,'GET /api/config HTTP/1.1\r\nHost: rebind.test:'+new URL(peer.origin).port+'\r\n\r\n'),/^HTTP\/1\.1 403/,name+' hostile Host');
  const host=new URL(peer.origin).host;
  for(const request of ['GET /api/config HTTP/1.1\r\nHost: '+host+'\r\nHost: evil.test\r\n\r\n','POST /api/transfers HTTP/1.1\r\nHost: '+host+'\r\nContent-Length: 1\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n','GET http://evil.test/api/config HTTP/1.1\r\nHost: '+host+'\r\n\r\n'])assert.match(await raw(peer.origin,request),/^HTTP\/1\.1 400/,name+' ambiguous HTTP framing');
  console.log('PASS: '+name+' local capability, remote-write rejection, token privacy, cross-origin and DNS-rebinding guards, duplicate Host and CL/TE rejection.');
 }
 // Header timeout is absolute: bytes arriving slowly cannot keep a Java worker occupied forever.
 const host=new URL(phone.origin).host;const started=Date.now();const response=await raw(phone.origin,'GET /api/config HTTP/1.1\r\nHost: '+host+'\r\nX-Slow: unfinished');assert.match(response,/^HTTP\/1\.1 408/);assert.ok(Date.now()-started<13000);console.log('PASS: Android incomplete headers terminate within the absolute 10 second deadline.');
}finally{for(const child of children)child.kill();await Promise.all(children.map(c=>new Promise(r=>c.exitCode!==null?r():c.once('exit',r))));await rm(dir,{recursive:true,force:true});}
