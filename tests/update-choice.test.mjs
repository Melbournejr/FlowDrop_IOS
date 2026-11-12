import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash,generateKeyPairSync,sign} from 'node:crypto';
import {DesktopUpdater} from '../scripts/secure-update.mjs';
const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:2048});
const key=publicKey.export({format:'pem',type:'spki'}),bytes=Buffer.from('verified installer');
function manifest(version){const payload=JSON.stringify({schema:1,app:'FlowDrop',platforms:{windows:{version,url:'https://updates.test/app.exe',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}}});return {payload,signature:sign('RSA-SHA256',Buffer.from(payload),privateKey).toString('base64')};}
test('manual and scheduled checks report results; Later never downloads; explicit acceptance waits for active transfers',async()=>{
 const dir=await mkdtemp(path.join(tmpdir(),'flowdrop-update-choice-'));let latest='1.0.0',offline=false,busy=false;const calls=[];
 const fetcher=async url=>{calls.push(url);if(offline)throw new Error('offline');return new Response(url.endsWith('.json')?JSON.stringify(manifest(latest)):bytes);};
 const updater=new DesktopUpdater({dataDirectory:dir,version:'1.0.0',feed:'https://updates.test/latest.json',key,fetcher,busy:()=>busy,enabled:false});
 try{
  updater.check(true);await updater.task;assert.equal(updater.state.phase,'current');assert.equal(updater.state.manual,true);
  latest='1.1.0';updater.check();await updater.task;assert.equal(updater.state.phase,'available');assert.equal(updater.state.manual,false);assert.ok(calls.every(x=>x.endsWith('.json')));
  updater.later();assert.equal(updater.state.accepted,false);await assert.rejects(updater.prepareInstall());const old=updater.state.checkId;
  updater.check(true);await updater.task;assert.throws(()=>updater.accept({version:latest,checkId:old}));assert.ok(calls.every(x=>x.endsWith('.json')));
  busy=true;updater.accept({version:latest,checkId:updater.state.checkId});assert.equal(updater.state.phase,'deferred');assert.ok(calls.every(x=>x.endsWith('.json')));updater.resume();assert.equal(updater.state.phase,'deferred');
  busy=false;updater.resume();await updater.task;assert.equal(updater.state.phase,'ready');assert.equal(updater.snapshot().canApply,true);assert.equal(calls.filter(x=>x.endsWith('.exe')).length,1);
  await updater.prepareInstall();updater.installFailed();assert.equal(updater.state.phase,'available');assert.equal(updater.state.accepted,false);
  offline=true;updater.check(true);await updater.task;assert.equal(updater.state.phase,'error');assert.match(updater.state.error,/offline/);assert.equal(updater.snapshot().canApply,false);
 }finally{updater.close();await rm(dir,{recursive:true,force:true});}
});
