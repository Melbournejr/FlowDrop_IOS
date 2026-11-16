import {validateMetadata} from './request-security.mjs';
import {peerJson,peerDownload} from './peer-offers.mjs';
export const normalizeCode=value=>String(value??'').replace(/[\s\u0085-]/gu,'').toUpperCase();
export function validateSharedMetadata(metadata,code){
  if(metadata?.code!==code||!Array.isArray(metadata.files)||!metadata.files.length)throw new Error('Danh sách file không hợp lệ.');
  let total=0;for(const file of metadata.files){if(!/^[a-f0-9-]{36}$/.test(file.id)||typeof file.name!=='string'||!file.name.trim()||!Number.isSafeInteger(file.size)||file.size<0||file.size>Number.MAX_SAFE_INTEGER-total)throw new Error('Thông tin file không hợp lệ.');total+=file.size;}
  return validateMetadata(metadata,code);
}
/** A code identifies a share, not a local database row. Search verified LAN peers. */
export async function findCode(input,{getPeers,getLocal,preferredId,timeout=7000}){
  const code=normalizeCode(input);if(!/^[A-Z2-9]{8}$/.test(code))throw new Error('Nhập đủ mã nhận 8 ký tự.');
  const stop=new AbortController(),timer=setTimeout(()=>stop.abort(),timeout),deadline=Date.now()+timeout;
  const matches=[],attempted=new Set();let verified=0,expired=false;
  try{
    try{const response=await getLocal('/api/transfers/'+code);if(response.ok){const metadata=validateSharedMetadata(await response.json(),code);matches.push({origin:'local',metadata,name:'Máy này',id:'local',getResponse:getLocal});}else if(response.status===410)expired=true;}catch{}
    // Discovery may complete after the user pastes a code. A snapshot of an empty
    // peer list must not turn a valid LAN share into an immediate "not found".
    do{
      const peers=[...new Map(getPeers().map(peer=>[peer.id,peer])).values()].slice(0,64);
      await Promise.allSettled(peers.map(async peer=>{
        const url=new URL(peer.url);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return;
        const key=peer.id+'@'+url.origin;if(attempted.has(key)||attempted.size>=128)return;attempted.add(key);
        const config=await peerJson(url.origin,'/api/config',undefined,3000,stop.signal);if(config.name!=='FlowDrop'||config.deviceId!==peer.id)return;verified++;
        try{const metadata=validateSharedMetadata(await peerJson(url.origin,'/api/transfers/'+code,undefined,3000,stop.signal),code);
          matches.push({origin:url.origin,metadata,name:config.deviceName||peer.name,id:peer.id,getResponse:route=>peerDownload(url.origin+route)});
        }catch(error){if(error.status===410)expired=true;}
      }));
      if(matches.length||stop.signal.aborted)break;
      await new Promise(resolve=>setTimeout(resolve,Math.min(200,Math.max(0,deadline-Date.now()))));
    }while(Date.now()<deadline);
  }finally{clearTimeout(timer);stop.abort();}
  const chosen=matches.find(match=>match.id===preferredId);if(chosen)return chosen;
  if(matches.length>1)throw new Error('Có nhiều thiết bị dùng cùng mã. Chọn đúng thiết bị rồi nhận lại.');
  if(!matches.length)throw new Error(expired?'Mã chia sẻ đã hết hạn. Tạo mã mới trên thiết bị gửi.':verified?'Mã không tồn tại hoặc đã được thu hồi trên các thiết bị tìm thấy. Kiểm tra mã và máy gửi.':'Chưa tìm thấy thiết bị giữ mã trong Wi-Fi. Mở FlowDrop trên máy gửi rồi bấm nhận lại.');
  return matches[0];
}
