import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readdir} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {sameSecret,validateMetadata,browserRequestAllowed} from '../scripts/request-security.mjs';
import {DesktopStorage} from '../scripts/desktop-storage.mjs';
const good={code:'ABCDEFGH',files:[{id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Tài liệu.txt',size:12,type:'text/plain'}]};
test('reject untrusted metadata before opening any file body or destination',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'flowdrop-untrusted-'));let downloads=0;
 try{
  for(const changed of [x=>x.code='BCDEFGHJ',x=>x.files[0].size='12',x=>x.files[0].size=Infinity,x=>x.files[0].size=-1,x=>x.files[0].id='../secret',x=>x.files[0].name='bad\nname',x=>x.files[0].name='x'.repeat(256),x=>x.files[0].type='text/plain\r\nInjected: yes',x=>x.files.push({...x.files[0]})]){
   const metadata=structuredClone(good);changed(metadata);
   const storage=new DesktopStorage({dataDirectory:path.join(root,'state'),defaultDirectory:path.join(root,'received'),getResponse:async url=>{if(url.endsWith('/ABCDEFGH'))return Response.json(metadata);downloads++;return new Response('data');}});
   await assert.rejects(storage.receive('ABCDEFGH'));assert.equal(downloads,0);assert.deepEqual(await readdir(root),[]);
  }
  assert.equal(validateMetadata(structuredClone(good),'ABCDEFGH').files.length,1);
 }finally{await rm(root,{recursive:true,force:true});}
});
test('capabilities compare full bytes, and browser cross-origin requests are rejected',()=>{
 assert.equal(sameSecret('abc','abc'),true);for(const bad of [undefined,'','ab','abd','ééé',{},['abc']])assert.equal(sameSecret(bad,'abc'),false);
 assert.equal(browserRequestAllowed({},'http://127.0.0.1:5173'),true);
 for(const headers of [{origin:'null'},{origin:'https://evil.test'},{'sec-fetch-site':'cross-site'},{'sec-fetch-site':'same-site'}])assert.equal(browserRequestAllowed(headers,'http://127.0.0.1:5173'),false);
});
