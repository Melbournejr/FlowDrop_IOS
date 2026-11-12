import {createHash,verify} from 'node:crypto';
import {mkdir,readFile,writeFile,rename,unlink,stat,open} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import path from 'node:path';
import {UPDATE_FEED,UPDATE_PUBLIC_KEY,APP_VERSION} from './release-config.mjs';
export function compareVersions(a,b){
  if(!/^\d+\.\d+\.\d+$/.test(a)||!/^\d+\.\d+\.\d+$/.test(b))throw new Error('Phiên bản cập nhật không hợp lệ.');
  const x=a.split('.').map(BigInt),y=b.split('.').map(BigInt);for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]>y[i]?1:-1;return 0;
}
export function verifyRelease(envelope,key=UPDATE_PUBLIC_KEY,platform='windows'){
  if(typeof envelope?.payload!=='string'||Buffer.byteLength(envelope.payload)>65536||typeof envelope.signature!=='string'||!verify('RSA-SHA256',Buffer.from(envelope.payload),key,Buffer.from(envelope.signature,'base64')))throw new Error('Thông tin cập nhật không có chữ ký FlowDrop hợp lệ.');
  const payload=JSON.parse(envelope.payload),item=payload.platforms?.[platform];
  if(payload.app!=='FlowDrop'||payload.schema!==1||!item||!/^\d+\.\d+\.\d+$/.test(item.version)||!Number.isSafeInteger(item.size)||item.size<=0||item.size>1024*1024*1024||!/^[a-f0-9]{64}$/.test(item.sha256))throw new Error('Thông tin bộ cài cập nhật không hợp lệ.');
  const url=new URL(item.url);if(url.protocol!=='https:'||url.username||url.password)throw new Error('Cập nhật cần đường dẫn HTTPS.');
  return {...item,notes:String(payload.notes||'').slice(0,4000)};
}
async function httpsFetch(url,fetcher,signal){
  for(let count=0;count<6;count++){
    const target=new URL(url);if(target.protocol!=='https:'||target.username||target.password)throw new Error('Máy chủ cập nhật cần HTTPS.');
    const response=await fetcher(target.href,{redirect:'manual',signal,headers:{'User-Agent':'FlowDrop/'+APP_VERSION,'Accept':'application/octet-stream, application/json'}});
    if([301,302,303,307,308].includes(response.status)){const next=response.headers.get('location');await response.body?.cancel();if(!next)throw new Error('Đường dẫn cập nhật không hợp lệ.');url=new URL(next,target).href;continue;}
    if(!response.ok){await response.body?.cancel();throw new Error('Chưa truy cập được bản cập nhật ('+response.status+').');}return response;
  }
  throw new Error('Đường dẫn cập nhật chuyển tiếp quá nhiều lần.');
}
async function hashFile(file){const hash=createHash('sha256');let size=0;for await(const chunk of createReadStream(file)){hash.update(chunk);size+=chunk.length;}return {size,sha256:hash.digest('hex')};}
export class DesktopUpdater {
  constructor({dataDirectory,version=APP_VERSION,feed=UPDATE_FEED,key=UPDATE_PUBLIC_KEY,fetcher=fetch,busy=()=>false,enabled=true}){
    Object.assign(this,{version,feed,key,fetcher,isBusy:busy});this.directory=path.join(dataDirectory,'updates');this.preferences=path.join(dataDirectory,'update-settings.json');this.state={phase:'idle',version,automatic:enabled,bytes:0,size:0,error:''};this.running=false;this.closed=false;
  }
  async start(){try{const saved=JSON.parse(await readFile(this.preferences,'utf8'));this.state.automatic=saved.automatic!==false;}catch{}
    if(this.state.automatic)this.check();this.timer=setInterval(()=>{if(this.state.automatic)this.check();},6*3600000);this.timer.unref?.();
  }
  close(){this.closed=true;clearInterval(this.timer);this.abort?.abort();}
  snapshot(){return {...this.state,busy:this.isBusy(),canApply:this.state.phase==='ready'&&this.state.accepted&&!this.isBusy()};}
  async configure(automatic){this.state.automatic=automatic===true;await mkdir(path.dirname(this.preferences),{recursive:true});await writeFile(this.preferences,JSON.stringify({automatic:this.state.automatic}),{mode:0o600});if(automatic)this.check();return this.snapshot();}
  check(manual=false){
    if(this.closed)return this.snapshot();
    if(this.running){if(manual&&this.state.phase==='checking')this.state.manual=true;return this.snapshot();}
    if(['deferred','downloading','ready','installing'].includes(this.state.phase))return this.snapshot();
    this.state.checkId=(this.state.checkId||0)+1;this.state.manual=manual;this.state.accepted=false;
    this.state.phase='checking';this.state.error='';this.state.lastChecked=Date.now();
    this.launch(()=>this.run());return this.snapshot();
  }
  launch(action){this.running=true;this.task=action().catch(error=>{if(!this.closed){this.state.phase='error';this.state.accepted=false;this.state.error=error.message;this.state.errorId=(this.state.errorId||0)+1;}}).finally(()=>{this.running=false;});}
  async run(){
    this.abort=new AbortController();const signal=AbortSignal.any([this.abort.signal,AbortSignal.timeout(60000)]);
    const response=await httpsFetch(this.feed,this.fetcher,signal);let text='',bytes=0;
    const decoder=new TextDecoder();for await(const chunk of response.body){bytes+=chunk.length;if(bytes>100000)throw new Error('Thông tin cập nhật quá lớn.');text+=decoder.decode(chunk,{stream:true});}text+=decoder.decode();
    const item=verifyRelease(JSON.parse(text),this.key);if(compareVersions(item.version,this.version)<=0){this.release=null;this.state.phase='current';delete this.state.latest;return;}
    this.release=item;Object.assign(this.state,{phase:'available',latest:item.version,notes:item.notes,size:item.size,bytes:0});
  }
  accept({version,checkId}={}){
    if(this.closed||this.running||this.state.phase!=='available'||version!==this.release?.version||checkId!==this.state.checkId)throw new Error('Thông tin cập nhật đã thay đổi. Kiểm tra lại trước khi cài.');
    this.state.accepted=true;this.state.phase='deferred';this.resume();return this.snapshot();
  }
  later(){if(this.state.phase==='available')this.state.accepted=false;return this.snapshot();}
  resume(){if(!this.closed&&!this.running&&this.state.phase==='deferred'&&this.state.accepted&&!this.isBusy())this.launch(()=>this.download());}
  async download(){
    if(!this.state.accepted||!this.release)throw new Error('Chưa chọn cập nhật.');
    const item=this.release;this.abort=new AbortController();const signal=AbortSignal.any([this.abort.signal,AbortSignal.timeout(15*60*1000)]);
    await mkdir(this.directory,{recursive:true});const destination=path.join(this.directory,'FlowDrop-'+item.version+'-'+item.sha256.slice(0,16)+'.exe');
    try{const existing=await hashFile(destination);if(existing.size===item.size&&existing.sha256===item.sha256){this.installer=destination;this.state.bytes=item.size;this.state.phase='ready';return;}}catch{}
    this.state.phase='downloading';const temporary=destination+'.part';await unlink(temporary).catch(()=>{});
    const output=await open(temporary,'wx',0o600),hash=createHash('sha256');let size=0;
    try{
      const download=await httpsFetch(item.url,this.fetcher,signal);
      const declared=download.headers.get('content-length');if(declared!==null&&Number(declared)!==item.size){await download.body?.cancel();throw new Error('Dung lượng bộ cài không khớp.');}
      for await(const chunk of download.body){size+=chunk.length;if(size>item.size)throw new Error('Bộ cài vượt dung lượng đã ký.');hash.update(chunk);let position=0;while(position<chunk.length){const written=await output.write(chunk,position,chunk.length-position);if(!written.bytesWritten)throw new Error('Không lưu được bản cập nhật.');position+=written.bytesWritten;}this.state.bytes=size;}
      if(size!==item.size||hash.digest('hex')!==item.sha256)throw new Error('Bộ cài chưa đủ dữ liệu hoặc sai SHA256.');
      await output.close();await rename(temporary,destination);this.installer=destination;this.state.phase='ready';
    }catch(error){await output.close().catch(()=>{});await unlink(temporary).catch(()=>{});throw error;}
  }
  installFailed(){if(this.state.phase==='installing'){this.state.phase='available';this.state.accepted=false;}return this.snapshot();}
  async prepareInstall(){
    if(this.state.phase!=='ready'||!this.state.accepted||this.isBusy())throw new Error('Chờ các phiên truyền kết thúc rồi cập nhật.');
    const actual=await hashFile(this.installer);if(actual.size!==this.release.size||actual.sha256!==this.release.sha256){this.state.phase='error';throw new Error('Bộ cài đã thay đổi. Kiểm tra cập nhật lại.');}
    if(this.isBusy()||this.state.phase!=='ready')throw new Error('Chờ các phiên truyền kết thúc rồi cập nhật.');
    this.state.phase='installing';return {path:this.installer,version:this.release.version};
  }
}
