import {createReadStream,createWriteStream} from 'node:fs';
import {readFile,writeFile,mkdir,readdir,stat,statfs,unlink,rename} from 'node:fs/promises';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {randomUUID} from 'node:crypto';
import path from 'node:path';

// R2-compatible disk adapter. File bodies stay in streams, including downloads.
export async function localBucket(directory){
  await mkdir(directory,{recursive:true});
  for(const name of await readdir(directory))if(/^\.upload-[a-f0-9-]+\.part$/.test(name))await unlink(path.join(directory,name)).catch(()=>{});
  const filename=key=>path.join(directory,Buffer.from(key).toString('hex'));
  return {
    async availableSpace(){try{const info=await statfs(directory);return info.bavail*info.bsize;}catch{return null;}},
    async put(key,value){
      const temporary=path.join(directory,'.upload-'+randomUUID()+'.part');
      try{
        if(value instanceof ReadableStream)await pipeline(Readable.fromWeb(value),createWriteStream(temporary,{flags:'wx',mode:0o600}));
        else await writeFile(temporary,value,{flag:'wx',mode:0o600});
        await rename(temporary,filename(key));return {key};
      }finally{await unlink(temporary).catch(()=>{});}
    },
    async get(key){
      const file=filename(key);
      try{
        const info=await stat(file);
        return {size:info.size,get body(){return Readable.toWeb(createReadStream(file));},json:async()=>JSON.parse(await readFile(file,'utf8'))};
      }catch(error){if(error.code==='ENOENT')return null;throw error;}
    },
    async head(key){try{return {size:(await stat(filename(key))).size};}catch(error){if(error.code==='ENOENT')return null;throw error;}},
    async delete(keys){for(const key of Array.isArray(keys)?keys:[keys])await unlink(filename(key)).catch(error=>{if(error.code!=='ENOENT')throw error;});},
    async list({prefix,limit}){return {objects:(await readdir(directory)).filter(name=>/^[a-f0-9]+$/.test(name)).map(name=>Buffer.from(name,'hex').toString()).filter(key=>key.startsWith(prefix)).sort().slice(0,limit).map(key=>({key}))};}
  };
}
