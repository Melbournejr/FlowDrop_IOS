import {readFile,writeFile,rename} from 'node:fs/promises';
import path from 'node:path';
export function validateDeviceName(value){
  if(typeof value!=='string'||/[\x00-\x1f\x7f\u2028\u2029]/u.test(value))throw new Error('Tên thiết bị không được chứa ký tự điều khiển.');
  const name=value.trim();if(!name||[...name].length>50)throw new Error('Tên thiết bị cần từ 1 đến 50 ký tự.');return name;
}
export class DeviceName {
  constructor(directory,fallback){this.file=path.join(directory,'device-settings.json');this.fallback=[...String(fallback).replace(/[\x00-\x1f\x7f\u2028\u2029]/gu,' ').trim()].slice(0,50).join('')||'FlowDrop';this.pending=Promise.resolve();}
  async load(){try{return validateDeviceName(JSON.parse(await readFile(this.file,'utf8')).name);}catch{return this.fallback;}}
  save(value){const name=validateDeviceName(value);const task=this.pending.catch(()=>{}).then(async()=>{await writeFile(this.file+'.tmp',JSON.stringify({name}),{mode:0o600});await rename(this.file+'.tmp',this.file);return name;});this.pending=task;return task;}
}
