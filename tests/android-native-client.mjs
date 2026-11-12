import {readdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHarness,javaCommand,waitForHost} from './helpers/harness.mjs';
const source=['android/src/app/flowdrop/mobile/TransferClient.java','android/src/app/flowdrop/mobile/CodeLookup.java','android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','tests/NativeClientHarness.java','tests/NativeHostHarness.java'];
const harness=await createHarness('native-client'),folder=harness.directory,desktopData=path.join(folder,'desktop'),androidData=path.join(folder,'android');
const report=[];
try{
 const {classpath}=await harness.compileJava(source);
 // This existing Java-client fixture uses the Node web host; the native Windows
 // capability boundary is exercised separately by large-transfer and security.
 const desktop=harness.spawn(process.execPath,['scripts/dev.mjs'],{env:{...process.env,PORT:'0',FLOWDROP_DATA_DIR:desktopData,FLOWDROP_DISABLE_UPDATES:'1'},stdio:['ignore','pipe','pipe']});
 const android=harness.spawn(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.NativeHostHarness',androidData],{stdio:['ignore','pipe','pipe']});
 const [winHost,phoneHost]=await Promise.all([waitForHost(desktop,'node-web'),waitForHost(android,'android')]);
 const win=winHost.origin+'/',phone=phoneHost.origin+'/',phoneToken=phoneHost.token;
 assert.equal((await fetch(phone)).headers.get('content-type'),'text/plain; charset=utf-8');assert.equal((await fetch(phone+'app.js')).status,404);assert.equal((await(await fetch(phone+'api/config')).json()).version,'1.13.0');
 for(const [name,base,bytes] of [['Windows 1.5 host',win,384*1024*1024+17],['Android 1.6 host',phone,4*1024*1024*1024+131089]]){
  console.log('Testing native Java client → '+name+'; large file '+bytes+' bytes.');
  const result=await new Promise((resolve,reject)=>{const client=harness.spawn(javaCommand,['-Xmx96m','-cp',classpath,'app.flowdrop.mobile.NativeClientHarness',base,String(bytes)],{env:{...process.env,FLOWDROP_TEST_LOCAL_CAPABILITY:base===phone?phoneToken:''},stdio:['ignore','pipe','pipe']});let out='',err='';const timer=setTimeout(()=>{client.kill();reject(new Error('Native client timeout '+err));},600000);client.stdout.on('data',b=>out+=b);client.stderr.on('data',b=>err+=b);client.once('error',error=>{clearTimeout(timer);reject(error);});client.on('exit',code=>{clearTimeout(timer);code===0?resolve(JSON.parse(out.trim().split('\n').at(-1))):reject(new Error(err+out));});});
  report.push({host:name,...result});console.log(JSON.stringify(report.at(-1)));
 }
 for(const name of await readdir(desktopData))assert.ok(!name.startsWith('.upload-')&&!Buffer.from(name,'hex').toString().startsWith('transfers/'),'Desktop leaked cancelled/revoked data');
 assert.deepEqual((await readdir(androidData)).filter(n=>n!=='device-id'),[],'Android leaked cancelled/revoked data');
 await harness.writeReport('android-native-client-verification.json',report);
}finally{await harness.cleanup();}
