import {validateMetadata,sameSecret} from './request-security.mjs';
import {randomUUID} from 'node:crypto';
import {isIPv4} from 'node:net';
import http from 'node:http';
import {Readable} from 'node:stream';
const terminal=new Set(['completed','rejected','failed','expired','untracked']);
const publicItem=i=>({id:i.id,direction:i.direction,name:i.name,code:i.code,count:i.count,size:i.size,bytes:i.bytes||0,filesDone:i.filesDone||0,currentName:i.currentName||'',state:i.state,createdAt:i.createdAt,startedAt:i.startedAt||0,updatedAt:i.updatedAt,finishedAt:i.finishedAt||0,error:i.error||'',connectionError:i.connectionError||''});
// Receiver status is authenticated per offer. Completion means every file was committed.
export class PeerOffers {
  constructor({deviceId,deviceName,port,getPeers,storage}){
    Object.assign(this,{deviceId,deviceName,port,getPeers,storage});this.key=randomUUID();this.items=new Map();this.outgoing=new Map();this.pendingIncoming=0;
    this.timer=setInterval(()=>this.refresh(),1000);this.timer.unref?.();
  }
  close(){clearInterval(this.timer);}
  touch(item,state,extra={}){Object.assign(item,extra,{state,updatedAt:Date.now()});if(terminal.has(state))item.finishedAt=Date.now();}
  prune(){
    const now=Date.now();for(const map of [this.items,this.outgoing]){
      for(const item of map.values())if(item.state==='pending'&&item.expiresAt<now||!terminal.has(item.state)&&now-item.createdAt>86400000)this.touch(item,'expired');
      const done=[...map.values()].filter(i=>terminal.has(i.state)).sort((a,b)=>b.createdAt-a.createdAt);
      for(const item of done)if(now-item.createdAt>86400000||done.indexOf(item)>=50)map.delete(item.id);
    }
  }
  list(){this.prune();return [...this.items.values()].filter(i=>i.state==='pending').map(({origin,statusToken,...i})=>i);}
  sessions(){this.prune();return [...this.items.values(),...this.outgoing.values()].sort((a,b)=>b.createdAt-a.createdAt).map(publicItem);}
  status(id,token){this.prune();const item=this.items.get(id);if(!item||!token||!sameSecret(token,item.statusToken))throw new Error('Không có quyền xem phiên truyền.');return publicItem(item);}
  async incoming(body,remote){
    this.prune();if(!sameSecret(body.offerKey,this.key))throw new Error('Mở lại danh sách thiết bị rồi gửi lại.');
    remote=remote?.replace(/^::ffff:/,'');
    if(!isIPv4(remote)||remote==='0.0.0.0'||remote.startsWith('169.254.')||!Number.isInteger(body.port)||body.port<1||body.port>65535||!/^[A-Z2-9]{8}$/.test(body.code)||typeof body.deviceId!=='string'||body.deviceId===this.deviceId)throw new Error('Thiết bị gửi không hợp lệ.');
    if([...this.items.values()].filter(i=>!terminal.has(i.state)).length>=20)throw new Error('Đang có nhiều yêu cầu nhận. Hãy thử lại sau.');
    if(this.pendingIncoming>=8)throw new Error('Đang xác minh nhiều yêu cầu. Thử lại sau.');
    this.pendingIncoming++;try{
    const origin='http://'+remote+':'+body.port,config=await peerJson(origin,'/api/config');
    if(config.name!=='FlowDrop'||config.deviceId!==body.deviceId)throw new Error('Không xác minh được FlowDrop trên thiết bị gửi.');
    const metadata=validateMetadata(await peerJson(origin,'/api/transfers/'+body.code),body.code);
    if([...this.items.values()].filter(i=>!terminal.has(i.state)).length>=20)throw new Error('Đang có nhiều yêu cầu nhận.');
    const duplicate=[...this.items.values()].find(i=>!terminal.has(i.state)&&i.origin===origin&&i.code===body.code&&i.statusToken===body.statusToken);if(duplicate)return {id:duplicate.id,state:duplicate.state,tracking:1};
    const now=Date.now(),item={id:randomUUID(),origin,code:body.code,name:String(config.deviceName||'Thiết bị').slice(0,100),count:metadata.files.length,size:metadata.files.reduce((n,f)=>n+f.size,0),direction:'receive',bytes:0,filesDone:0,state:'pending',createdAt:now,updatedAt:now,expiresAt:now+120000,statusToken:/^[a-f0-9-]{36}$/.test(body.statusToken||'')?body.statusToken:randomUUID()};
    this.items.set(item.id,item);return {id:item.id,state:item.state,tracking:1};
    }finally{this.pendingIncoming--;}
  }
  async send(peerId,code){
    if(!/^[A-Z2-9]{8}$/.test(code))throw new Error('Mã gửi không hợp lệ.');
    const peer=this.getPeers().find(p=>p.id===peerId);if(!peer)throw new Error('Thiết bị đã rời mạng. Bấm Tìm lại rồi chọn thiết bị.');
    const config=await peerJson(peer.url,'/api/config');
    if(config.name!=='FlowDrop'||!config.offerKey||config.deviceId===this.deviceId)throw new Error('Cập nhật FlowDrop trên thiết bị nhận để gửi trực tiếp.');
    const metadata=await(await this.storage.getResponse('/api/transfers/'+code)).json(),now=Date.now();
    const item={id:randomUUID(),direction:'send',name:peer.name,code,count:metadata.files.length,size:metadata.files.reduce((n,f)=>n+f.size,0),bytes:0,filesDone:0,state:'pending',createdAt:now,updatedAt:now,expiresAt:now+120000,statusToken:randomUUID(),origin:peer.url};this.outgoing.set(item.id,item);
    try{const reply=await peerJson(peer.url,'/api/offers',{code,port:this.port(),deviceId:this.deviceId,offerKey:config.offerKey,statusToken:item.statusToken});if(typeof reply.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(reply.id))throw new Error('Mã phiên nhận không hợp lệ.');item.remoteId=reply.id;if(reply.tracking!==1)this.touch(item,'untracked',{error:'Cập nhật FlowDrop 1.8 trên máy nhận để xem tiến độ và xác nhận hoàn tất.'});return {...reply,sessionId:item.id};}
    catch(error){this.touch(item,'failed',{error:error.message});throw error;}
  }
  async refresh(){
    this.prune();for(const item of this.outgoing.values()){
      if(terminal.has(item.state)||item.polling||!item.remoteId)continue;item.polling=true;
      peerJson(item.origin,'/api/offers/status',{id:item.remoteId,token:item.statusToken}).then(status=>{
        if(status.size!==item.size||status.count!==item.count||!Number.isSafeInteger(status.bytes)||status.bytes<0||status.bytes>item.size||!Number.isInteger(status.filesDone)||status.filesDone<0||status.filesDone>item.count||!['pending','accepted','transferring','completed','rejected','failed','expired'].includes(status.state)||status.state==='completed'&&(status.bytes!==item.size||status.filesDone!==item.count))throw new Error('Máy nhận trả trạng thái không hợp lệ.');
        for(const key of ['startedAt','updatedAt','finishedAt'])if(status[key]!==undefined&&(!Number.isSafeInteger(status[key])||status[key]<0))throw new Error('Thời gian phiên truyền không hợp lệ.');
        for(const key of ['currentName','error'])if(status[key]!==undefined&&typeof status[key]!=='string')throw new Error('Trạng thái phiên truyền không hợp lệ.');
        Object.assign(item,{state:status.state,bytes:status.bytes,filesDone:status.filesDone,currentName:(status.currentName||'').slice(0,255),startedAt:status.startedAt||0,updatedAt:status.updatedAt||0,finishedAt:status.finishedAt||0,error:(status.error||'').slice(0,500),connectionError:''});
      }).catch(error=>{item.connectionError='Mất kết nối · đang thử lại';item.error=String(error.message).slice(0,500);}).finally(()=>{item.polling=false;});
    }
  }
  async answer(id,accept){
    this.prune();const item=this.items.get(id);if(!item||item.state!=='pending')throw new Error('Yêu cầu đã hết hạn hoặc đã được xử lý.');
    if(!accept){this.touch(item,'rejected');return {rejected:true};}
    this.touch(item,'accepted',{startedAt:Date.now()});
    try{const result=await this.storage.receive(item.code,undefined,route=>peerDownload(item.origin+route),item.origin,progress=>this.touch(item,'transferring',progress));
      this.touch(item,'completed',{bytes:item.size,filesDone:item.count,currentName:''});return result;
    }catch(error){this.touch(item,'failed',{error:error.message});throw error;}
  }
  async receiveCode(found,fileId){
    const selected=fileId?found.metadata.files.filter(file=>file.id===fileId):found.metadata.files;if(!selected.length)throw new Error('Không tìm thấy file trong mã này.');
    const now=Date.now(),item={id:randomUUID(),direction:'receive',name:found.name,origin:found.origin,code:found.metadata.code,count:selected.length,size:selected.reduce((n,f)=>n+f.size,0),bytes:0,filesDone:0,state:'accepted',createdAt:now,startedAt:now,updatedAt:now,statusToken:randomUUID()};this.items.set(item.id,item);
    try{
      const result=await this.storage.receive(item.code,fileId,found.getResponse,found.origin,progress=>this.touch(item,'transferring',progress));
      if(result.files.length!==item.count||result.files.reduce((n,f)=>n+f.size,0)!==item.size)throw new Error('Danh sách file đã thay đổi. Nhận lại mã mới.');
      this.touch(item,'completed',{bytes:item.size,filesDone:item.count,currentName:''});return result;
    }catch(error){this.touch(item,'failed',{error:error.message});throw error;}
  }
}
export async function peerJson(origin,route,body,timeout=8000,signal){
  const response=await fetch(origin+route,{method:body?'POST':'GET',redirect:'error',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.any([AbortSignal.timeout(timeout),signal].filter(Boolean))});
  if(Number(response.headers.get('content-length'))>8*1024*1024){await response.body?.cancel();throw new Error('Phản hồi quá lớn.');}
  let bytes=0,text='';const decoder=new TextDecoder();for await(const chunk of response.body){bytes+=chunk.length;if(bytes>8*1024*1024)throw new Error('Phản hồi quá lớn.');text+=decoder.decode(chunk,{stream:true});}text+=decoder.decode();const result=JSON.parse(text);if(!response.ok)throw new Error(String(result.error||'Không kết nối được thiết bị.').slice(0,500));return result;
}

// Only idle periods time out: a large, steadily downloading file has no total deadline.
export function peerDownload(url){
  return new Promise((resolve,reject)=>{
    // Node's HTTP stream handles an abruptly truncated download without the
    // Fetch parser's paused-body assertion; only idle periods are timed out.
    const request=http.get(url,response=>{
      clearTimeout(headerTimer);response.setTimeout(120000,()=>response.destroy(new Error('Kết nối nhận file đã hết thời gian chờ.')));
      const headers=Object.fromEntries(Object.entries(response.headers).filter(([,v])=>v!==undefined).map(([k,v])=>[k,Array.isArray(v)?v.join(', '):v]));
      resolve(new Response(Readable.toWeb(response),{status:response.statusCode,headers}));
    });
    const headerTimer=setTimeout(()=>request.destroy(new Error('Thiết bị gửi không phản hồi.')),8000);
    request.on('error',error=>{clearTimeout(headerTimer);reject(error);});
  });
}
