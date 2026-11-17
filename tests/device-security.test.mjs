import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import https from 'node:https';
import {DeviceSecurity,deviceVault} from '../scripts/device-security.mjs';

test('Windows request signature has a fixed cross-platform canonical byte vector',()=>{
 assert.equal(DeviceSecurity.prototype.signature('11'.repeat(32),'POST','/api/secure/session','1763384400000','22'.repeat(32),''),'d06e638576c1c502ed2303468c665db07cec48e91adfc45debf841d0b298a519');
});

test('real TLS, two-screen pairing, identity pin, expiring authenticated sessions and replay rejection',async()=>{
 const scratch=await mkdtemp(path.join(tmpdir(),'flowdrop-secure-unit-')),servers=[];
 try{
  async function host(id){const vault=await deviceVault(scratch,id),security=new DeviceSecurity({id,name:id,vault});const server=https.createServer(security.tlsOptions(),async(req,res)=>{try{let body='';for await(const chunk of req){body+=chunk;if(body.length>16384)throw Error('large');}const route=new URL(req.url,'https://localhost').pathname;
   let value;if(route.startsWith('/api/secure/pair/'))value=await security.pairRoute(route,JSON.parse(body),req.socket.remoteAddress);else if(route==='/api/secure/session')value=security.session(req.headers);else{security.authorize(req.method,route,req.headers);value={ok:true};}res.setHeader('content-type','application/json');res.end(JSON.stringify(value));}catch{res.statusCode=403;res.end('{"error":"Denied"}');}});servers.push(server);await new Promise(r=>server.listen(0,'127.0.0.1',r));security.config(server.address().port);return {security,vault,origin:'https://127.0.0.1:'+server.address().port};}
  const a=await host('device-a'),b=await host('device-b');const peer=a.security.candidate('device-b',b.origin,b.security.identity.certificate,'B');
  await assert.rejects(a.security.json(peer,'/private'),/Ghép nối/);
  const state=await a.security.start(peer.id),p=state.pairings[0];assert.match(p.code,/^\d{6}$/);assert.ok(p.code===b.security.snapshot().pairings[0].code,'Pairing SAS must match');
  await a.security.confirm(p.id,true);assert.equal(a.security.snapshot().trusted.length,0,'one-sided approval must not establish trust');
  await b.security.confirm(p.id,true);await a.security.refresh();assert.equal(a.security.snapshot().trusted.length,1);assert.equal(b.security.snapshot().trusted.length,1);
  assert.equal((await a.security.json(peer,'/private')).ok,true);
  b.security.sessions.clear();assert.equal((await a.security.json(peer,'/private')).ok,true,'Cached trust must obtain a fresh session after receiver restart');
  const session=a.security.remoteSessions.get(peer.id),headers=a.security.headers(peer.id,'GET','/private',session.token);
  const first=await a.security.raw(peer,'/private',{headers});assert.equal(first.statusCode,200);first.resume();
  const replay=await a.security.raw(peer,'/private',{headers});assert.equal(replay.statusCode,403);replay.resume();
  const bad=a.security.headers(peer.id,'GET','/private',session.token);bad['x-fd-time']='1000000000000';const stale=await a.security.raw(peer,'/private',{headers:bad});assert.equal(stale.statusCode,403);stale.resume();
  await assert.rejects(a.security.raw({...peer,fingerprint:'0'.repeat(64)},'/private'),/Danh tính TLS/);
  const wrong=await host('device-b');assert.throws(()=>a.security.candidate('device-b',wrong.origin,wrong.security.identity.certificate,'fake'),/đã đổi/);
  await b.security.forget('device-a');await assert.rejects(a.security.json(peer,'/private'),/Denied/);
  assert.equal(JSON.stringify(a.security.snapshot()).includes(a.vault.value.trusted['device-b'].secret),false,'public state cannot leak paired secrets');
 }finally{for(const server of servers){server.closeAllConnections();await new Promise(r=>server.close(r));}await rm(scratch,{recursive:true,force:true});}
});

test('pairing commitment mismatch, expiry and guessing limits never create trust',async()=>{
 const dir=await mkdtemp(path.join(tmpdir(),'flowdrop-pair-negative-'));
 try{
  const a=new DeviceSecurity({id:'negative-a',name:'A',vault:await deviceVault(dir,'negative-a')});
  const b=new DeviceSecurity({id:'negative-b',name:'B',vault:await deviceVault(dir,'negative-b')});
  const body={id:b.id,name:'B',certificate:b.identity.certificate,commit:'0'.repeat(64)};
  const start={id:'a'.repeat(64)};a.pairs.set(start.id,{peer:{id:b.id},commit:body.commit,transcript:'test',direction:'incoming',until:Date.now()+120000});
  await assert.rejects(a.pairRoute('/api/secure/pair/reveal',{id:start.id,nonce:'1'.repeat(64)},'same-address'),/không hợp lệ/);
  a.pairs.get(start.id).until=0;await assert.rejects(a.confirm(start.id,true),/hết hạn/);
  for(let i=0;i<3;i++)await assert.rejects(a.pairRoute('/api/secure/pair/start',body,'same-address'),/TLS/);
  await assert.rejects(a.pairRoute('/api/secure/pair/start',body,'same-address'),/Quá nhiều/);
  assert.equal(a.snapshot().trusted.length,0);
 }finally{await rm(dir,{recursive:true,force:true});}
});
