// Regression: actual code-receive endpoint / production Java resolver with late discovery.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {advertiseFlowDrop} from '../scripts/discovery.mjs';
import {createHarness,waitForHost,javaCommand,localFetch,root} from './helpers/harness.mjs';
const harness=await createHarness('code-receive-114'),cases=[];let advert,timer;
const hash=b=>createHash('sha256').update(b).digest('hex');
try{
 const {classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/CodeLookup.java','tests/HostHarness.java','tests/CodeLookupLateHarness.java']);
 const desktopChild=harness.spawn(process.execPath,['scripts/dev.mjs','--host','0.0.0.0'],{env:{...process.env,PORT:'0',FLOWDROP_DESKTOP:'1',FLOWDROP_DESKTOP_NATIVE:'1',FLOWDROP_DISABLE_UPDATES:'1',FLOWDROP_DATA_DIR:path.join(harness.directory,'desktop'),FLOWDROP_DEFAULT_RECEIVE_DIR:path.join(harness.directory,'saved')},stdio:['ignore','pipe','pipe']});
 const phoneChild=harness.spawn(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.HostHarness',path.join(harness.directory,'phone'),path.join(root,'web')],{stdio:['ignore','pipe','pipe']});
 const [desktop,phone]=await Promise.all([waitForHost(desktopChild,'desktop'),waitForHost(phoneChild,'android')]);
 const bytes=[Buffer.alloc(0),Buffer.from('Nhận bằng mã — 中文 😀')];
 async function stage(host){const created=await localFetch(host,'/api/transfers',{method:'POST',body:JSON.stringify({files:bytes.map((b,i)=>({name:'Tệp '+i+'.txt',size:b.length,type:'text/plain'}))})});assert.equal(created.status,201);const s=await created.json();for(let i=0;i<bytes.length;i++){const r=await fetch(host.origin+'/api/transfers/'+s.code+'/files/'+s.files[i].id,{method:'PUT',headers:{'X-Upload-Token':s.token},body:bytes[i]});assert.equal(r.status,200);}assert.equal((await fetch(host.origin+'/api/transfers/'+s.code+'/complete',{method:'POST',headers:{'X-Upload-Token':s.token}})).status,200);return s;}
 const phoneShare=await stage(phone),desktopShare=await stage(desktop);
 // Desktop begins with no phone in its peer list. The real mDNS announcement arrives after the old 1.2s fixed wait.
 const config=await(await fetch(phone.origin+'/api/config')).json();
 timer=setTimeout(()=>{advert=advertiseFlowDrop({port:Number(new URL(phone.origin).port),deviceId:config.deviceId,deviceName:'Late phone',platform:'android'});},2200);
 const before=Date.now();const response=await localFetch(desktop,'/api/desktop/receive',{method:'POST',body:JSON.stringify({code:phoneShare.code.toLowerCase()})});
 const result=await response.json();let correct=false;
 if(response.status===200){correct=result.files.length===2;for(let i=0;i<2;i++)correct&&=hash(await readFile(result.files[i].path))===hash(bytes[i]);}
 cases.push({id:'CODE-ANDROID-TO-WINDOWS-COLD',status:response.status===200&&correct?'PASS':'FAIL',http_status:response.status,elapsed_ms:Date.now()-before,sha256:bytes.map(hash),download_exact:correct});
 let peerSeen=false;for(let i=0;i<100;i++){const r=await localFetch(desktop,'/api/desktop/peers',{method:'POST',body:'{}'});const p=await r.json();if(p.peers.some(v=>v.id===config.deviceId)){peerSeen=true;break;}await new Promise(resolve=>setTimeout(resolve,100));}assert.ok(peerSeen,'Test environment did not deliver the real late mDNS advertisement');cases[0].peer_visible_after_lookup=peerSeen;
 for(const [id,host,share] of [['CODE-WINDOWS-TO-ANDROID-COLD',desktop,desktopShare],['CODE-ANDROID-TO-ANDROID-COLD',phone,phoneShare]]){
  const child=spawnSync(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.CodeLookupLateHarness',host.origin,share.code],{encoding:'utf8',timeout:15000});let value;try{value=JSON.parse(child.stdout);}catch{}
  const exact=child.status===0&&value?.passed===true&&value.files.length===2&&value.files.every((f,i)=>f.size===bytes[i].length&&f.sha256===hash(bytes[i]));
  cases.push({id,status:exact?'PASS':'FAIL',exit_code:child.status,download_exact:exact,sha256:bytes.map(hash)});
 }
 const report={scope:'Real Node endpoint + production Java resolver, not physical device evidence',status:cases.every(c=>c.status==='PASS')?'PASS':'FAIL',cases};
 await harness.writeReport('code-receive-114.json',report);console.log(JSON.stringify(report,null,2));if(report.status!=='PASS')process.exitCode=1;
}finally{clearTimeout(timer);await advert?.stop();await harness.cleanup();}
