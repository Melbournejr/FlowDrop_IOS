import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeCode,findCode} from '../scripts/code-lookup.mjs';
import {CodeGuessGuard} from '../scripts/request-security.mjs';
test('share codes normalize pasted Unicode spacing and separators, not arbitrary characters',()=>{
 assert.equal(normalizeCode('\ufeffab-cd\u00a0ef\u0085gh\n'),'ABCDEFGH');assert.equal(normalizeCode('AB!CDEFGH'),'AB!CDEFGH');
});
test('malformed codes fail before network access',async()=>{
 await assert.rejects(findCode('AB!CDEFGH',{getPeers(){throw Error('network');}}),/8 ký tự/);
});
test('expired and unknown codes have distinct messages',async()=>{
 for(const [status,message] of [[410,/hết hạn/],[404,/thiết bị/]])await assert.rejects(findCode('ABCDEFGH',{getPeers:()=>[],getLocal:async()=>new Response('{}',{status}),timeout:5}),message);
});
test('failed guess limiter is address scoped, bounded, and expires',()=>{
 let now=1;const guard=new CodeGuessGuard({clock:()=>now});for(let i=0;i<25;i++)guard.failed('a');assert.equal(guard.allowed('a'),false);assert.equal(guard.allowed('b'),true);
 now+=60001;assert.equal(guard.allowed('a'),true);for(let i=0;i<700;i++)guard.failed('ip'+i);assert.equal(guard.items.size,512);
});

test('receiver rejects same-size corrupted payload before publishing a destination',async()=>{
 const {DesktopStorage}=await import('../scripts/desktop-storage.mjs');const {mkdtemp,rm,readdir}=await import('node:fs/promises');const {tmpdir}=await import('node:os');const path=await import('node:path');
 const d=await mkdtemp(path.join(tmpdir(),'flowdrop-hash-'));try{
  const meta={code:'ABCDEFGH',files:[{id:'00000000-0000-4000-8000-000000000001',name:'safe.txt',size:3,sha256:'0'.repeat(64)}]};
  const storage=new DesktopStorage({dataDirectory:path.join(d,'data'),defaultDirectory:path.join(d,'saved'),getResponse:async route=>route.includes('/files/')?new Response('bad'):Response.json(meta)});
  await assert.rejects(storage.receive('ABCDEFGH'),/SHA-256/);assert.deepEqual(await readdir(path.join(d,'saved')),[]);
 }finally{await rm(d,{recursive:true,force:true});}
});

test('original public signing inventory and its signature remain valid',async()=>{
 const {spawnSync}=await import('node:child_process');const r=spawnSync(process.execPath,['security/verify-key-inventory.mjs'],{encoding:'utf8',timeout:10000});assert.equal(r.status,0,'Public signing identity verification failed');
});
