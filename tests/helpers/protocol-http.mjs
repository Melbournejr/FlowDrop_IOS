// Test-only bounded HTTP/1.1 client. Uses node:http, not the application's transport.
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';

async function collected(stream,limit){
 const chunks=[];let size=0;
 for await(const part of stream){size+=part.length;if(size>limit){stream.destroy();throw new Error('Test control response exceeds bound');}chunks.push(part);}
 return Buffer.concat(chunks,size);
}
export async function request(value,{method='GET',headers={},body}={}){
 const url=new URL(value);
 assert.ok(url.protocol==='http:'&&url.hostname==='127.0.0.1'&&!url.username&&!url.password&&!url.hash,'Test requests stay on the explicitly owned loopback origin');
 assert.ok(Number(url.port)>0&&Number(url.port)<=65535,'Explicit test host port required');
 const prepared={...headers};
 if((typeof body==='string'||Buffer.isBuffer(body)||body instanceof Uint8Array)&&!Object.keys(prepared).some(k=>k.toLowerCase()==='content-length'))prepared['Content-Length']=Buffer.byteLength(body);
 let req;
 const ready=new Promise((resolve,reject)=>{
  req=http.request(url,{method,headers:prepared,agent:false},res=>{
   res.on('error',()=>{});
   if(res.statusCode>=300&&res.statusCode<400){res.resume();reject(new Error('Redirect forbidden in test transport'));return;}
   resolve({status:res.statusCode,headers:{get(name){return res.headers[String(name).toLowerCase()]??null;}},body:res,
    json:async()=>JSON.parse((await collected(res,8*2**20)).toString('utf8')),
    arrayBuffer:async()=>collected(res,8*2**20)});
  });
  req.once('error',reject);req.setTimeout(90000,()=>req.destroy(new Error('Test HTTP idle deadline')));
 });
 // Consume rejections immediately even if source pumping is still in progress.
 ready.catch(()=>{});
 try{
  if(body===undefined||body===null)req.end();
  else if(typeof body==='string'||Buffer.isBuffer(body)||body instanceof Uint8Array)req.end(body);
  else{for await(const part of body){if(!req.write(part))await once(req,'drain');}req.end();}
  return await ready;
 }catch(error){req.destroy();throw error;}
}

export async function localRequest(host,route,options={}){
 assert.ok(typeof route==='string'&&route.startsWith('/')&&!route.startsWith('//'),'Only an origin-relative local route');
 const url=new URL(route,host.origin);assert.equal(url.origin,host.origin,'Do not forward local capability to another origin');
 assert.ok(['X-Desktop-Token','X-Local-Token'].includes(host.header)&&typeof host.token==='string'&&host.token,'Private startup capability required');
 return request(url,{...options,headers:{...options.headers,[host.header]:host.token}});
}
