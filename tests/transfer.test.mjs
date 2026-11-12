import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.js';
class MemoryBucket{
  objects=new Map();
  async put(key,value){const bytes=typeof value==='string'?new TextEncoder().encode(value):value instanceof ReadableStream?new Uint8Array(await new Response(value).arrayBuffer()):new Uint8Array(value);this.objects.set(key,bytes);return {key};}
  async get(key){const value=this.objects.get(key);if(!value)return null;return {body:new Response(value).body,json:async()=>JSON.parse(new TextDecoder().decode(value)),size:value.byteLength};}
  async head(key){const value=this.objects.get(key);return value?{size:value.byteLength}:null;}
  async delete(keys){for(const key of Array.isArray(keys)?keys:[keys])this.objects.delete(key);}
  async list({prefix,limit}){return {objects:[...this.objects.keys()].filter(k=>k.startsWith(prefix)).sort().slice(0,limit).map(key=>({key}))};}
}
function setup(){const bucket=new MemoryBucket();const call=(path,method='GET',body,headers={})=>worker.fetch(new Request('https://flowdrop.test'+path,{method,body,...(body instanceof ReadableStream?{duplex:'half'}:{}),headers}),{BUCKET:bucket},{});const create=async(files=[{name:'Tài liệu.txt',size:8,type:'text/plain'}])=>{const response=await call('/api/transfers','POST',JSON.stringify({files}));assert.equal(response.status,201);return response.json();};return {bucket,call,create};}
test('send, finalize, receive original bytes, and revoke across clients',async()=>{
 const {call,create}=setup();const transfer=await create();const root='/api/transfers/'+transfer.code,headers={'X-Upload-Token':transfer.token};
 assert.equal((await call(root)).status,409);
 assert.equal((await call(root+'/files/'+transfer.files[0].id,'GET')).status,409);
 assert.equal((await call(root+'/complete','POST',null,headers)).status,409);
 assert.equal((await call(root+'/files/'+transfer.files[0].id,'PUT','xin chao',headers)).status,200);
 assert.equal((await call(root+'/complete','POST',null,headers)).status,200);
 const received=await (await call(root)).json();assert.equal(received.token,undefined);assert.equal(received.files[0].name,'Tài liệu.txt');
 const download=await call(root+'/files/'+transfer.files[0].id);assert.equal(download.status,200);assert.equal(await download.text(),'xin chao');assert.match(download.headers.get('Content-Disposition'),/filename\*=UTF-8/);assert.equal(download.headers.get('Content-Type'),'application/octet-stream');
 assert.equal((await call(root,'DELETE',null,headers)).status,200);assert.equal((await call(root)).status,404);assert.equal((await call(root+'/files/'+transfer.files[0].id)).status,404);
});
test('upload and revoke require uploader token; foreign origin blocked',async()=>{
 const {call,create}=setup();const t=await create(),root='/api/transfers/'+t.code;
 assert.equal((await call(root,'DELETE')).status,403);assert.equal((await call(root+'/files/'+t.files[0].id,'PUT','xin chao')).status,403);assert.equal((await call(root+'/complete','POST')).status,403);
 assert.equal((await call('/api/transfers','POST',JSON.stringify({files:[{name:'ok',size:1}]}),{Origin:'https://foreign.test'})).status,403);
});
test('invalid names, protocol bounds, byte mismatch and missing codes rejected',async()=>{
 const {call,create}=setup();
 for(const files of [[],[{name:'bad\nname',size:1}],[{name:'',size:1}],[{name:'negative',size:-1}],[{name:'overflow',size:Number.MAX_SAFE_INTEGER+1}],[{name:'fraction',size:1.5}]])assert.equal((await call('/api/transfers','POST',JSON.stringify({files}))).status,400);
 const t=await create(),path='/api/transfers/'+t.code+'/files/'+t.files[0].id,headers={'X-Upload-Token':t.token};
 assert.equal((await call(path,'PUT','short',headers)).status,400);assert.equal((await call(path,'PUT','too many bytes here',headers)).status,413);
 assert.equal((await call('/api/transfers/ABCDEFGH')).status,404);
});
test('expiry blocks access; empty files transfer; finalized uploads immutable',async()=>{
 const {call,create,bucket}=setup();const empty=await create([{name:'empty.txt',size:0}]);const root='/api/transfers/'+empty.code,headers={'X-Upload-Token':empty.token};
 assert.equal((await call(root+'/files/'+empty.files[0].id,'PUT',null,headers)).status,200);assert.equal((await call(root+'/complete','POST',null,headers)).status,200);
 assert.equal(await (await call(root+'/files/'+empty.files[0].id)).text(),'');assert.equal((await call(root+'/files/'+empty.files[0].id,'PUT',null,headers)).status,403);
 const key='transfers/'+empty.code+'/meta.json',meta=await (await bucket.get(key)).json();meta.expiresAt=Date.now()-1;await bucket.put(key,JSON.stringify(meta));assert.equal((await call(root)).status,410);assert.equal((await call(root+'/files/'+empty.files[0].id)).status,410);
});
