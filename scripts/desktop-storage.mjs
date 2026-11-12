import {access,copyFile,link,mkdir,open,readFile,rename,stat,unlink,writeFile} from 'node:fs/promises';
import {constants,createWriteStream} from 'node:fs';
import {homedir} from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Readable,Transform} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {spawn} from 'node:child_process';
import {validateMetadata} from './request-security.mjs';
import {FOLDER_TYPE,receiveFolder,folderStillSaved} from './folder-receive.mjs';

export function safeReceiveName(input){
  let name=String(input).replace(/[<>:"/\\|?*\x00-\x1f\x7f]/g,'_').replace(/[. ]+$/g,'').trim();
  if(!name)name='file';if(/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name))name='_'+name;
  let extension=path.extname(name);if(Buffer.byteLength(extension)>40)extension='';const stem=extension?name.slice(0,-extension.length):name;
  let limited='';for(const char of stem){if(Buffer.byteLength(limited+char+extension)>190)break;limited+=char;}return (limited||'file')+extension;
}
function powershell(script,extraEnv={}){
  return new Promise((resolve,reject)=>{
    const child=spawn('powershell.exe',['-NoProfile','-STA','-WindowStyle','Hidden','-EncodedCommand',Buffer.from('[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;'+script,'utf16le').toString('base64')],{windowsHide:true,env:{...process.env,...extraEnv}});
    let text='',error='';child.stdout.on('data',b=>{text+=b.toString();});child.stderr.on('data',b=>error+=b.toString());child.on('error',reject);child.on('close',code=>code===0?resolve(text.replace(/^\uFEFF/,'').trim()):reject(new Error(error||'Không mở được hộp chọn thư mục.')));
  });
}
async function defaultReceiveDirectory(){
  if(process.env.FLOWDROP_DEFAULT_RECEIVE_DIR)return process.env.FLOWDROP_DEFAULT_RECEIVE_DIR;
  if(process.platform==='win32')try{
    const downloads=await powershell("$p=(Get-ItemProperty -LiteralPath 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders').'{374DE290-123F-4565-9164-39C4925E467B}';if($p){[Console]::Out.Write([Environment]::ExpandEnvironmentVariables($p))}");
    if(downloads&&path.isAbsolute(downloads))return path.join(downloads,'FlowDrop');
  }catch{}
  return path.join(homedir(),'Downloads','FlowDrop');
}
export class DesktopStorage {
  constructor({dataDirectory,getResponse,defaultDirectory}){this.dataDirectory=dataDirectory;this.getResponse=getResponse;this.defaultDirectory=defaultDirectory;this.tail=Promise.resolve();this.pending=0;this.settingsPath=path.join(dataDirectory,'receive-settings.json');this.receiptPath=path.join(dataDirectory,'receive-receipts.json');}
  async settings(){
    let stored={};try{stored=JSON.parse(await readFile(this.settingsPath,'utf8'));}catch{}
    const directory=typeof stored.directory==='string'&&path.isAbsolute(stored.directory)?stored.directory:this.defaultDirectory||await defaultReceiveDirectory();
    return {directory,autoSave:stored.autoSave!==false};
  }
  async update(input){
    if(typeof input.directory!=='string'||!path.isAbsolute(input.directory)||/[\x00-\x1f]/.test(input.directory)||typeof input.autoSave!=='boolean')throw new Error('Chọn đường dẫn thư mục đầy đủ và chế độ lưu hợp lệ.');
    const directory=path.resolve(input.directory);await mkdir(directory,{recursive:true});await access(directory,constants.W_OK);
    const probe=path.join(directory,'.flowdrop-'+randomUUID()+'.tmp');const handle=await open(probe,'wx',0o600);await handle.close();await unlink(probe);
    const settings={directory,autoSave:input.autoSave};await this.persist(this.settingsPath,settings);return settings;
  }
  async persist(file,value){await mkdir(this.dataDirectory,{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp';try{await writeFile(temporary,JSON.stringify(value),{mode:0o600});await rename(temporary,file);}finally{await unlink(temporary).catch(()=>{});}}
  async chooseDirectory(){
    if(process.platform!=='win32')throw new Error('Hộp chọn thư mục chỉ có trên Windows. Bạn có thể nhập đường dẫn.');
    const selected=await powershell("Add-Type -AssemblyName System.Windows.Forms;$owner=New-Object System.Windows.Forms.Form;$owner.TopMost=$true;$owner.ShowInTaskbar=$false;$owner.Opacity=0;$owner.Show();$d=New-Object System.Windows.Forms.FolderBrowserDialog;$d.Description='Chon thu muc luu file FlowDrop';$d.ShowNewFolderButton=$true;$d.SelectedPath=$env:FLOWDROP_SELECTED_DIR;try{if($d.ShowDialog($owner)-eq[System.Windows.Forms.DialogResult]::OK){[Console]::Out.Write($d.SelectedPath)}}finally{$d.Dispose();$owner.Dispose()}",{FLOWDROP_SELECTED_DIR:(await this.settings()).directory});
    return selected||null;
  }
  async prepareDirectory(){const {directory}=await this.settings();await mkdir(directory,{recursive:true});return directory;}
  async openDirectory(){
    const directory=await this.prepareDirectory();
    if(process.platform!=='win32')throw new Error('Mở thư mục tự động chỉ có trên Windows.');
    await new Promise((resolve,reject)=>{const child=spawn('explorer.exe',[directory],{detached:true,windowsHide:false,stdio:'ignore'});child.once('error',reject);child.once('spawn',()=>{child.unref();resolve();});});return directory;
  }
  receive(code,fileId,getResponse=this.getResponse,source='local',onProgress=()=>{}){
    this.pending++;const run=()=>this.receiveNow(code,fileId,getResponse,source,onProgress);const job=this.tail.then(run,run).finally(()=>{this.pending--;});this.tail=job.catch(()=>{});return job;
  }
  async receiveNow(code,fileId,getResponse=this.getResponse,source='local',onProgress=()=>{}){
    if(!/^[A-Z2-9]{8}$/.test(code)||fileId!==undefined&&!/^[a-f0-9-]{36}$/.test(fileId))throw new Error('Mã nhận hoặc file không hợp lệ.');
    const response=await getResponse('/api/transfers/'+code);const metadata=await response.json();if(!response.ok)throw new Error(metadata.error||'Không nhận được file.');validateMetadata(metadata,code);
    const selected=fileId?metadata.files.filter(f=>f.id===fileId):metadata.files;if(!selected.length)throw new Error('Không tìm thấy file.');
    const {directory}=await this.settings();await mkdir(directory,{recursive:true});let receipts={};try{receipts=JSON.parse(await readFile(this.receiptPath,'utf8'));}catch{}
    const saved=[];let completed=0,lastProgress=0;
    const report=(file,bytes,done=false)=>{const now=Date.now();if(done||bytes===0||now-lastProgress>=200){lastProgress=now;onProgress({bytes:completed+bytes,filesDone:saved.length,currentName:file.name});}};
    for(const file of selected){
      report(file,0);
      const receiptKey=source+'/'+code+'/'+file.id+'/'+directory,previous=receipts[receiptKey];
      if(previous&&path.dirname(previous.path)===directory)try{if(previous.kind==='folder'?file.type===FOLDER_TYPE&&previous.size===file.size&&await folderStillSaved(previous):file.type!==FOLDER_TYPE&&(await stat(previous.path)).size===file.size){saved.push({...previous,id:file.id,alreadySaved:true});report(file,file.size,true);completed+=file.size;continue;}}catch{}
      const download=await getResponse('/api/transfers/'+code+'/files/'+file.id);if(!download.ok)throw new Error((await download.json()).error||'Không tải được file.');
      const temporary=path.join(directory,'.flowdrop-'+randomUUID()+'.part');let bytes=0;
      const limit=new Transform({transform(chunk,encoding,next){bytes+=chunk.length;if(bytes>file.size)return next(new Error('Dung lượng file không khớp.'));report(file,bytes);next(null,chunk);}});
      try{
        await pipeline(Readable.fromWeb(download.body),limit,createWriteStream(temporary,{flags:'wx',mode:0o600}));
        if(bytes!==file.size)throw new Error('File chưa tải đủ. Hãy thử lại.');
        if(file.type===FOLDER_TYPE){
          const folder=await receiveFolder(temporary,directory,this.dataDirectory,entry=>onProgress({bytes:completed+bytes,filesDone:saved.length,currentName:'Đang tạo thư mục · '+entry.name}));
          const item={...folder,id:file.id,size:bytes};saved.push(item);receipts[receiptKey]=item;await this.persist(this.receiptPath,receipts);report(file,bytes,true);completed+=bytes;continue;
        }
        const original=safeReceiveName(file.name),extension=path.extname(original),stem=original.slice(0,original.length-extension.length);let target;
        for(let i=0;i<10000;i++){
          const candidate=path.join(directory,i===0?original:stem+' ('+i+')'+extension);
          try{try{await link(temporary,candidate);}catch(e){if(e.code==='EEXIST')throw e;await copyFile(temporary,candidate,constants.COPYFILE_EXCL);}target=candidate;break;}
          catch(e){if(e.code!=='EEXIST')throw e;}
        }
        if(!target)throw new Error('Có quá nhiều file trùng tên. Chọn thư mục khác.');
        const item={id:file.id,name:path.basename(target),path:target,size:bytes};saved.push(item);receipts[receiptKey]=item;
        const keys=Object.keys(receipts);for(const key of keys.slice(0,Math.max(0,keys.length-500)))delete receipts[key];await this.persist(this.receiptPath,receipts);report(file,bytes,true);completed+=bytes;
      }finally{await unlink(temporary).catch(()=>{});}
    }
    return {directory,files:saved};
  }
}
