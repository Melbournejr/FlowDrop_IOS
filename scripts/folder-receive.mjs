import {mkdir,mkdtemp,rm,readdir,rename,lstat,readFile,writeFile,statfs} from 'node:fs/promises';
import {createWriteStream} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {Transform} from 'node:stream';
import {crc32} from 'node:zlib';
import {randomUUID} from 'node:crypto';
import path from 'node:path';
import yauzl from 'yauzl';

export const FOLDER_TYPE='application/vnd.flowdrop.folder+zip';
function part(name){
  if(!name||name==='.'||name==='..'||/[\\/\x00-\x1f\x7f]/.test(name))throw new Error('Đường dẫn trong thư mục không hợp lệ.');
  if(process.platform==='win32'&&(/[<>:"|?*]/.test(name)||/[. ]$/.test(name)||/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name)||name.length>255))throw new Error('Windows không hỗ trợ tên: '+name);
  return name;
}
export async function folderStillSaved(item){
  try{
    if(!(await lstat(item.path)).isDirectory()||(await lstat(item.path)).isSymbolicLink())return false;
    const entries=JSON.parse(await readFile(item.inventory,'utf8'));
    for(const entry of entries){const components=entry.name.split('/').map(part),file=path.join(item.path,...components);const info=await lstat(file);if(info.isSymbolicLink()||(entry.dir?!info.isDirectory():!info.isFile()||info.size!==entry.size))return false;}
    return true;
  }catch{return false;}
}
/** Restore only explicitly marked folder packages into an isolated staging tree. */
export async function receiveFolder(archive,directory,dataDirectory,onProgress=()=>{}){
  const staging=await mkdtemp(path.join(directory,'.flowdrop-folder-'));let destination,inventoryFile;
  let zip,root,count=0,total=0;const seen=new Set(),inventory=[];
  try{
    zip=await yauzl.openPromise(archive,{strictFileNames:true,validateEntrySizes:true,autoClose:false});
    for await(const entry of zip.eachEntry()){
      const dir=entry.fileName.endsWith('/'),name=dir?entry.fileName.slice(0,-1):entry.fileName,components=name.split('/').map(part);
      if(!root){if(!dir||components.length!==1)throw new Error('Gói thư mục thiếu thư mục gốc.');root=components[0];}
      if(components[0]!==root)throw new Error('Gói chứa nhiều thư mục gốc.');
      const identity=process.platform==='win32'?name.toLowerCase():name;
      if(seen.has(identity))throw new Error('Gói có tên bị trùng: '+name);seen.add(identity);
      const mode=(entry.externalFileAttributes>>>16)&0xf000;
      if(entry.isEncrypted()||mode&&mode!==(dir?0x4000:0x8000)||!Number.isSafeInteger(entry.uncompressedSize)||entry.uncompressedSize<0||entry.uncompressedSize>Number.MAX_SAFE_INTEGER-total||dir&&entry.uncompressedSize!==0)throw new Error('Gói thư mục chứa dữ liệu không hỗ trợ.');
      const space=await statfs(staging);if(entry.uncompressedSize+64*1024*1024>space.bavail*space.bsize)throw new Error('Không đủ dung lượng trống để khôi phục thư mục an toàn.');
      const target=path.join(staging,...components);await mkdir(dir?target:path.dirname(target),{recursive:true});
      if(components.length>1)inventory.push({name:components.slice(1).join('/'),dir,size:entry.uncompressedSize});
      if(dir)continue;
      let bytes=0,crc=0;const input=await zip.openReadStreamPromise(entry);
      const check=new Transform({transform(chunk,encoding,next){try{bytes+=chunk.length;crc=crc32(chunk,crc);onProgress({name,bytes:total+bytes});next(null,chunk);}catch(error){next(error);}}});
      await pipeline(input,check,createWriteStream(target,{flags:'wx',mode:0o600}));
      if(bytes!==entry.uncompressedSize||crc!==entry.crc32)throw new Error('File trong thư mục bị thiếu hoặc sai CRC: '+name);
      total+=bytes;count++;
    }
    zip.close();zip=null;if(!root)throw new Error('Gói thư mục rỗng không hợp lệ.');
    // Reserve a fresh root name exclusively; existing folder contents are never merged.
    for(let i=0;i<10000;i++){const candidate=path.join(directory,i?root+' ('+i+')':root);try{await mkdir(candidate);destination=candidate;break;}catch(error){if(error.code!=='EEXIST')throw error;}}
    if(!destination)throw new Error('Có quá nhiều thư mục trùng tên.');
    const source=path.join(staging,root);for(const child of await readdir(source))await rename(path.join(source,child),path.join(destination,child));
    const receipts=path.join(dataDirectory,'folder-receipts');await mkdir(receipts,{recursive:true});inventoryFile=path.join(receipts,randomUUID()+'.json');await writeFile(inventoryFile,JSON.stringify(inventory),{mode:0o600});
    return {kind:'folder',name:path.basename(destination),path:destination,filesCount:count,unpackedSize:total,inventory:inventoryFile};
  }catch(error){if(destination)await rm(destination,{recursive:true,force:true}).catch(()=>{});if(inventoryFile)await rm(inventoryFile,{force:true}).catch(()=>{});throw error;}
  finally{zip?.close();await rm(staging,{recursive:true,force:true});}
}
