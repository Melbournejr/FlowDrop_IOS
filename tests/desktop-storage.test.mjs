import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,readFile,writeFile,readdir,rm} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {DesktopStorage,safeReceiveName} from '../scripts/desktop-storage.mjs';
test('receiver preserves data, folder settings, duplicate names and already saved files',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'flowdrop-saved-'));
 try{
  const directory=path.join(root,'my downloads');await mkdir(directory);await writeFile(path.join(directory,'Tài liệu.txt'),'original');
  const files=[{id:'a'.repeat(8)+'-aaaa-aaaa-aaaa-'+ 'a'.repeat(12),name:'Tài liệu.txt',size:4},{id:'b'.repeat(8)+'-bbbb-bbbb-bbbb-'+ 'b'.repeat(12),name:'Tài liệu.txt',size:0}];
  const getResponse=async url=>url.endsWith('/api/transfers/ABCDEFGH')?Response.json({code:'ABCDEFGH',files}):url.endsWith(files[0].id)?new Response('data'):new Response(new Uint8Array());
  const storage=new DesktopStorage({dataDirectory:path.join(root,'data'),defaultDirectory:directory,getResponse});assert.equal((await storage.settings()).autoSave,true);
  const first=await storage.receive('ABCDEFGH');assert.deepEqual(first.files.map(f=>f.name),['Tài liệu (1).txt','Tài liệu (2).txt']);assert.equal(await readFile(path.join(directory,'Tài liệu.txt'),'utf8'),'original');assert.equal(await readFile(first.files[0].path,'utf8'),'data');assert.equal((await readFile(first.files[1].path)).length,0);
  const again=await storage.receive('ABCDEFGH');assert.ok(again.files.every(f=>f.alreadySaved));assert.equal((await readdir(directory)).length,3);
  await assert.rejects(storage.update({directory:'relative',autoSave:true}));
  const other=path.join(root,'chosen');await storage.update({directory:other,autoSave:false});const reopened=new DesktopStorage({dataDirectory:path.join(root,'data'),getResponse});assert.deepEqual(await reopened.settings(),{directory:other,autoSave:false});
  await reopened.receive('ABCDEFGH',files[0].id);assert.equal(await readFile(path.join(other,'Tài liệu.txt'),'utf8'),'data');
  await rm(path.join(root,'data'),{recursive:true,force:true});assert.equal(await readFile(first.files[0].path,'utf8'),'data');
 }finally{await rm(root,{recursive:true,force:true});}
});
test('receiver never exposes partial files and handles unsafe or long filenames',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'flowdrop-partial-'));try{
  const file={id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'../bad.txt',size:10};
  const storage=new DesktopStorage({dataDirectory:path.join(root,'data'),defaultDirectory:path.join(root,'saved'),getResponse:async url=>url.endsWith('/api/transfers/ABCDEFGH')?Response.json({code:'ABCDEFGH',files:[file]}):new Response('short')});
  await assert.rejects(storage.receive('ABCDEFGH'),/tải đủ/);assert.deepEqual(await readdir(path.join(root,'saved')),[]);
  for(const unsafe of ['../evil.exe','AUX.txt','file:zone.txt','name?bad.txt']){const safe=safeReceiveName(unsafe);assert.ok(!/[<>:"/\\|?*]/.test(safe));assert.ok(!/^(aux|con|nul|prn)(\.|$)/i.test(safe));}
  const long=safeReceiveName('Ảnh'.repeat(100)+'.jpeg');assert.ok(long.endsWith('.jpeg'));assert.ok(Buffer.byteLength(long)<=190);
 }finally{await rm(root,{recursive:true,force:true});}
});
