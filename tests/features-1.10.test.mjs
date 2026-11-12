import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,symlink,open,readdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash,generateKeyPairSync,sign,randomUUID} from 'node:crypto';
import {spawnSync,spawn} from 'node:child_process';
import {zipFolder} from '../scripts/folder-zip.mjs';
import {verifyRelease,compareVersions,DesktopUpdater} from '../scripts/secure-update.mjs';
import {findCode} from '../scripts/code-lookup.mjs';
const tools='/workspace/flowdrop-build',jar=tools+'/downloads/json-test.jar';
const dir=await mkdtemp(tools+'/features-1.10-');
after(()=>rm(dir,{recursive:true,force:true}));
const compiled=path.join(dir,'java');await mkdir(compiled);
const build=spawnSync('java',['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',jar,'-d',compiled,'android/src/app/flowdrop/mobile/UpdateManifest.java','android/src/app/flowdrop/mobile/CodeLookup.java','tests/UpdateManifestHarness.java'],{encoding:'utf8'});assert.equal(build.status,0,build.stderr);
const java=(...args)=>new Promise((resolve,reject)=>{const child=spawn('java',['-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.UpdateManifestHarness',...args],{stdio:['ignore','pipe','pipe']});let out='',err='';child.stdout.on('data',b=>out+=b);child.stderr.on('data',b=>err+=b);child.once('exit',code=>code?reject(new Error(err)):resolve(JSON.parse(out)));});
test('ZIP preserves Unicode, nested/empty folders, empty files; refuses links and cancellation',async()=>{
 const source=path.join(dir,'Thư mục 📁');await mkdir(path.join(source,'con','rỗng'),{recursive:true});await writeFile(path.join(source,'con','nội dung.txt'),'Dữ liệu thử nghiệm\n');await writeFile(path.join(source,'zero'),Buffer.alloc(0));
 const archive=path.join(dir,'normal.zip');const zipped=await zipFolder(source,archive);assert.equal(zipped.files,2);
 const validate=spawnSync('python',['-c',`import zipfile,sys\nwith zipfile.ZipFile(sys.argv[1]) as z:\n assert z.testzip() is None\n assert z.read('Thư mục 📁/con/nội dung.txt').decode()=='Dữ liệu thử nghiệm\\n'\n assert z.read('Thư mục 📁/zero')==b''\n assert z.getinfo('Thư mục 📁/con/rỗng/').is_dir()`,archive],{encoding:'utf8'});assert.equal(validate.status,0,validate.stderr);
 await assert.rejects(zipFolder(source,path.join(source,'nested.zip')),/ngoài/);
 await symlink(path.join(source,'zero'),path.join(source,'link'));await assert.rejects(zipFolder(source,path.join(dir,'links.zip')),/liên kết/);await rm(path.join(source,'link'));
 const abort=new AbortController();abort.abort();await assert.rejects(zipFolder(source,path.join(dir,'cancel.zip'),()=>{},abort.signal));
});
test('ZIP64 streams a file above 4 GiB and validates independently with Python',async()=>{
 const source=path.join(dir,'large');await mkdir(source);const size=2**32+131089,handle=await open(path.join(source,'large.bin'),'w');await handle.truncate(size);await handle.write(Buffer.from('A'),0,1,0);await handle.write(Buffer.from('Z'),0,1,size-1);await handle.close();const archive=path.join(dir,'large.zip');
 try{const result=await zipFolder(source,archive);assert.ok(result.size>size);const verify=spawnSync('python',['-c',`import zipfile,sys\nwith zipfile.ZipFile(sys.argv[1]) as z:\n info=z.getinfo('large/large.bin');assert info.file_size==int(sys.argv[2]);assert info.extract_version==45\n assert z.testzip() is None\n with z.open(info) as f:\n  assert f.read(1)==b'A';f.seek(info.file_size-1);assert f.read()==b'Z'`,archive,String(size)],{encoding:'utf8',timeout:120000});assert.equal(verify.status,0,verify.stderr);}finally{await rm(source,{recursive:true,force:true});await rm(archive,{force:true});}
});
test('Windows and Android verify the same signed release; tampering/invalid URLs rejected',async()=>{
 const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:2048}),key=publicKey.export({type:'spki',format:'pem'}),androidKey=publicKey.export({type:'spki',format:'der'}).toString('base64');
 const bytes=Buffer.from('installer fixture'),sha256=createHash('sha256').update(bytes).digest('hex');
 const item={version:'1.11.0',url:'https://github.com/test/releases/download/v1.11.0/setup.exe',size:bytes.length,sha256};
 const envelope=(change={})=>{const payload=JSON.stringify({schema:1,app:'FlowDrop',platforms:{windows:{...item,...change},android:{...item,versionCode:12,...change}}});return {payload,signature:sign('RSA-SHA256',Buffer.from(payload),privateKey).toString('base64')};};
 const valid=envelope();assert.equal(verifyRelease(valid,key).version,'1.11.0');const file=path.join(dir,'manifest.json');await writeFile(file,JSON.stringify(valid));assert.equal((await java('manifest',file,androidKey)).versionCode,12);
 for(const value of [{...valid,payload:valid.payload.replace('1.11.0','9.0.0')},{...valid,signature:'AAAA'},envelope({url:'http://unsafe.test/setup.exe'}),envelope({size:0})]){assert.throws(()=>verifyRelease(value,key));await writeFile(file,JSON.stringify(value));await assert.rejects(java('manifest',file,androidKey));}
 assert.equal(compareVersions('1.10.0','1.9.0'),1);assert.equal(compareVersions('1.10.0','1.10.0'),0);
 let busy=true,badHash=false,truncated=false,httpRedirect=false,downloadCalls=0;
 const fetcher=async url=>{if(url.includes('latest.json'))return new Response(JSON.stringify(valid));downloadCalls++;if(httpRedirect)return new Response(null,{status:302,headers:{Location:'http://unsafe.test/setup.exe'}});return new Response(truncated?bytes.subarray(1):badHash?Buffer.alloc(bytes.length):bytes);};
 const updater=new DesktopUpdater({dataDirectory:path.join(dir,'update'),version:'1.10.0',feed:'https://github.com/latest.json',key,fetcher,busy:()=>busy});
 updater.check(true);await updater.task;assert.equal(updater.snapshot().phase,'available');assert.equal(downloadCalls,0);
 updater.later();assert.equal(downloadCalls,0);assert.equal(updater.snapshot().canApply,false);
 assert.throws(()=>updater.accept({version:item.version,checkId:999}),/thay đổi/);
 const consent=()=>({version:item.version,checkId:updater.state.checkId});updater.accept(consent());assert.equal(updater.snapshot().phase,'deferred');assert.equal(downloadCalls,0);busy=false;
 badHash=true;updater.resume();await updater.task;assert.equal(updater.state.phase,'error');assert.match(updater.state.error,/SHA256/);assert.deepEqual(await readdir(updater.directory),[]);badHash=false;
 async function retry(){updater.check(true);await updater.task;updater.accept(consent());await updater.task;}
 truncated=true;await retry();assert.equal(updater.state.phase,'error');truncated=false;httpRedirect=true;await retry();assert.match(updater.state.error,/HTTPS/);httpRedirect=false;
 await retry();assert.equal(updater.snapshot().phase,'ready');busy=true;await assert.rejects(updater.prepareInstall(),/Chờ/);busy=false;
 await writeFile(updater.installer,Buffer.alloc(bytes.length));await assert.rejects(updater.prepareInstall(),/thay đổi/);await retry();const installation=await updater.prepareInstall();assert.equal(installation.version,'1.11.0');assert.equal((await readFile(installation.path)).toString(),bytes.toString());updater.close();
 const current=new DesktopUpdater({dataDirectory:path.join(dir,'current'),version:'2.0.0',feed:'https://github.com/latest.json',key,fetcher});await current.run();assert.equal(current.snapshot().phase,'current');current.close();
});
test('Java/Node resolve codes across multiple hosts, reject ambiguity, wrong and revoked shares',async()=>{
 const http=await import('node:http');const servers=[];let revoked=false;const code='ABCDEFGH',id=randomUUID();
 async function host(device){const server=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');if(req.url==='/api/config')res.end(JSON.stringify({name:'FlowDrop',deviceId:device,deviceName:device}));else if(req.url==='/api/transfers/'+code&&!revoked)res.end(JSON.stringify({code,files:[{id,name:'mã thử.txt',size:0}]}));else{res.statusCode=404;res.end('{}');}});await new Promise(r=>server.listen(0,'127.0.0.1',r));servers.push(server);return {id:device,url:'http://127.0.0.1:'+server.address().port};}
 try{const a=await host('a'),b=await host('b'),local=async()=>new Response('{}',{status:404});
 const result=await findCode('abcd efgh',{getPeers:()=>[a],getLocal:local});assert.equal(result.origin,a.url);
 assert.equal((await java('code','ABCD-EFGH','',a.url)).origin,a.url+'/');
 await assert.rejects(findCode(code,{getPeers:()=>[a,b],getLocal:local}),/nhiều/);await assert.rejects(java('code',code,'',a.url,b.url));
 assert.equal((await findCode(code,{getPeers:()=>[a,b],getLocal:local,preferredId:'b'})).origin,b.url);assert.equal((await java('code',code,b.url,a.url,b.url)).origin,b.url+'/');
 revoked=true;await assert.rejects(findCode(code,{getPeers:()=>[a],getLocal:local}),/Chưa tìm/);await assert.rejects(java('code',code,'',a.url));
 }finally{for(const server of servers){server.closeAllConnections();await new Promise(r=>server.close(r));}}
});
