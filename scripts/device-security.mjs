// LAN device identity is separate from the APK/EXE update signing identity.
import {createHash,createHmac,randomBytes,X509Certificate,timingSafeEqual} from 'node:crypto';
import https from 'node:https';
import {checkServerIdentity} from 'node:tls';
import {spawnSync} from 'node:child_process';
import {readFile,writeFile,rename,mkdtemp,rm} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
export const digest=value=>createHash('sha256').update(value).digest('hex');
export const identityName=id=>'flowdrop-'+digest(id).slice(0,24)+'.local';
const random=()=>randomBytes(32).toString('hex');
const same=(a,b)=>typeof a==='string'&&typeof b==='string'&&a.length===b.length&&Buffer.byteLength(a)===Buffer.byteLength(b)&&timingSafeEqual(Buffer.from(a),Buffer.from(b));
const commit=(transcript,nonce)=>digest(JSON.stringify([transcript,nonce]));
const sas=(transcript,a,b)=>String(parseInt(digest(JSON.stringify([transcript,a,b])).slice(0,8),16)%1000000).padStart(6,'0');
function certificate(value,id){
 const cert=new X509Certificate(Buffer.from(value,'base64'));
 if(cert.raw.length>8192||cert.issuer!==cert.subject||!cert.verify(cert.publicKey)||!cert.checkHost(identityName(id))||Date.parse(cert.validFrom)>Date.now()||Date.parse(cert.validTo)<Date.now()||cert.publicKey.asymmetricKeyType!=='rsa'||cert.publicKey.asymmetricKeyDetails.modulusLength<2048)throw Error('Danh tính TLS không hợp lệ.');
 return {pem:cert.toString(),fingerprint:digest(cert.raw),certificate:cert.raw.toString('base64')};
}
function powershell(body){
 const script=fileURLToPath(new URL('./device-vault.ps1',import.meta.url));
 const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',script],{input:JSON.stringify(body),encoding:'utf8',windowsHide:true,maxBuffer:1024*1024,timeout:60000});
 if(r.status!==0){const code=r.stderr?.match(/FLOWDROP_VAULT_ERROR=([A-Za-z0-9_.,:-]{1,180})/)?.[1];throw Error('Không mở được kho danh tính thiết bị Windows.'+(code?' ['+code+']':''));}return r.stdout.trim();
}
export async function deviceVault(directory,id){
 if(process.platform==='win32'){
  const file=path.join(directory,'device-transport.dpapi');let value;
  try{value=JSON.parse(powershell({operation:'open',value:await readFile(file,'utf8')}));}catch(error){if(error.code!=='ENOENT')throw error;value={...JSON.parse(powershell({operation:'create',name:identityName(id)})),trusted:{}};}
  let tail=Promise.resolve();const save=()=>{const snapshot=JSON.stringify(value);const operation=async()=>{const sealed=powershell({operation:'seal',value:snapshot});await writeFile(file+'.tmp',sealed,{mode:0o600});await rename(file+'.tmp',file);};const pending=tail.then(operation,operation);tail=pending.catch(()=>{});return pending;};await save();return {value,save};
 }
 // Non-Windows engine tests have no persistent private keys; no plaintext fallback vault.
 const scratch=await mkdtemp(path.join(tmpdir(),'flowdrop-test-identity-'));
 try{
  const keyFile=path.join(scratch,'private.pem'),certFile=path.join(scratch,'public.pem');
  const r=spawnSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','30','-subj','/CN='+identityName(id),'-addext','basicConstraints=critical,CA:FALSE','-addext','keyUsage=critical,digitalSignature,keyEncipherment','-addext','extendedKeyUsage=serverAuth','-keyout',keyFile,'-out',certFile],{encoding:'utf8',maxBuffer:1024*1024,timeout:30000});
  if(r.status!==0)throw Error('Không tạo được danh tính TLS tạm cho engine test.');
  const key=await readFile(keyFile,'utf8'),cert=await readFile(certFile,'utf8');
  return {value:{key,cert,certificate:new X509Certificate(cert).raw.toString('base64'),trusted:{}},save:async()=>{}};
 }finally{await rm(scratch,{recursive:true,force:true});}
}
export class DeviceSecurity {
 constructor({id,name,vault}){Object.assign(this,{id,name,vault});this.identity=certificate(vault.value.certificate,id);this.trusted=vault.value.trusted;this.pairs=new Map();this.candidates=new Map();this.nonces=new Map();this.sessions=new Map();this.remoteSessions=new Map();this.attempts=new Map();this.legacy=false;this.proposals=new Map();this.active=new Map();}
 tlsOptions(){const v=this.vault.value;return {minVersion:'TLSv1.2',...(v.pfx?{pfx:Buffer.from(v.pfx,'base64'),passphrase:v.passphrase}:{key:v.key,cert:v.cert})};}
 config(port){this.listenPort=port;return {protocol:2,port,certificate:this.identity.certificate,fingerprint:this.identity.fingerprint};}
 candidate(id,origin,certValue,name){
  if(!/^[a-zA-Z0-9-]{1,100}$/.test(id)||id===this.id)throw Error('Thiết bị không hợp lệ.');
  const c={id,origin:new URL(origin).origin,name:String(name||'Thiết bị').replace(/[\x00-\x1f\x7f]/g,' ').slice(0,100),...certificate(certValue,id)};
  if(new URL(c.origin).protocol!=='https:')throw Error('Cần kết nối TLS.');
  if(this.trusted[id]&&this.trusted[id].fingerprint!==c.fingerprint)throw Error('Danh tính thiết bị đã đổi. Kiểm tra và xóa ghép nối cũ trước.');
  if(this.candidates.size>=128&&!this.candidates.has(id))this.candidates.delete(this.candidates.keys().next().value);this.candidates.set(id,c);return c;
 }
 async discover(peer,config){if(config.deviceId!==peer.id||config.name!=='FlowDrop')throw Error('Không xác minh được thiết bị.');if(!config.secure){if(this.legacy)return peer;throw Error('Thiết bị dùng FlowDrop cũ. Bật tương thích có cảnh báo hoặc cập nhật.');}const origin=new URL(peer.url);origin.protocol='https:';origin.port=String(config.secure.port);const c=this.candidate(peer.id,origin.origin,config.secure.certificate,config.deviceName);return {...peer,url:c.origin,secure:true,trusted:!!this.trusted[c.id]};}
 prune(){const now=Date.now();for(const [id,p] of this.pairs)if(p.until<now)this.pairs.delete(id);for(const map of [this.nonces,this.sessions,this.attempts,this.proposals])for(const [k,v] of map)if((v.until||v)<now)map.delete(k);}
 snapshot(){this.prune();return {fingerprint:this.identity.fingerprint,legacy:this.legacy,trusted:Object.entries(this.trusted).map(([id,t])=>({id,name:t.name,fingerprint:t.fingerprint})),pairings:[...this.pairs].map(([id,p])=>({id,name:p.peer.name,code:p.code||'',direction:p.direction,confirmed:!!p.local,complete:!!p.complete}))};}
 track(id,socket){if(!this.active.has(id))this.active.set(id,new Set());if(this.active.get(id).has(socket))return;this.active.get(id).add(socket);socket.once('close',()=>{this.active.get(id)?.delete(socket);if(!this.active.get(id)?.size)this.active.delete(id);});}
 async forget(id){delete this.trusted[id];for(const socket of this.active.get(id)||[])socket.destroy();this.active.delete(id);for(const [key,s] of this.sessions)if(s.id===id)this.sessions.delete(key);this.remoteSessions.delete(id);for(const [key,p] of this.pairs)if(p.peer.id===id)this.pairs.delete(key);await this.vault.save();}
 transcript(a,b){return JSON.stringify(['FlowDropPair1',a.id,a.fingerprint,b.id,b.fingerprint]);}
 async start(id){this.prune();const peer=this.candidates.get(id);if(!peer)throw Error('Tìm lại thiết bị trước khi ghép nối.');const nonce=random(),transcript=this.transcript({id:this.id,...this.identity},peer);
  this.proposals.set(commit(transcript,nonce),{until:Date.now()+120000,fingerprint:peer.fingerprint});
  const r=await this.json(peer,'/api/secure/pair/start',{id:this.id,name:this.name,certificate:this.identity.certificate,tlsPort:this.listenPort,commit:commit(transcript,nonce)},false);
  if(!/^[a-f0-9]{64}$/.test(r.id)||!/^[a-f0-9]{64}$/.test(r.commit))throw Error('Phản hồi ghép nối không hợp lệ.');
  const revealed=await this.json(peer,'/api/secure/pair/reveal',{id:r.id,nonce},false);if(!/^[a-f0-9]{64}$/.test(revealed.nonce)||!same(commit(transcript,revealed.nonce),r.commit))throw Error('Cam kết ghép nối không khớp.');
  this.pairs.set(r.id,{peer,nonce,transcript,code:sas(transcript,nonce,revealed.nonce),until:Date.now()+120000,direction:'outgoing'});return this.snapshot();
 }
 async confirm(id,accept){this.prune();const p=this.pairs.get(id);if(!p)throw Error('Ghép nối đã hết hạn.');if(!accept){this.pairs.delete(id);return this.snapshot();}if(!p.code)throw Error('Chưa có mã xác nhận.');p.local=true;await this.refresh();return this.snapshot();}
 async refresh(){for(const [id,p] of this.pairs)if(p.direction==='outgoing'&&p.local&&!p.complete&&!p.polling){p.polling=true;try{const r=await this.json(p.peer,'/api/secure/pair/status',{id,nonce:p.nonce,confirmed:true},false);if(r.confirmed&&/^[a-f0-9]{64}$/.test(r.secret)){this.trusted[p.peer.id]={...p.peer,secret:r.secret};await this.vault.save();p.complete=true;}}finally{p.polling=false;}}}
 async pairRoute(route,body,address){this.prune();
  if(route.endsWith('/prove')){const p=this.proposals.get(body.commit);if(!p||p.fingerprint!==body.targetFingerprint)throw Error('Không có đề nghị ghép nối tương ứng.');return {commit:body.commit};}
  if(route.endsWith('/start')){
   const n=this.attempts.get(address)||{until:Date.now()+300000,count:0};if(++n.count>3||this.pairs.size>=20)throw Error('Quá nhiều lần ghép nối. Chờ 5 phút.');if(this.attempts.size>=512&&!this.attempts.has(address))throw Error('Có quá nhiều yêu cầu.');this.attempts.set(address,n);
   const peer={id:body.id,name:String(body.name||'Thiết bị').replace(/[\x00-\x1f\x7f]/g,' ').slice(0,100),...certificate(body.certificate,body.id)};if(peer.id===this.id||!/^[a-f0-9]{64}$/.test(body.commit))throw Error('Ghép nối không hợp lệ.');
   if(this.trusted[peer.id])throw Error('Thiết bị đã tin cậy. Xóa ghép nối cũ trên cả hai máy trước khi ghép lại.');
   if(!Number.isInteger(body.tlsPort)||body.tlsPort<1||body.tlsPort>65535)throw Error('Cổng TLS không hợp lệ.');
   const host=String(address).replace(/^::ffff:/,'');if(!/^\d{1,3}(?:\.\d{1,3}){3}$/.test(host))throw Error('Cần địa chỉ Wi-Fi IPv4.');
   const proof=await this.json({...peer,origin:'https://'+host+':'+body.tlsPort},'/api/secure/pair/prove',{commit:body.commit,targetFingerprint:this.identity.fingerprint},false);
   if(proof.commit!==body.commit)throw Error('Không chứng minh được danh tính thiết bị gửi.');
   const id=random(),nonce=random(),transcript=this.transcript(peer,{id:this.id,...this.identity});this.pairs.set(id,{peer,nonce,transcript,commit:body.commit,direction:'incoming',until:Date.now()+120000});return {id,commit:commit(transcript,nonce)};
  }
  const p=this.pairs.get(body.id);if(!p||p.direction!=='incoming'||!/^[a-f0-9]{64}$/.test(body.nonce)||!same(commit(p.transcript,body.nonce),p.commit))throw Error('Ghép nối đã hết hạn hoặc không hợp lệ.');
  if(route.endsWith('/reveal')){p.remoteNonce=body.nonce;p.code=sas(p.transcript,body.nonce,p.nonce);return {nonce:p.nonce};}
  if(!route.endsWith('/status')||!p.code||!same(p.remoteNonce,body.nonce))throw Error('Ghép nối không hợp lệ.');
  if(p.local&&body.confirmed===true){if(!p.secret)p.secret=random();this.trusted[p.peer.id]={...p.peer,secret:p.secret};await this.vault.save();p.complete=true;return {confirmed:true,secret:p.secret};}return {confirmed:false};
 }
 signature(secret,method,route,time,nonce,token){return createHmac('sha256',Buffer.from(secret,'hex')).update(JSON.stringify(['FlowDropRequest1',method,route,String(time),nonce,token])).digest('hex');}
 headers(id,method,route,token=''){const trust=this.trusted[id];if(!trust)throw Error('Ghép nối thiết bị trước khi gửi hoặc nhận mã.');const time=String(Date.now()),nonce=random();return {'x-fd-id':this.id,'x-fd-time':time,'x-fd-nonce':nonce,'x-fd-session':token,'x-fd-mac':this.signature(trust.secret,method,route,time,nonce,token)};}
 authorize(method,route,h,session=true){this.prune();const id=h['x-fd-id'],trust=this.trusted[id],time=h['x-fd-time'],nonce=h['x-fd-nonce'],token=h['x-fd-session']||'';
  if(!trust||!/^\d{13}$/.test(time||'')||Math.abs(Date.now()-Number(time))>120000||!/^[a-f0-9]{64}$/.test(nonce||'')||this.nonces.has(id+nonce)||!same(h['x-fd-mac'],this.signature(trust.secret,method,route,time,nonce,token)))throw Error('Không có quyền truy cập thiết bị.');
  if(session&&(!this.sessions.has(token)||this.sessions.get(token).id!==id))throw Error('Phiên bảo mật đã hết hạn.');if(this.nonces.size>=4096)throw Error('Có quá nhiều yêu cầu bảo mật.');this.nonces.set(id+nonce,Date.now()+240000);return id;
 }
 session(h){const id=this.authorize('POST','/api/secure/session',h,false);if(this.sessions.size>=512)throw Error('Có quá nhiều phiên.');const token=random(),until=Date.now()+600000;this.sessions.set(token,{id,until});return {token,until};}
 async request(peer,route,{method='GET',body,authenticated=true,signal}={}){
  let headers={};if(authenticated){let s=this.remoteSessions.get(peer.id);if(!s||s.until<Date.now()+30000){s=await this.json(peer,'/api/secure/session',{},false,this.headers(peer.id,'POST','/api/secure/session'));if(!/^[a-f0-9]{64}$/.test(s.token)||!Number.isSafeInteger(s.until)||s.until>Date.now()+660000)throw Error('Phiên bảo mật không hợp lệ.');this.remoteSessions.set(peer.id,s);}headers=this.headers(peer.id,method,route,s.token);}
  return this.raw(peer,route,{method,body,headers,signal});
 }
 raw(peer,route,{method='GET',body,headers={},signal}={}){return new Promise((resolve,reject)=>{
   const url=new URL(route,peer.origin);if(url.origin!==peer.origin||url.protocol!=='https:')return reject(Error('Không chuyển tiếp danh tính sang địa chỉ khác.'));
   const bytes=body===undefined?undefined:Buffer.from(JSON.stringify(body));
   const request=https.request(url,{agent:false,method,headers:{...headers,...(bytes?{'Content-Type':'application/json','Content-Length':bytes.length}:{})},ca:peer.pem,rejectUnauthorized:true,minVersion:'TLSv1.2',servername:identityName(peer.id),checkServerIdentity:(_name,cert)=>{const error=checkServerIdentity(identityName(peer.id),cert);return error||(!same(digest(cert.raw),peer.fingerprint)?Error('Danh tính TLS không khớp.'):undefined);},signal},response=>{clearTimeout(timer);response.setTimeout(120000,()=>response.destroy(Error('Mất kết nối với thiết bị.')));resolve(response);});
   request.once('socket',socket=>this.track(peer.id,socket));
   const timer=setTimeout(()=>request.destroy(Error('Thiết bị không phản hồi.')),8000);request.once('error',e=>{clearTimeout(timer);reject(e);});if(bytes)request.write(bytes);request.end();
  });}
 async json(peer,route,body,authenticated=true,headers){const r=headers?await this.raw(peer,route,{method:'POST',body,headers}):await this.request(peer,route,{method:body===undefined?'GET':'POST',body,authenticated});const chunks=[];let size=0;for await(const b of r){size+=b.length;if(size>8*1024*1024){r.destroy();throw Error('Phản hồi quá lớn.');}chunks.push(b);}const v=JSON.parse(Buffer.concat(chunks));if(r.statusCode>=400)throw Object.assign(Error(String(v.error||'Thiết bị từ chối yêu cầu.').slice(0,500)),{status:r.statusCode});return v;}
 peer(origin){const uri=new URL(origin);const p=[...this.candidates.values()].find(c=>c.origin===uri.origin);if(!p||!this.trusted[p.id])throw Error('Ghép nối thiết bị trước khi gửi hoặc nhận mã.');return p;}
}
