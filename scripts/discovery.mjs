import {Bonjour} from 'bonjour-service';
import {hostname,networkInterfaces} from 'node:os';
import {isIPv4} from 'node:net';
import {createHash} from 'node:crypto';

// DNS-SD/mDNS is understood by Android's built-in NsdManager.
export function advertiseFlowDrop({port,version='1.13.0',deviceName=hostname(),deviceId=hostname(),platform='windows',onError=console.warn,options={}}){
  const instanceName=value=>{let clean='';for(const char of String(value).replace(/[.\x00-\x1f\x7f]/g,' ').trim()){if(Buffer.byteLength(clean+char)>45)break;clean+=char;}return 'FlowDrop - '+(clean||'Thiết bị');};
  let name=instanceName(deviceName),publishing=false;
  let bonjour,service,browser,timer,closed=false,announcedAddresses;
  const peers=new Map();
  const own=()=>Object.values(networkInterfaces()).flat().filter(Boolean).map(a=>a.address);
  const remember=peer=>{
    if(peer.txt?.app!=='flowdrop'||peer.txt?.protocol!=='1'||peer.txt?.id===deviceId||!peer.port)return;
    const candidates=(peer.addresses||[]).filter(isIPv4);
    const address=candidates.includes(peer.referer?.address)?peer.referer.address:candidates.find(a=>!a.startsWith('127.'))||candidates[0];
    if(!address||peer.port===port&&own().includes(address))return;
    const id=peer.txt.id||peer.fqdn;peers.set(id,{id,name:String(peer.txt.label||peer.name.replace(/^FlowDrop - /,'')).slice(0,100),platform:peer.txt.platform||'device',version:peer.txt.version||'',url:'http://'+address+':'+peer.port,address,port:peer.port,seen:Date.now(),fqdn:peer.fqdn});
  };
  const report=error=>{if(!closed)onError('Tìm thiết bị tự động: '+(error?.message||error));};
  try{
    bonjour=new Bonjour(options,report);
    bonjour.server?.mdns?.on('error',report);
    bonjour.server?.mdns?.on('warning',report);
    const host='flowdrop-'+createHash('sha256').update(deviceId).digest('hex').slice(0,12)+'.local';
    announcedAddresses=own().sort().join(',');
    const publish=()=>{if(closed)return;service=bonjour.publish({name,host,type:'flowdrop',protocol:'tcp',port,disableIPv6:true,txt:{app:'flowdrop',version,protocol:'1',id:deviceId,platform,direct:'1',label:deviceName,ipv4:own().filter(ip=>isIPv4(ip)&&!ip.startsWith('127.')&&!ip.startsWith('169.254.')).slice(0,12).join(',')}});service.on('error',report);};
    var refresh=()=>{if(closed)return;if(publishing)return;publishing=true;const old=service;old.stop(()=>{publishing=false;if(closed)return;publish();});};
    publish();
    browser=bonjour.find({type:'flowdrop',protocol:'tcp'});
    browser.on('up',remember);browser.on('txt-update',remember);
    browser.on('down',peer=>{for(const [id,p] of peers)if(p.fqdn===peer.fqdn)peers.delete(id);});
    // Refresh liveness on every response, including unchanged TXT records.
    bonjour.server.mdns.on('response',(packet,rinfo)=>{
      if(closed)return;
      for(const peer of browser.buildServicesFor('_flowdrop._tcp.local',packet,browser.txt,rinfo))remember(peer);
    });
    timer=setInterval(()=>{const current=own().sort().join(',');if(current!==announcedAddresses){announcedAddresses=current;refresh();}browser.update();for(const [id,p] of peers)if(Date.now()-p.seen>70000)peers.delete(id);},10000);timer.unref?.();
  }catch(error){report(error);}
  return {
    get name(){return name;},
    rename(value){deviceName=value;name=instanceName(value);refresh?.();browser?.update();},
    peers(){return [...peers.values()].filter(p=>Date.now()-p.seen<70000).map(({seen,fqdn,...p})=>p).sort((a,b)=>a.name.localeCompare(b.name));},
    rescan(){browser?.update();},
    stop(){
      if(closed)return Promise.resolve();closed=true;clearInterval(timer);browser?.stop();peers.clear();
      return new Promise(resolve=>{
        let finished=false;
        const finish=()=>{if(finished)return;finished=true;clearTimeout(timer);try{bonjour?.destroy();}catch{}resolve();};
        const timer=setTimeout(finish,800);
        try{if(service)service.stop(finish);else finish();}catch{finish();}
      });
    }
  };
}
