import {lstat,readdir,open,unlink,mkdir} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {crc32} from 'node:zlib';
import path from 'node:path';
const LIMIT=0xffffffffn,MAX=9007199254740991n;
const u16=n=>{const b=Buffer.alloc(2);b.writeUInt16LE(n);return b;};
const u32=n=>{const b=Buffer.alloc(4);b.writeUInt32LE(Number(n));return b;};
const u64=n=>{const b=Buffer.alloc(8);b.writeBigUInt64LE(BigInt(n));return b;};
function stamp(value){const d=new Date(value),year=Math.max(1980,Math.min(2107,d.getFullYear()));return {time:(d.getHours()<<11)|(d.getMinutes()<<5)|(d.getSeconds()>>1),date:((year-1980)<<9)|((d.getMonth()+1)<<5)|d.getDate()};}
function component(name){if(!name||name==='.'||name==='..'||/[\\/\x00-\x1f]/.test(name))throw new Error('Tên thư mục/file không thể đóng gói an toàn.');return name;}
/** Streaming ZIP/ZIP64. No file contents are retained in memory; links are never followed. */
export async function zipFolder(source,destination,onProgress=()=>{},signal){
  source=path.resolve(source);const root=await lstat(source);
  if(root.isSymbolicLink()||!root.isDirectory())throw new Error('Chọn một thư mục thông thường, không phải liên kết.');
  const entries=[];let total=0n;
  async function walk(file,name){
    signal?.throwIfAborted();const info=await lstat(file);
    if(info.isSymbolicLink())throw new Error('Thư mục có liên kết: '+name+'. Hãy bỏ liên kết rồi gửi lại.');
    if(info.isDirectory()){
      entries.push({file,name:name+'/',size:0n,info,dir:true});
      for(const child of (await readdir(file)).sort())await walk(path.join(file,child),name+'/'+component(child));
    }else if(info.isFile()){
      const size=BigInt(info.size);total+=size;if(total>MAX)throw new Error('Dung lượng vượt phạm vi giao thức.');
      entries.push({file,name,size,info,dir:false});
    }else throw new Error('Không gửi được loại file đặc biệt: '+name);
  }
  await walk(source,component(path.basename(source)));
  // Never write an archive inside its source tree.
  const relative=path.relative(source,path.resolve(destination));
  if(relative===''||(!relative.startsWith('..'+path.sep)&&relative!=='..'&&!path.isAbsolute(relative)))throw new Error('Bản ZIP tạm phải nằm ngoài thư mục gửi.');
  await mkdir(path.dirname(destination),{recursive:true});const out=await open(destination,'wx',0o600);
  let offset=0n,completed=0n,last=0;const central=[];
  async function write(bytes){let position=0;while(position<bytes.length){signal?.throwIfAborted();const {bytesWritten}=await out.write(bytes,position,bytes.length-position);if(!bytesWritten)throw new Error('Không ghi được ZIP tạm.');position+=bytesWritten;offset+=BigInt(bytesWritten);if(offset>MAX)throw new Error('ZIP vượt phạm vi giao thức.');}}
  try{
    for(const entry of entries){
      const name=Buffer.from(entry.name,'utf8');if(name.length>65535)throw new Error('Đường dẫn trong thư mục quá dài.');
      const large=entry.size>=LIMIT,flags=0x800|(entry.dir?0:8),version=large?45:20,start=offset,{time,date}=stamp(entry.info.mtime);
      const extra=large?Buffer.concat([u16(1),u16(16),u64(entry.size),u64(entry.size)]):Buffer.alloc(0);
      await write(Buffer.concat([u32(0x04034b50),u16(version),u16(flags),u16(0),u16(time),u16(date),u32(0),u32(large?LIMIT:entry.size),u32(large?LIMIT:entry.size),u16(name.length),u16(extra.length),name,extra]));
      let crc=0,read=0n;
      if(!entry.dir){
        for await(const chunk of createReadStream(entry.file,{highWaterMark:65536})){
          signal?.throwIfAborted();read+=BigInt(chunk.length);if(read>entry.size)throw new Error('File đã thay đổi: '+entry.name);
          crc=crc32(chunk,crc);await write(chunk);
          if(Date.now()-last>200){last=Date.now();onProgress({bytes:Number(completed+read),size:Number(total),currentName:entry.name});}
        }
        const after=await lstat(entry.file);if(read!==entry.size||after.isSymbolicLink()||after.size!==entry.info.size||after.mtimeMs!==entry.info.mtimeMs)throw new Error('File đã thay đổi: '+entry.name);
        await write(Buffer.concat([u32(0x08074b50),u32(crc),large?u64(read):u32(read),large?u64(read):u32(read)]));
      }
      completed+=read;central.push({name,size:entry.size,flags,version,start,time,date,crc,dir:entry.dir});
    }
    const centralOffset=offset;
    for(const item of central){
      const values=[];if(item.size>=LIMIT)values.push(u64(item.size),u64(item.size));if(item.start>=LIMIT)values.push(u64(item.start));
      const extra=values.length?Buffer.concat([u16(1),u16(values.length*8),...values]):Buffer.alloc(0),version=values.length?45:item.version;
      const attrs=((item.dir?0o40755:0o100644)*65536+(item.dir?0x10:0))>>>0;
      await write(Buffer.concat([u32(0x02014b50),u16(0x300|version),u16(version),u16(item.flags),u16(0),u16(item.time),u16(item.date),u32(item.crc),u32(item.size>=LIMIT?LIMIT:item.size),u32(item.size>=LIMIT?LIMIT:item.size),u16(item.name.length),u16(extra.length),u16(0),u16(0),u16(0),u32(attrs),u32(item.start>=LIMIT?LIMIT:item.start),item.name,extra]));
    }
    const centralSize=offset-centralOffset,count=BigInt(central.length);
    if(centralOffset>=LIMIT||centralSize>=LIMIT||count>=65535n){
      const end=offset;await write(Buffer.concat([u32(0x06064b50),u64(44),u16(45),u16(45),u32(0),u32(0),u64(count),u64(count),u64(centralSize),u64(centralOffset)]));
      await write(Buffer.concat([u32(0x07064b50),u32(0),u64(end),u32(1)]));
    }
    await write(Buffer.concat([u32(0x06054b50),u16(0),u16(0),u16(Number(count>=65535n?65535n:count)),u16(Number(count>=65535n?65535n:count)),u32(centralSize>=LIMIT?LIMIT:centralSize),u32(centralOffset>=LIMIT?LIMIT:centralOffset),u16(0)]));
    await out.close();onProgress({bytes:Number(completed),size:Number(total),currentName:''});
    return {path:destination,name:path.basename(source)+'.zip',size:Number(offset),files:entries.filter(e=>!e.dir).length};
  }catch(error){await out.close().catch(()=>{});await unlink(destination).catch(()=>{});throw error;}
}
