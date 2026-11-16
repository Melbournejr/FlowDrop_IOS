import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {createHash} from 'node:crypto';
import {request,localRequest} from './helpers/protocol-http.mjs';

async function fixture(run,handler){const server=http.createServer(handler);await new Promise(r=>server.listen(0,'127.0.0.1',r));try{await run('http://127.0.0.1:'+server.address().port);}finally{server.closeAllConnections();await new Promise(r=>server.close(r));}}
async function* generated(size){let left=size;const part=Buffer.alloc(65536,91);while(left){const out=part.subarray(0,Math.min(left,part.length));left-=out.length;yield out;}}
test('HTTP helper streams actual upload/download and preserves Content-Length and SHA',async()=>{
 const size=16*2**20+17;const expected=createHash('sha256');for await(const b of generated(size))expected.update(b);const hash=expected.digest('hex');
 await fixture(async origin=>{
  const upload=await request(origin+'/upload',{method:'PUT',headers:{'Content-Length':String(size)},body:generated(size)});assert.equal(upload.status,200);assert.deepEqual(await upload.json(),{size,sha256:hash});
  const response=await request(origin+'/download');assert.equal(Number(response.headers.get('Content-Length')),size);const actual=createHash('sha256');let count=0;for await(const b of response.body){count+=b.length;actual.update(b);}assert.equal(count,size);assert.equal(actual.digest('hex'),hash);
 },async(req,res)=>{try{
  if(req.method==='PUT'){const h=createHash('sha256');let n=0;for await(const b of req){n+=b.length;h.update(b);}assert.equal(Number(req.headers['content-length']),size);res.end(JSON.stringify({size:n,sha256:h.digest('hex')}));}
  else{res.writeHead(200,{'Content-Length':String(size)});for await(const b of generated(size)){if(!res.write(b))await once(res,'drain');}res.end();}
 }catch(e){res.destroy(e);}});
});
test('HTTP helper reports a prematurely truncated Content-Length body as failure',async()=>{
 await fixture(async origin=>{const response=await request(origin+'/short');await assert.rejects(async()=>{for await(const part of response.body){};});},(req,res)=>{res.writeHead(200,{'Content-Length':'1024'});res.write('short');res.socket.end();});
});
test('HTTP helper does not follow redirects or send data to an external host',async()=>{
 let requests=0;await fixture(async origin=>{await assert.rejects(request(origin+'/redirect'),/Redirect/);assert.equal(requests,1);},(req,res)=>{requests++;res.writeHead(302,{Location:'http://invalid.example/never-request'});res.end();});
 await assert.rejects(request('https://invalid.example/never-request'));
});
test('local capability belongs to exactly one loopback origin and kind',async()=>{
 await fixture(async origin=>{const host={origin,header:'X-Local-Token',token:'synthetic-fixture-capability'};const result=await localRequest(host,'/api/transfers',{method:'POST',body:'{}'});assert.equal(result.status,200);await result.json();await assert.rejects(localRequest(host,'//invalid.example/steal',{method:'POST',body:'{}'}));},(req,res)=>{assert.equal(req.headers['x-local-token'],'synthetic-fixture-capability');req.resume();req.on('end',()=>res.end('{}'));});
});
test('oversized control JSON is rejected without treating a prefix as valid',async()=>{
 await fixture(async origin=>{const result=await request(origin+'/large');await assert.rejects(result.json(),/exceeds bound/);},(req,res)=>{res.end(Buffer.alloc(8*2**20+1,32));});
});
