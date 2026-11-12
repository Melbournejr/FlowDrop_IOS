import http from 'node:http';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {readFile,writeFile,mkdir,readdir,stat,unlink} from 'node:fs/promises';
import path from 'node:path';
import {networkInterfaces,hostname} from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import worker from '../worker/index.js';
import {startLanDiscovery} from './lan-discovery.mjs';
import {advertiseFlowDrop} from './discovery.mjs';
import {DesktopStorage} from './desktop-storage.mjs';
import {PeerOffers} from './peer-offers.mjs';
import {localBucket} from './local-bucket.mjs';
import {findCode} from './code-lookup.mjs';
import {FolderJobs} from './folder-jobs.mjs';
import {sameSecret,loopback,browserRequestAllowed} from './request-security.mjs';
import {DeviceName} from './device-name.mjs';
import {DesktopUpdater} from './secure-update.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),data=process.env.FLOWDROP_DATA_DIR||path.join(root,'.local-data');await mkdir(data,{recursive:true,mode:0o700});
const identity=new DeviceName(data,process.env.FLOWDROP_DEVICE_NAME||hostname());let deviceName=await identity.load();
const desktopToken=randomUUID(),stateFile=path.join(data,'desktop-state.json');
let discovery=null,lanDiscovery=null;
const discoveredPeers=()=>[...new Map([...(discovery?.peers()||[]),...(lanDiscovery?.peers()||[])].map(p=>[p.id,p])).values()].sort((a,b)=>a.name.localeCompare(b.name));
let deviceId;try{deviceId=(await readFile(path.join(data,'device-id'),'utf8')).trim();}catch{deviceId=randomUUID();await writeFile(path.join(data,'device-id'),deviceId);}
const addresses=()=>Object.entries(networkInterfaces()).flatMap(([name,list])=>(list||[]).filter(a=>a.family==='IPv4'&&!a.internal&&!a.address.startsWith('169.254.')).map(a=>({name,address:a.address}))).sort((a,b)=>Number(!/wi-fi|wlan|wireless/i.test(a.name))-Number(!/wi-fi|wlan|wireless/i.test(b.name)));
function openBrowser(url){if(process.platform==='win32')spawn('rundll32.exe',['url.dll,FileProtocolHandler',url],{detached:true,stdio:'ignore'}).unref();}
const bucket=await localBucket(data);
const folders=new FolderJobs(data);folders.cleanup().catch(()=>{});
const storage=new DesktopStorage({dataDirectory:data,getResponse:pathname=>worker.fetch(new Request('http://flowdrop.local'+pathname),{BUCKET:bucket},{})});
const offers=new PeerOffers({deviceId,deviceName,port:()=>server.address().port,getPeers:discoveredPeers,storage});
let bulkRequests=0;
const busy=()=>folders.busy()||bulkRequests>0||storage.pending>0||offers.sessions().some(s=>['pending','accepted','transferring'].includes(s.state));
const updater=new DesktopUpdater({dataDirectory:data,busy,enabled:process.env.FLOWDROP_DISABLE_UPDATES!=='1'});
if(process.platform==='win32'&&process.env.FLOWDROP_DESKTOP_NATIVE==='1')updater.start().catch(()=>{});
const json=(res,status,value)=>{if(status>=400)res.shouldKeepAlive=false;res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cross-Origin-Resource-Policy':'same-origin','Referrer-Policy':'no-referrer','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(value));};
async function smallJson(req){const chunks=[];let bytes=0;for await(const chunk of req){bytes+=chunk.length;if(bytes>16384)throw new Error('Yêu cầu quá lớn.');chunks.push(chunk);}return bytes?JSON.parse(Buffer.concat(chunks).toString('utf8')):{};}
function localDesktop(req,url){const client=req.socket.remoteAddress?.replace(/^::ffff:/,'');const own=['127.0.0.1','::1',...addresses().map(a=>a.address)];return own.includes(client)&&['localhost',...own].includes(url.hostname.replace(/^\[|\]$/g,''))&&url.port===String(server.address().port);}
const files={'/':['web/index.html','text/html; charset=utf-8'],'/app.js':['web/app.js','text/javascript; charset=utf-8'],'/style.css':['web/style.css','text/css; charset=utf-8']};
const server=http.createServer({maxHeaderSize:16384,headersTimeout:10000,requestTimeout:0,connectionsCheckingInterval:1000},async(req,res)=>{
 try{
  if(!req.url.startsWith('/')||req.url.startsWith('//')||typeof req.headers.host!=='string'){json(res,400,{error:'Yêu cầu không hợp lệ.'});return;}
  for(const name of ['host','origin','x-desktop-token','x-upload-token']){let count=0;for(let i=0;i<req.rawHeaders.length;i+=2)if(req.rawHeaders[i].toLowerCase()===name)count++;if(count>1){json(res,400,{error:'Header trùng lặp.'});return;}}
  const url=new URL(req.url,'http://'+req.headers.host);
  const allowedHosts=['localhost','127.0.0.1','::1',...addresses().map(a=>a.address)];
  if(!allowedHosts.includes(url.hostname.replace(/^\[|\]$/g,''))||url.port!==String(server.address().port)){json(res,403,{error:'Địa chỉ truy cập không được phép.'});return;}
  if(url.pathname.startsWith('/api/')&&!browserRequestAllowed(req.headers,url.origin)){json(res,403,{error:'Yêu cầu từ website khác bị chặn.'});return;}
  if(url.pathname==='/api/transfers'&&req.method==='POST'&&(!loopback(req.socket.remoteAddress)||process.env.FLOWDROP_DESKTOP_NATIVE==='1'&&!sameSecret(req.headers['x-desktop-token'],desktopToken))){json(res,403,{error:'Chỉ ứng dụng FlowDrop trên máy này được tạo phiên gửi.'});return;}

  if(url.pathname.startsWith('/api/desktop/')&&url.pathname!=='/api/desktop/stop'){
    if(!localDesktop(req,url)){json(res,403,{error:'Cài đặt này chỉ dùng trên máy tính đang chạy FlowDrop.'});return;}
    if(req.method==='GET'&&url.pathname==='/api/desktop/settings'){if(process.env.FLOWDROP_DESKTOP_NATIVE==='1'&&(!loopback(req.socket.remoteAddress)||!sameSecret(req.headers['x-desktop-token'],desktopToken))){json(res,403,{error:'Thiếu quyền truy cập ứng dụng trên máy này.'});return;}json(res,200,{...await storage.settings(),token:desktopToken,deviceName});return;}
    if(req.method!=='POST'||!sameSecret(req.headers['x-desktop-token'],desktopToken)||req.headers.origin&&req.headers.origin!==url.origin){json(res,403,{error:'Không có quyền thay đổi hoặc lưu file trên máy tính.'});return;}
    try{
      if(url.pathname==='/api/desktop/peers'){const body=await smallJson(req);if(body.rescan){discovery?.rescan();lanDiscovery?.rescan();}json(res,200,{peers:discoveredPeers(),offers:offers.list(),sessions:offers.sessions(),deviceName,update:updater.snapshot()});updater.resume();return;}
      if(updater.state.phase==='installing'&&['/api/desktop/send-offer','/api/desktop/answer-offer','/api/desktop/archive-folder','/api/desktop/receive'].includes(url.pathname))throw new Error('Đang cài cập nhật. Mở lại FlowDrop sau khi cài xong.');
      if(url.pathname==='/api/desktop/send-offer'){const body=await smallJson(req);json(res,200,await offers.send(body.peerId,body.code));return;}
      if(url.pathname==='/api/desktop/answer-offer'){const body=await smallJson(req);json(res,200,await offers.answer(body.id,body.accept===true));return;}
      if(url.pathname==='/api/desktop/settings'){json(res,200,await storage.update(await smallJson(req)));return;}
      if(url.pathname==='/api/desktop/device-name'){const body=await smallJson(req);deviceName=await identity.save(body.name);offers.deviceName=deviceName;discovery?.rename(deviceName);lanDiscovery?.rename(deviceName);json(res,200,{deviceName});return;}
      if(url.pathname==='/api/desktop/update/accept'){json(res,200,updater.accept(await smallJson(req)));return;}
      if(url.pathname==='/api/desktop/update/later'){json(res,200,updater.later());return;}
      if(url.pathname==='/api/desktop/update/check'){json(res,200,updater.check(true));return;}
      if(url.pathname==='/api/desktop/update/settings'){const body=await smallJson(req);json(res,200,await updater.configure(body.automatic));return;}
      if(url.pathname==='/api/desktop/update/failed'){json(res,200,updater.installFailed());return;}
      if(url.pathname==='/api/desktop/update/apply'){json(res,200,await updater.prepareInstall());return;}
      if(url.pathname==='/api/desktop/choose-folder'){json(res,200,{directory:await storage.chooseDirectory()});return;}
      if(url.pathname==='/api/desktop/reveal-directory'){json(res,200,{directory:await storage.prepareDirectory()});return;}
      if(url.pathname==='/api/desktop/open-folder'){json(res,200,{directory:await storage.openDirectory()});return;}
      if(url.pathname==='/api/desktop/archive-folder'){const body=await smallJson(req);json(res,200,await folders.create(body.directory));return;}
      if(url.pathname==='/api/desktop/archive-status'){const body=await smallJson(req);json(res,200,folders.snapshot(body.id));return;}
      if(url.pathname==='/api/desktop/receive'){
        const body=await smallJson(req);discovery?.rescan();lanDiscovery?.rescan();
        if(!discoveredPeers().length)await new Promise(resolve=>setTimeout(resolve,1200));
        const found=await findCode(body.code,{getPeers:discoveredPeers,getLocal:storage.getResponse,preferredId:body.peerId});
        json(res,200,await offers.receiveCode(found,body.fileId));return;
      }
      json(res,404,{error:'Không tìm thấy chức năng.'});
    }catch(error){json(res,400,{error:error.message||'Chưa lưu được file.'});}return;
  }
  if(/^\/assets\/fonts\/BeVietnamPro-(Regular|Medium|Bold)\.ttf$/.test(url.pathname)){res.writeHead(200,{'Content-Type':'font/ttf','Cache-Control':'public, max-age=86400'});res.end(await readFile(path.join(root,'web',url.pathname)));return;}
  if(files[url.pathname]){const [file,type]=files[url.pathname];res.writeHead(200,{'Content-Type':type,'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"});res.end(await readFile(path.join(root,file)));return;}
  if(url.pathname==='/favicon.svg'){res.writeHead(200,{'Content-Type':'image/svg+xml'});res.end('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="12" fill="#1b654e"/><path d="M13 18a12 12 0 0 1 21-3l2 2m0-9v9h-9M35 30a12 12 0 0 1-21 3l-2-2m0 9v-9h9" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>');return;}
  if(url.pathname==='/manifest.webmanifest'){res.writeHead(200,{'Content-Type':'application/manifest+json'});res.end(JSON.stringify({name:'FlowDrop',short_name:'FlowDrop',start_url:'/',display:'standalone',theme_color:'#1b654e',background_color:'#f9faf7',icons:[{src:'/favicon.svg',sizes:'any',type:'image/svg+xml'}]}));return;}
  if(url.pathname==='/api/config'){res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({name:'FlowDrop',deviceName,platform:'windows',mode:'local',version:'1.13.0',deviceId,offerKey:offers.key,direct:1,sessions:1,discovery:discovery?'mdns+lan':null,addresses:addresses().map(a=>'http://'+a.address+':'+server.address().port)}));return;}
  if(url.pathname==='/api/offers/status'&&req.method==='POST'){
    if(req.headers.origin&&req.headers.origin!==url.origin){json(res,403,{error:'Yêu cầu khác nguồn không được phép.'});return;}
    try{const body=await smallJson(req);json(res,200,offers.status(body.id,body.token));}catch(error){json(res,403,{error:error.message});}return;
  }
  if(updater.state.phase==='installing'&&(url.pathname==='/api/offers'||url.pathname.startsWith('/api/transfers'))){json(res,503,{error:'FlowDrop đang cài cập nhật. Mở lại ứng dụng sau ít giây.'});return;}
  if(url.pathname==='/api/offers'&&req.method==='POST'){
    if(req.headers.origin&&req.headers.origin!==url.origin){json(res,403,{error:'Yêu cầu khác nguồn không được phép.'});return;}
    try{json(res,201,await offers.incoming(await smallJson(req),req.socket.remoteAddress));}catch(error){json(res,400,{error:error.message});}return;
  }
  if(url.pathname==='/api/desktop/stop'){
   const loopback=['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress);
   if(req.method!=='POST'||!loopback||!sameSecret(req.headers['x-desktop-token'],desktopToken)){res.writeHead(403);res.end();return;}
   res.writeHead(200,{'Content-Type':'application/json'});res.end('{"ok":true}');setTimeout(()=>server.close(async()=>{updater.close();offers.close();lanDiscovery?.stop();await discovery?.stop();process.exit(0);}),100);return;
  }
  if(/^\/api\/transfers\//.test(url.pathname)&&(req.method==='PUT'||/\/files\//.test(url.pathname))){bulkRequests++;let done=false;const finish=()=>{if(!done){done=true;bulkRequests--;}};res.once('close',finish);res.once('finish',finish);}
  const request=new Request(url,{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body:Readable.toWeb(req),duplex:'half'}:{})});
  const response=await worker.fetch(request,{BUCKET:bucket},{waitUntil:p=>p.catch(()=>{})});
  if(res.destroyed)return;
  if(response.status>=400)res.shouldKeepAlive=false;res.writeHead(response.status,Object.fromEntries(response.headers));if(response.body)await pipeline(Readable.fromWeb(response.body),res);else res.end();
 }catch(e){if(res.destroyed)return;if(res.headersSent){res.destroy();return;}console.error(e.message);res.writeHead(500);res.end('Chưa hoàn tất được yêu cầu.');}
});
// A steady large upload can run for hours. Keep only an idle socket timeout.
server.requestTimeout=0;server.headersTimeout=10000;server.maxConnections=128;server.setTimeout(120000);
const hostIndex=process.argv.indexOf('--host'),host=hostIndex>=0?process.argv[hostIndex+1]:'127.0.0.1';
if(!host)throw new Error('Thiếu địa chỉ sau --host');
server.on('error',async e=>{
 if(e.code==='EADDRINUSE'&&process.env.FLOWDROP_DESKTOP==='1'){
  try{const config=await (await fetch('http://127.0.0.1:'+Number(process.env.PORT||5173)+'/api/config')).json();if(config.name==='FlowDrop'&&process.env.FLOWDROP_DESKTOP_NATIVE!=='1'){openBrowser(config.addresses?.[0]||'http://127.0.0.1:'+Number(process.env.PORT||5173));return;}}catch{}
 }
 console.error('Không thể khởi động FlowDrop:',e.message);process.exitCode=1;
});
server.listen(Number(process.env.PORT||5173),host,async()=>{
 const port=server.address().port;
 console.log('FlowDrop: http://127.0.0.1:'+port);
 if(host==='0.0.0.0'){
  discovery=advertiseFlowDrop({port,deviceId,deviceName});
  lanDiscovery=startLanDiscovery({port,deviceId,deviceName});
  console.log('Tự tìm qua Wi-Fi: '+discovery.name);
  console.log('Trên thiết bị khác cùng Wi-Fi, mở một địa chỉ sau:');
  for(const list of Object.values(networkInterfaces()))for(const address of list||[])if(address.family==='IPv4'&&!address.internal)console.log('  http://'+address.address+':'+port);
 }
 if(process.env.FLOWDROP_DESKTOP==='1'){
  await writeFile(stateFile,JSON.stringify({pid:process.pid,port,token:desktopToken}),{mode:0o600});
  if(process.env.FLOWDROP_DESKTOP_NATIVE==='1')console.log('FLOWDROP_READY '+JSON.stringify({port,token:desktopToken}));
  else openBrowser(addresses()[0]?'http://'+addresses()[0].address+':'+port:'http://127.0.0.1:'+port);
 }
});
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{server.close(async()=>{updater.close();offers.close();lanDiscovery?.stop();await discovery?.stop();process.exit(0);});setTimeout(()=>process.exit(0),1500).unref();});
