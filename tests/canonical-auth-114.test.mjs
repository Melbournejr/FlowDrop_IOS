import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {DeviceSecurity} from '../scripts/device-security.mjs';
import {createHarness,javaCommand} from './helpers/harness.mjs';

test('Java signing bytes match Windows for paths, JSON escapes, UTF-8 and lone surrogates',async()=>{
 const harness=await createHarness('canonical-auth');
 try{
  const {classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/DeviceSecurity.java','android/src/app/flowdrop/mobile/RequestSecurity.java','tests/RequestCanonicalHarness.java']);
  const routes=['/api/secure/session','/api/offers','/api/transfers/ABCD2345/files/00000000-0000-0000-0000-000000000000','/api/offers?name=a%20b&state=ready','/a\\/b"c','/Tiếng Việt/中文/😀','/\b\f\n\r\t','/\ud800','/\udc00','/\ud800x\udc00','/\u2028\u2029'];
  // Exercise every C0 character and UTF-16 boundary without relying on org.json
  // serialization for the expected value. These are pure signing inputs only.
  for(let c=0;c<32;c++)routes.push('/control/'+String.fromCharCode(c));
  for(const a of [0x20,0x22,0x2f,0x5c,0x7f,0x80,0x2028,0x2029,0xd7ff,0xd800,0xdbff,0xdc00,0xdfff,0xe000,0xffff])for(const b of [0x22,0x2f,0x5c,0xd800,0xdc00])routes.push('/'+String.fromCharCode(a,b));
  const vectors=routes.map((route,i)=>({secret:'11'.repeat(32),method:i%2?'GET':'POST',route,time:'1763384400000',nonce:'22'.repeat(32),token:i%3?'33'.repeat(32):''}));
  const expected=vectors.map(v=>DeviceSecurity.prototype.signature(v.secret,v.method,v.route,v.time,v.nonce,v.token));
  const result=spawnSync(javaCommand,['-cp',classpath,'app.flowdrop.mobile.RequestCanonicalHarness'],{input:vectors.map(v=>JSON.stringify(v)).join('\n')+'\n',encoding:'utf8',timeout:15000,maxBuffer:1024*1024});
  assert.equal(result.status,0,result.stderr);assert.deepEqual(result.stdout.trim().split(/\r?\n/),expected);
 }finally{await harness.cleanup();}
});
