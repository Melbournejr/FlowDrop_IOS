import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,rm,readdir,lstat,open} from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {zipFolder} from '../scripts/folder-zip.mjs';
import {receiveFolder,FOLDER_TYPE,folderStillSaved} from '../scripts/folder-receive.mjs';
import {DesktopStorage} from '../scripts/desktop-storage.mjs';
import {createHarness,javaCommand,pythonCommand} from './helpers/harness.mjs';
const harness=await createHarness('folder-receive'),root=harness.directory;
after(()=>harness.cleanup());
let classpath;
try{({classpath}=await harness.compileJava(['android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/TransferClient.java','android/src/app/flowdrop/mobile/FolderPackage.java','tests/FolderPackageHarness.java']));}catch(error){await harness.cleanup();throw error;}
const java=(...args)=>spawnSync(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.FolderPackageHarness',...args],{encoding:'utf8',timeout:120000});
async function source(name='Dự án gốc 📁'){const folder=path.join(root,name);await mkdir(path.join(folder,'con','rỗng'),{recursive:true});await writeFile(path.join(folder,'con','Tên file gốc.txt'),'Nội dung nguyên bản');await writeFile(path.join(folder,'Tên file gốc.txt'),'khác');await writeFile(path.join(folder,'zero.bin'),Buffer.alloc(0));const zip=path.join(root,name+'.zip');await zipFolder(folder,zip);return {folder,zip};}
test('folder transfer restores original names and nested/empty directories, reserves root without merging, and verifies receipts',async()=>{
 const {zip}=await source();const directory=path.join(root,'received');await mkdir(path.join(directory,'Dự án gốc 📁'),{recursive:true});await writeFile(path.join(directory,'Dự án gốc 📁','Giữ nguyên.txt'),'old');
 const data=await readFile(zip),file={id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Dự án gốc 📁.zip',size:data.length,type:FOLDER_TYPE};
 const storage=new DesktopStorage({dataDirectory:path.join(root,'state'),defaultDirectory:directory,getResponse:async url=>url.endsWith(file.id)?new Response(data):Response.json({code:url.split('/').at(-1),files:[file]})});
 const first=(await storage.receive('ABCDEFGH')).files[0];assert.equal(first.name,'Dự án gốc 📁 (1)');assert.equal(first.kind,'folder');assert.equal(first.filesCount,3);assert.equal(first.size,data.length);assert.equal(await readFile(path.join(first.path,'con','Tên file gốc.txt'),'utf8'),'Nội dung nguyên bản');assert.equal(await readFile(path.join(first.path,'Tên file gốc.txt'),'utf8'),'khác');assert.ok((await lstat(path.join(first.path,'con','rỗng'))).isDirectory());assert.equal((await lstat(path.join(first.path,'zero.bin'))).size,0);assert.equal(await readFile(path.join(directory,'Dự án gốc 📁','Giữ nguyên.txt'),'utf8'),'old');assert.equal(await folderStillSaved(first),true);
 const again=(await storage.receive('ABCDEFGH')).files[0];assert.equal(again.alreadySaved,true);
 await rm(path.join(first.path,'con','Tên file gốc.txt'));assert.equal(await folderStillSaved(first),false);const repair=(await storage.receive('ABCDEFGH')).files[0];assert.equal(repair.name,'Dự án gốc 📁 (2)');assert.equal(await readFile(path.join(repair.path,'con','Tên file gốc.txt'),'utf8'),'Nội dung nguyên bản');
 file.type='application/zip';const ordinary=(await storage.receive('BCDEFGHJ')).files[0];assert.ok(ordinary.name.endsWith('.zip'));assert.deepEqual(await readFile(ordinary.path),data);assert.equal(ordinary.kind,undefined);
 const javaDest=path.join(root,'java-node');const result=java('extract',zip,javaDest);assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).files,3);assert.equal(await readFile(path.join(javaDest,'Dự án gốc 📁','con','Tên file gốc.txt'),'utf8'),'Nội dung nguyên bản');
});
test('Java deflated folder packages restore on Windows engine with exact names',async()=>{
 const zip=path.join(root,'android.zip');const result=java('create',zip);assert.equal(result.status,0,result.stderr);const destination=path.join(root,'android-to-win');await mkdir(destination);const folder=await receiveFolder(zip,destination,path.join(root,'state-android'));assert.equal(folder.name,'Ảnh dự án');assert.equal(folder.filesCount,2);assert.equal(await readFile(path.join(folder.path,'hình','Tên gốc.txt'),'utf8'),'Nội dung nguyên bản');assert.ok((await lstat(path.join(folder.path,'rỗng'))).isDirectory());
});
test('invalid paths, duplicate names, corrupt CRC and interrupted downloads never become completed folders',async()=>{
 const fixtures=path.join(root,'bad');await mkdir(fixtures);const make=spawnSync(pythonCommand,['-c',`import zipfile,pathlib,sys\np=pathlib.Path(sys.argv[1])\nfor name,entry in [('escape','Thư mục/../outside.txt'),('absolute','/outside.txt'),('drive','C:/outside.txt'),('backslash','Thư mục/..\\\\outside.txt'),('duplicate','Thư mục/a.txt')]:\n with zipfile.ZipFile(p/(name+'.zip'),'w') as z:\n  z.writestr('Thư mục/',b'');z.writestr(entry,b'hello')\n  if name=='duplicate':z.writestr(entry,b'other')\nwith zipfile.ZipFile(p/'crc.zip','w') as z:z.writestr('Thư mục/',b'');z.writestr('Thư mục/a.txt',b'hello')\nf=p/'crc.zip';f.write_bytes(f.read_bytes().replace(b'hello',b'jello',1))`,fixtures],{encoding:'utf8'});assert.equal(make.status,0,make.stderr);
 for(const name of ['escape','absolute','drive','backslash','duplicate','crc']){const folder=path.join(root,'bad-'+name);await mkdir(folder);await assert.rejects(receiveFolder(path.join(fixtures,name+'.zip'),folder,path.join(root,'state-bad')));assert.deepEqual(await readdir(folder),[]);const result=java('extract',path.join(fixtures,name+'.zip'),path.join(root,'java-bad-'+name));assert.notEqual(result.status,0,name);}
 const file={id:'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',name:'truncated.zip',size:100,type:FOLDER_TYPE},destination=path.join(root,'truncated');const storage=new DesktopStorage({dataDirectory:path.join(root,'state-truncated'),defaultDirectory:destination,getResponse:async url=>url.endsWith(file.id)?new Response('short'):Response.json({code:url.split('/').at(-1),files:[file]})});await assert.rejects(storage.receive('CDEFGHJK'));assert.deepEqual(await readdir(destination),[]);
});
test('folder import streams ZIP64 file above 4 GiB in both production readers',async()=>{
 const source=path.join(root,'Lớn');await mkdir(source);const size=2**32+131089,file=await open(path.join(source,'lớn.bin'),'w');await file.truncate(size);await file.write(Buffer.from('A'),0,1,0);await file.write(Buffer.from('Z'),0,1,size-1);await file.close();const zip=path.join(root,'large.zip');const destination=path.join(root,'large-dest');await mkdir(destination);
 try{await zipFolder(source,zip);const saved=await receiveFolder(zip,destination,path.join(root,'large-state'));assert.equal((await lstat(path.join(saved.path,'lớn.bin'))).size,size);const handle=await open(path.join(saved.path,'lớn.bin'),'r');const bytes=Buffer.alloc(1);await handle.read(bytes,0,1,size-1);await handle.close();assert.equal(bytes.toString(),'Z');await rm(saved.path,{recursive:true});const result=java('extract',zip,destination);assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).size,size);assert.equal((await lstat(path.join(destination,'Lớn','lớn.bin'))).size,size);}finally{await rm(zip,{force:true});await rm(source,{recursive:true,force:true});await rm(destination,{recursive:true,force:true});}
});
test('ZIP64 inflated size beyond available storage is rejected before file extraction',async()=>{
 const archive=path.join(root,'claimed-petabyte.zip');
 const build=spawnSync(pythonCommand,['-c',`import zipfile,struct,sys\np=sys.argv[1]\nwith zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:\n z.writestr('Root/',b'');z.writestr('Root/data.bin',b'x')\nb=bytearray(open(p,'rb').read());i=b.find(b'PK\\x01\\x02',b.find(b'PK\\x01\\x02')+4);n,e=struct.unpack_from('<HH',b,i+28);struct.pack_into('<I',b,i+24,0xffffffff);struct.pack_into('<H',b,i+30,e+12);at=i+46+n;b[at:at]=struct.pack('<HHQ',1,8,1<<50);end=b.rfind(b'PK\\x05\\x06');size=struct.unpack_from('<I',b,end+12)[0];struct.pack_into('<I',b,end+12,size+12);open(p,'wb').write(b)`,archive],{encoding:'utf8'});assert.equal(build.status,0,build.stderr);
 const destination=path.join(root,'capacity-reject');await mkdir(destination);
 await assert.rejects(receiveFolder(archive,destination,path.join(root,'state-capacity')),/dung lượng/);assert.deepEqual(await readdir(destination),[]);
 const android=java('extract',archive,path.join(root,'android-capacity'));assert.notEqual(android.status,0);assert.match(android.stderr,/dung lượng/);
});
