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
