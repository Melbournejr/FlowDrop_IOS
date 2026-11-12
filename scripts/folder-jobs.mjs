import {randomUUID} from 'node:crypto';
import {mkdir,readdir,stat,rm} from 'node:fs/promises';
import path from 'node:path';
import {zipFolder} from './folder-zip.mjs';
import {safeReceiveName} from './desktop-storage.mjs';
export class FolderJobs {
  constructor(data){this.root=path.join(data,'prepared-folders');this.jobs=new Map();}
  busy(){return [...this.jobs.values()].some(job=>job.state==='preparing');}
  async create(directory){
    if(typeof directory!=='string'||!path.isAbsolute(directory)||/[\x00-\x1f]/.test(directory))throw new Error('Chọn thư mục bằng hộp chọn Windows.');
    const id=randomUUID(),folder=path.join(this.root,id);await mkdir(folder,{recursive:true});
    const destination=path.join(folder,safeReceiveName(path.basename(directory)+'.zip'));
    const job={id,state:'preparing',name:path.basename(directory),bytes:0,size:0,currentName:'',createdAt:Date.now()};this.jobs.set(id,job);
    zipFolder(directory,destination,progress=>Object.assign(job,progress)).then(result=>Object.assign(job,{state:'ready',result:{...result,name:path.basename(destination)}})).catch(error=>Object.assign(job,{state:'failed',error:error.message}));
    this.cleanup().catch(()=>{});return {id};
  }
  snapshot(id){const job=this.jobs.get(id);if(!job)throw new Error('Phiên đóng gói đã dừng. Chọn lại thư mục.');return {...job};}
  async cleanup(){
    for(const id of await readdir(this.root).catch(()=>[])){
      if(!/^[a-f0-9-]{36}$/.test(id)||this.jobs.get(id)?.state==='preparing')continue;
      const folder=path.join(this.root,id);if(Date.now()-(await stat(folder)).mtimeMs>86400000){await rm(folder,{recursive:true,force:true});this.jobs.delete(id);}
    }
  }
}
