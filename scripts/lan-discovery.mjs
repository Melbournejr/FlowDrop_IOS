import dgram from 'node:dgram';
import {networkInterfaces} from 'node:os';
import {isIPv4} from 'node:net';
import {peerJson} from './peer-offers.mjs';
export const LAN_PORT=53317,LAN_GROUP='239.255.77.77';
const ipv4=ip=>ip.split('.').reduce((n,b)=>(n*256+Number(b))>>>0,0);
const address=n=>[24,16,8,0].map(s=>(n>>>s)&255).join('.');
export function startLanDiscovery({deviceId,deviceName,port,platform='windows',version='1.13.0',onError=console.warn,interfaces=()=>Object.values(networkInterfaces()).flat().filter(a=>a?.family==='IPv4'&&!a.internal&&!a.address.startsWith('169.254.'))}){
  const socket=dgram.createSocket({type:'udp4',reuseAddr:true}),peers=new Map(),attempts=new Map(),pending=new Set(),members=new Set(),transports=new Map();
  let closed=false,ready=false,lastError='',timer;
  const report=error=>{const message=error?.message||String(error);if(!closed&&message!==lastError){lastError=message;onError('Dò thiết bị trong Wi-Fi: '+message);}};
  const packet=kind=>Buffer.from(JSON.stringify({app:'flowdrop',discovery:1,kind,id:deviceId,name:String(deviceName).slice(0,100),platform,port,version}));
  const send=(bytes,destination,targetPort=LAN_PORT,transport=socket)=>{if(ready&&!closed)try{transport.send(bytes,targetPort,destination,error=>{if(error)report(error);});}catch(error){report(error);}};
  function reconcile(){
    const current=new Map(interfaces().filter(i=>isIPv4(i.address)).map(i=>[i.address,i]));
    for(const [ip,entry] of transports)if(!current.has(ip)){try{entry.socket.close();socket.dropMembership(LAN_GROUP,ip);}catch{}transports.delete(ip);members.delete(ip);}
    for(const [ip,iface] of current){
      if(!members.has(ip))try{socket.addMembership(LAN_GROUP,ip);members.add(ip);}catch(error){report(error);}
      if(transports.has(ip)){transports.get(ip).iface=iface;continue;}
      const tx=dgram.createSocket('udp4'),entry={socket:tx,iface,ready:false};transports.set(ip,entry);tx.on('error',error=>{report(error);if(!entry.ready&&transports.get(ip)===entry){transports.delete(ip);try{tx.close();}catch{}}});tx.on('message',onMessage);
      tx.bind(0,ip,()=>{if(closed||transports.get(ip)!==entry)return;try{tx.setBroadcast(true);tx.setMulticastTTL(1);tx.setMulticastInterface(ip);entry.ready=true;send(packet('query'),LAN_GROUP,LAN_PORT,tx);}catch(error){report(error);}});
    }
  }
  function broadcast(kind='hello'){
    if(!ready||closed)return;reconcile();const bytes=packet(kind);
    for(const entry of transports.values())if(entry.ready){
      send(bytes,LAN_GROUP,LAN_PORT,entry.socket);send(bytes,'255.255.255.255',LAN_PORT,entry.socket);
      if(entry.iface.netmask)send(bytes,address((ipv4(entry.iface.address)|(~ipv4(entry.iface.netmask)))>>>0),LAN_PORT,entry.socket);
    }
  }
  socket.on('error',report);
  function onMessage(bytes,remote){
    if(closed||bytes.length>1200||!isIPv4(remote.address))return;
    let message;try{message=JSON.parse(bytes.toString('utf8'));}catch{return;}
    if(message.app!=='flowdrop'||message.discovery!==1||!['hello','query','bye'].includes(message.kind)||typeof message.id!=='string'||!/^[a-z0-9-]{1,80}$/i.test(message.id)||message.id===deviceId||!Number.isInteger(message.port)||message.port<1||message.port>65535)return;
    const origin='http://'+remote.address+':'+message.port,now=Date.now(),old=peers.get(message.id);
    if(message.kind==='bye'){if(old?.url===origin)peers.delete(message.id);return;}
    if(message.kind==='query')send(packet('hello'),remote.address,remote.port);
    if(old?.url===origin){old.seen=now;if(now-old.verified<8000)return;}
    const key=message.id+'@'+origin;if(pending.has(key)||now-(attempts.get(key)||0)<2000||pending.size>=16)return;
    if(attempts.size>=128){for(const [key,time] of attempts)if(now-time>20000)attempts.delete(key);if(attempts.size>=128)return;}
    attempts.set(key,now);pending.add(key);
    peerJson(origin,'/api/config').then(config=>{
      if(closed||config.name!=='FlowDrop'||config.deviceId!==message.id||config.deviceId===deviceId)return;
      peers.set(message.id,{id:message.id,name:String(config.deviceName||message.name||'Thiết bị').slice(0,100),platform:config.platform||message.platform,version:config.version||'',url:origin,address:remote.address,port:message.port,seen:Date.now(),verified:Date.now()});
    }).catch(()=>{if(old?.url===origin&&Date.now()-old.verified>16000)peers.delete(message.id);}).finally(()=>pending.delete(key));
  }
  socket.on('message',onMessage);
  socket.bind(LAN_PORT,'0.0.0.0',()=>{if(closed)return;ready=true;socket.setBroadcast(true);socket.setMulticastTTL(1);socket.setMulticastLoopback(true);broadcast('query');timer=setInterval(()=>{broadcast();for(const [id,peer] of peers)if(Date.now()-peer.seen>20000)peers.delete(id);},3000);timer.unref?.();});
  return {peers(){return [...peers.values()].filter(p=>Date.now()-p.seen<20000).map(({seen,verified,...p})=>p);},rename(value){deviceName=value;broadcast('query');},rescan(){broadcast('query');},stop(){if(closed)return;broadcast('bye');closed=true;clearInterval(timer);peers.clear();for(const entry of transports.values())try{entry.socket.close();}catch{}transports.clear();try{socket.close();}catch{}}};
}
