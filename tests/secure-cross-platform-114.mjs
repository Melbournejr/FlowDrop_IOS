import assert from 'node:assert/strict';
import {createHash,randomUUID} from 'node:crypto';
import {writeFile,mkdir,readFile} from 'node:fs/promises';
import {createInterface} from 'node:readline';
import {networkInterfaces} from 'node:os';
import path from 'node:path';
import {createHarness,waitForHost,localFetch,javaCommand} from './helpers/harness.mjs';
import {deviceVault} from '../scripts/device-security.mjs';
import {advertiseFlowDrop} from '../scripts/discovery.mjs';
const harness=await createHarness('secure-cross-114');let advert;
const hash=b=>createHash('sha256').update(b).digest('hex');
try{
 const {classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/DeviceSecurity.java','tests/SecureHostHarness.java']);
 const id=randomUUID(),phoneRoot=path.join(harness.directory,'phone');await mkdir(phoneRoot);await writeFile(path.join(phoneRoot,'device-id'),id);
 const vault=await deviceVault(harness.directory,id);await writeFile(path.join(harness.directory,'key.pem'),vault.value.key,{mode:0o600});await writeFile(path.join(harness.directory,'cert.pem'),vault.value.cert);
 const phoneChild=harness.spawn(javaCommand,['-Xmx128m','-cp',classpath,'app.flowdrop.mobile.SecureHostHarness',phoneRoot,path.join(harness.directory,'key.pem'),path.join(harness.directory,'cert.pem')],{stdio:['pipe','pipe','pipe']});const phone=await waitForHost(phoneChild,'android');
 const queue=[];const lines=createInterface({input:phoneChild.stdout});lines.on('line',line=>{const value=JSON.parse(line);queue.shift()?.(value);});const command=value=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('JVM driver timeout')),20000);queue.push(v=>{clearTimeout(timer);resolve(v);});phoneChild.stdin.write(JSON.stringify(value)+'\n');});
 const desktopChild=harness.spawn(process.execPath,['scripts/dev.mjs','--host','0.0.0.0'],{env:{...process.env,PORT:'0',FLOWDROP_LEGACY_HTTP:'0',FLOWDROP_DESKTOP:'1',FLOWDROP_DESKTOP_NATIVE:'1',FLOWDROP_DISABLE_UPDATES:'1',FLOWDROP_DATA_DIR:path.join(harness.directory,'desktop'),FLOWDROP_DEFAULT_RECEIVE_DIR:path.join(harness.directory,'saved')},stdio:['ignore','pipe','pipe']});const desktop=await waitForHost(desktopChild,'desktop');
 const address=Object.values(networkInterfaces()).flat().find(a=>a.family==='IPv4'&&!a.internal&&!a.address.startsWith('169.254.')).address;
 const phoneOrigin='http://'+address+':'+new URL(phone.origin).port,desktopOrigin='http://'+address+':'+new URL(desktop.origin).port;
 const phoneConfig=await(await fetch(phoneOrigin+'/api/config')).json(),desktopConfig=await(await fetch(desktopOrigin+'/api/config')).json();
 assert.ok(phoneConfig.secure&&desktopConfig.secure);
 assert.equal((await fetch(phoneOrigin+'/api/transfers/ABCDEFGH')).status,426,'Android defaults to rejecting LAN cleartext');
 assert.equal((await fetch(desktopOrigin+'/api/transfers/ABCDEFGH')).status,426,'Windows defaults to rejecting LAN cleartext');
 advert=advertiseFlowDrop({port:Number(new URL(phone.origin).port),deviceId:id,deviceName:'Secure phone',platform:'android'});
 for(let n=0;n<100;n++){const state=await(await localFetch(desktop,'/api/desktop/peers',{method:'POST',body:'{}'})).json();if(state.peers.some(p=>p.id===id))break;if(n===99)throw Error('Discovery timeout');await new Promise(r=>setTimeout(r,100));}
 const start=await localFetch(desktop,'/api/desktop/security/start',{method:'POST',body:JSON.stringify({peerId:id})});const state=await start.json();assert.equal(start.status,200,JSON.stringify(state));const pair=state.pairings[0];assert.match(pair.code,/^\d{6}$/);
 assert.ok((await command({op:'snapshot'})).pairings[0].code===pair.code,'Node/Java transcript/SAS must be identical');
 assert.equal((await localFetch(desktop,'/api/desktop/security/confirm',{method:'POST',body:JSON.stringify({id:pair.id,accept:true})})).status,200);
 await command({op:'confirm',id:pair.id,accept:true});
 for(let n=0;n<30;n++){const s=await(await localFetch(desktop,'/api/desktop/peers',{method:'POST',body:'{}'})).json();if(s.security.trusted.length)break;if(n===29)throw Error('Pair status timeout');await new Promise(r=>setTimeout(r,100));}
 assert.equal((await command({op:'observe',origin:desktopOrigin,config:desktopConfig})).ok,true);
 const bytes=Buffer.from('TLS ghép nối — 中文 😀');
 async function stage(h,payload=bytes){const r=await localFetch(h,'/api/transfers',{method:'POST',body:JSON.stringify({files:[{name:'TLS.txt',size:payload.length,type:'text/plain'}]})});assert.equal(r.status,201);const s=await r.json();assert.equal((await fetch(h.origin+'/api/transfers/'+s.code+'/files/'+s.files[0].id,{method:'PUT',headers:{'X-Upload-Token':s.token},body:payload})).status,200);assert.equal((await fetch(h.origin+'/api/transfers/'+s.code+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}})).status,200);return s;}
 const fromDesktop=await stage(desktop),fromPhone=await stage(phone);
 const secureDesktop='https://'+address+':'+desktopConfig.secure.port;
 const downloaded=await command({op:'request',url:secureDesktop+'/api/transfers/'+fromDesktop.code+'/files/'+fromDesktop.files[0].id});assert.equal(downloaded.status,200,JSON.stringify(downloaded));assert.equal(downloaded.sha256,hash(bytes));
 await command({op:'invalidateRemote'});const renewedDownload=await command({op:'request',url:secureDesktop+'/api/transfers/'+fromDesktop.code+'/files/'+fromDesktop.files[0].id});assert.equal(renewedDownload.status,200,JSON.stringify(renewedDownload));assert.equal(renewedDownload.sha256,hash(bytes));
 const received=await localFetch(desktop,'/api/desktop/receive',{method:'POST',body:JSON.stringify({code:fromPhone.code,peerId:id})});const result=await received.json();assert.equal(received.status,200,JSON.stringify(result));assert.equal(hash(await readFile(result.files[0].path)),hash(bytes));
 // Direct offers use the same authenticated TLS transport and explicit receive consent.
 await command({op:'expireSessions'});
 const offered=await localFetch(desktop,'/api/desktop/send-offer',{method:'POST',body:JSON.stringify({peerId:id,code:fromDesktop.code})});const offeredValue=await offered.json();assert.equal(offered.status,200,JSON.stringify(offeredValue));const pending=(await command({op:'offers'})).offers;assert.equal(pending.length,1);await command({op:'answer',id:pending[0].id,accept:false});
 await command({op:'invalidateRemote'});
 const reverse=await command({op:'send',origin:desktopOrigin,code:fromPhone.code});assert.ok(!reverse.error,reverse.error);
 const incoming=await(await localFetch(desktop,'/api/desktop/peers',{method:'POST',body:'{}'})).json();assert.equal(incoming.offers.length,1);
 const accepted=await localFetch(desktop,'/api/desktop/answer-offer',{method:'POST',body:JSON.stringify({id:incoming.offers[0].id,accept:true})});assert.equal(accepted.status,200);assert.equal(hash(await readFile((await accepted.json()).files[0].path)),hash(bytes));
 // A second production Java TLS engine, paired directly with the first one.
 const id2=randomUUID(),root2=path.join(harness.directory,'phone2');await mkdir(root2);await writeFile(path.join(root2,'device-id'),id2);const v2=await deviceVault(harness.directory,id2);await writeFile(path.join(harness.directory,'key2.pem'),v2.value.key,{mode:0o600});await writeFile(path.join(harness.directory,'cert2.pem'),v2.value.cert);
 const child2=harness.spawn(javaCommand,['-Xmx128m','-cp',classpath,'app.flowdrop.mobile.SecureHostHarness',root2,path.join(harness.directory,'key2.pem'),path.join(harness.directory,'cert2.pem')],{stdio:['pipe','pipe','pipe']});const phone2=await waitForHost(child2,'android'),q2=[];createInterface({input:child2.stdout}).on('line',line=>q2.shift()?.(JSON.parse(line)));const command2=b=>new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('JVM2 timeout')),20000);q2.push(v=>{clearTimeout(t);resolve(v);});child2.stdin.write(JSON.stringify(b)+'\n');});
 const origin2='http://'+address+':'+new URL(phone2.origin).port,cfg2=await(await fetch(origin2+'/api/config')).json();assert.equal((await command2({op:'observe',origin:phoneOrigin,config:phoneConfig})).ok,true);assert.equal((await command({op:'observe',origin:origin2,config:cfg2})).ok,true);
 const s2=await command2({op:'start',id});assert.ok(!s2.error,s2.error);const p2=s2.pairings[0];const remotePair=(await command({op:'snapshot'})).pairings.find(p=>p.id===p2.id);assert.ok(p2.code===remotePair.code,'Java pairing SAS must match');await command2({op:'confirm',id:p2.id,accept:true});await command({op:'confirm',id:p2.id,accept:true});assert.equal((await command2({op:'snapshot'})).trusted.length,1);
 const javaDownloaded=await command2({op:'request',url:'https://'+address+':'+phoneConfig.secure.port+'/api/transfers/'+fromPhone.code+'/files/'+fromPhone.files[0].id});assert.equal(javaDownloaded.status,200,JSON.stringify(javaDownloaded));assert.equal(javaDownloaded.sha256,hash(bytes));
 // Actual pinned-TLS bulk download keeps exact SHA and only bounded local timing samples.
 const bulkBytes=Buffer.alloc(2*1024*1024+17,0x5a),bulk=await stage(phone,bulkBytes);
 const bulkUrl='https://'+address+':'+phoneConfig.secure.port+'/api/transfers/'+bulk.code+'/files/'+bulk.files[0].id;
 for(let n=0;n<9;n++){const response=await command2({op:'request',url:bulkUrl});assert.equal(response.status,200);assert.equal(response.sha256,hash(bulkBytes));}
 const metrics=(await command({op:'sendStats'})).samples;assert.equal(metrics.length,8);
 const allowed=new Set(['bytesWritten','bodyWritten','tls','elapsedMs','diskReadMs','tlsWriteMs','bulkWrites','bufferBytes','tcpNoDelay','sendBufferBytes']);
 for(const sample of metrics){assert.equal(sample.bytesWritten,bulkBytes.length);assert.equal(sample.bodyWritten,true);assert.equal(sample.tls,true);assert.equal(sample.tcpNoDelay,true);assert.ok(sample.bufferBytes<=262144&&sample.bulkWrites>0);for(const key of ['elapsedMs','diskReadMs','tlsWriteMs'])assert.ok(Number.isSafeInteger(sample[key])&&sample[key]>=0);assert.ok(Object.keys(sample).every(key=>allowed.has(key)),'No identifiers/credentials in local body diagnostics');}
 console.log('PASS: pinned TLS bulk SHA, bounded local diagnostics and actual TCP_NODELAY; no physical throughput claim');
 // Compatibility is an explicit local capability action, never an automatic TLS fallback.
 assert.equal((await localFetch(desktop,'/api/desktop/security/legacy',{method:'POST',body:JSON.stringify({enabled:true})})).status,200);assert.equal((await fetch(desktopOrigin+'/api/transfers/'+fromDesktop.code)).status,200);
 assert.equal((await localFetch(desktop,'/api/desktop/security/legacy',{method:'POST',body:JSON.stringify({enabled:false})})).status,200);assert.equal((await fetch(desktopOrigin+'/api/transfers/'+fromDesktop.code)).status,426);
 const report={scope:'Real Node production endpoint and Java production TLS/transfer engine; not native OS/hardware',status:'PASS',cases:['LAN cleartext rejected by default on both hosts','Node initiates pairing with Java; both screen codes match','One-time two-sided confirmation persists session trust','Java pinned TLS download from Node: SHA-256 exact','Node pinned TLS code receive from Java: SHA-256 exact','Direct offers in both directions retain consent and exact saved bytes','Session loss on receiver restart renews once; Java GET/POST bodies remain exact','Java to Java pairing and pinned TLS download: SHA-256 exact']};await harness.writeReport('secure-cross-platform-114.json',report);console.log(JSON.stringify(report,null,2));
}finally{await advert?.stop();await harness.cleanup();}
