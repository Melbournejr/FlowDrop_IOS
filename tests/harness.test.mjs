import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter,once} from 'node:events';
import {mkdtemp,readFile,readdir,rm,writeFile} from 'node:fs/promises';
import http from 'node:http';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {PassThrough} from 'node:stream';
import {createHarness,javaCompileArguments,jsonJarPath,localFetch,redactCapabilities,root,stopChild,waitForHost} from './helpers/harness.mjs';

function fakeChild(){
  return Object.assign(new EventEmitter(),{stdout:new PassThrough(),stderr:new PassThrough(),exitCode:null,signalCode:null});
}

function listenLocal(server){
  return new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',()=>{server.off('error',reject);resolve();});});
}

test('REG-001: Java source paths remain individual arguments, including roots with spaces',()=>{
  const sources=['android/src/app/flowdrop/mobile/RequestSecurity.java','android/src/app/flowdrop/mobile/TransferServer.java','android/src/app/flowdrop/mobile/CodeLookup.java','tests/HostHarness.java'];
  const args=javaCompileArguments(sources,path.join(tmpdir(),'classes with spaces'),path.join(tmpdir(),'json with spaces.jar'));
  assert.deepEqual(args.slice(-sources.length),sources.map(source=>path.join(root,source)));
  assert.equal(args[args.indexOf('-d')+1],path.join(tmpdir(),'classes with spaces'));
  assert.throws(()=>javaCompileArguments([path.join(sources[0],sources[1])],'classes','json.jar'),/each Java source/);
});

test('compiler arguments reject outside-repository and non-Java inputs',()=>{
  for(const source of ['../outside.java','package.json'])assert.throws(()=>javaCompileArguments([source],'classes','json.jar'));
  assert.throws(()=>javaCompileArguments([],'classes','json.jar'));
});

test('test JAR configuration supports an explicit path and the existing build-tools override',()=>{
  const explicit=path.join(tmpdir(),'tools with spaces','json.jar');
  assert.equal(jsonJarPath({FLOWDROP_TEST_JSON_JAR:explicit}),explicit);
  const tools=path.join(tmpdir(),'legacy-tools');
  assert.equal(jsonJarPath({FLOWDROP_BUILD_TOOLS:tools}),path.join(tools,'downloads','json-test.jar'));
  assert.equal(jsonJarPath({}),path.join(tmpdir(),'flowdrop-test-tools','downloads','json-test.jar'));
});

test('concurrent workspaces are distinct and cleanup is idempotent',async()=>{
  const parent=await mkdtemp(path.join(tmpdir(),'flowdrop-harness-parent-'));
  const env={FLOWDROP_TEST_TMPDIR:parent};let a,b;
  try{
    [a,b]=await Promise.all([createHarness('isolation',{env}),createHarness('isolation',{env})]);
    assert.notEqual(a.directory,b.directory);
    await writeFile(path.join(a.directory,'scratch'),'a');await writeFile(path.join(b.directory,'scratch'),'b');
    await Promise.all([a.cleanup(),a.cleanup()]);assert.equal(await readFile(path.join(b.directory,'scratch'),'utf8'),'b');
    await b.cleanup();assert.deepEqual(await readdir(parent),[]);
  }finally{await a?.cleanup();await b?.cleanup();await rm(parent,{recursive:true,force:true});}
});

test('a missing JAR produces an actionable preflight failure and no scratch leak',async()=>{
  const parent=await mkdtemp(path.join(tmpdir(),'flowdrop-harness-preflight-'));
  const harness=await createHarness('missing-jar',{env:{FLOWDROP_TEST_TMPDIR:parent,FLOWDROP_TEST_JSON_JAR:path.join(parent,'missing.jar')}});
  try{
    try{await assert.rejects(harness.compileJava(['tests/HostHarness.java']),/FLOWDROP_TEST_JSON_JAR/);}finally{await harness.cleanup();}
    assert.deepEqual(await readdir(parent),[]);
  }finally{await harness.cleanup();await rm(parent,{recursive:true,force:true});}
});

test('a mismatched JAR is rejected before compilation instead of silently changing the fixture dependency',async()=>{
  const parent=await mkdtemp(path.join(tmpdir(),'flowdrop-harness-jar-')),jar=path.join(parent,'fixture.jar');
  await writeFile(jar,'not the audited JAR');
  const harness=await createHarness('wrong-jar',{env:{FLOWDROP_TEST_TMPDIR:parent,FLOWDROP_TEST_JSON_JAR:jar}});
  try{await assert.rejects(harness.compileJava(['tests/HostHarness.java']),/SHA-256/);}finally{await harness.cleanup();await rm(parent,{recursive:true,force:true});}
});

test('desktop readiness waits for the private pipe record and handles fragmented UTF-8',async()=>{
  const child=fakeChild(),ready=waitForHost(child,'desktop');
  child.stdout.write('FlowDrop: http://127.0.0.1:12345\n');
  const record=Buffer.from('FLOWDROP_READY '+JSON.stringify({port:54321,token:'desktop-fixture',label:'Điện thoại 📱'})+'\n');
  for(let i=0;i<record.length;i+=3)child.stdout.write(record.subarray(i,i+3));
  assert.deepEqual(await ready,{origin:'http://127.0.0.1:54321',header:'X-Desktop-Token',token:'desktop-fixture'});
  assert.equal(child.stdout.listenerCount('data'),0);assert.equal(child.listenerCount('exit'),0);
});

test('Android readiness parses a fragmented local capability from the JVM pipe',async()=>{
  const child=fakeChild(),ready=waitForHost(child,'android');
  const record=JSON.stringify({url:'http://127.0.0.1:54322/',localToken:'android-fixture'})+'\n';
  child.stdout.write(record.slice(0,17));child.stdout.write(record.slice(17));
  assert.deepEqual(await ready,{origin:'http://127.0.0.1:54322',header:'X-Local-Token',token:'android-fixture'});
});

test('readiness rejects missing capabilities and non-loopback addresses',async()=>{
  for(const record of [{url:'http://127.0.0.1:54322/'},{url:'http://example.test:54322/',localToken:'fixture'}]){
    const child=fakeChild(),ready=waitForHost(child,'android');child.stdout.write(JSON.stringify(record)+'\n');
    await assert.rejects(ready,/loopback address or local capability/);
  }
});

test('startup failure and timeout detach listeners and redact capability diagnostics',async()=>{
  const child=fakeChild(),ready=waitForHost(child,'desktop'),secret='startup-fixture-must-not-appear';
  child.stderr.write(JSON.stringify({token:secret}));child.emit('exit',2,null);
  await assert.rejects(ready,error=>error.message.includes('[REDACTED]')&&!error.message.includes(secret));
  const silent=fakeChild();await assert.rejects(waitForHost(silent,'desktop',{timeoutMs:10}),/timeout/);
  assert.equal(silent.stdout.listenerCount('data'),0);assert.equal(silent.listenerCount('error'),0);
});

test('a host that exited before the readiness listener was attached fails immediately',async()=>{
  const child=fakeChild();child.exitCode=2;
  await assert.rejects(waitForHost(child,'desktop'),/exited before readiness/);
});

test('a missing executable is reported and cleaned up without waiting for an exit event',async()=>{
  const harness=await createHarness('missing-process');
  try{
    const child=harness.spawn(path.join(harness.directory,'no-such-executable'),[],{stdio:['ignore','pipe','pipe']});
    await assert.rejects(waitForHost(child,'desktop'),/could not start/);
  }finally{await harness.cleanup();}
});

test('cleanup terminates a child that ignores graceful shutdown and removes its files',async()=>{
  const harness=await createHarness('stubborn-child');
  try{
    const child=harness.spawn(process.execPath,['-e',"process.on('SIGTERM',()=>{});console.log('ready');setInterval(()=>{},1000)"],{stdio:['ignore','pipe','pipe']});
    await once(child.stdout,'data');await writeFile(path.join(harness.directory,'scratch'),'test data');
    await stopChild(child,{graceMs:30,killMs:1000});
    assert.ok(child.exitCode!==null||child.signalCode!==null);
    await harness.cleanup();await assert.rejects(readFile(path.join(harness.directory,'scratch')),/ENOENT/);
  }finally{await harness.cleanup();}
});

test('local requests use the correct per-host header; missing and wrong credentials remain denied',async()=>{
  const calls=[],server=http.createServer((req,res)=>{
    const expected=req.url==='/android'?'android-fixture':'desktop-fixture',header=req.url==='/android'?'x-local-token':'x-desktop-token';
    calls.push({route:req.url,headers:req.headers});res.writeHead(req.headers[header]===expected?200:403);res.end();
  });
  await listenLocal(server);
  const origin='http://127.0.0.1:'+server.address().port;
  try{
    for(const [route,header,token] of [['/desktop','X-Desktop-Token','desktop-fixture'],['/android','X-Local-Token','android-fixture']]){
      for(const headers of [{},{[header]:'wrong'}]){const denied=await fetch(origin+route,{headers});assert.equal(denied.status,403);await denied.arrayBuffer();}
      const allowed=await localFetch({origin,header,token},route);assert.equal(allowed.status,200);await allowed.arrayBuffer();
      assert.equal(calls.at(-1).headers[header.toLowerCase()],token);
    }
    const count=calls.length;
    for(const route of ['http://example.test/','//example.test/'])assert.throws(()=>localFetch({origin,header:'X-Desktop-Token',token:'desktop-fixture'},route),/path on this local host/);
    assert.equal(calls.length,count);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('local capabilities are not forwarded when a local endpoint redirects to another origin',async()=>{
  let forwarded=0;
  const target=http.createServer((req,res)=>{forwarded++;res.end();});await listenLocal(target);
  const server=http.createServer((req,res)=>{res.writeHead(302,{Location:'http://127.0.0.1:'+target.address().port+'/'});res.end();});
  try{
    await listenLocal(server);
    const host={origin:'http://127.0.0.1:'+server.address().port,header:'X-Desktop-Token',token:'redirect-fixture'};
    await assert.rejects(localFetch(host,'/redirect'));
    assert.equal(forwarded,0,'A redirected request must not carry a local capability to a different server');
  }finally{
    for(const item of [server,target]){item.closeAllConnections();await new Promise(resolve=>item.close(resolve));}
  }
});

test('optional report output stays outside scratch cleanup and redacts capability fields',async()=>{
  const parent=await mkdtemp(path.join(tmpdir(),'flowdrop-harness-report-')),reports=path.join(parent,'reports');
  const harness=await createHarness('report',{env:{FLOWDROP_TEST_TMPDIR:parent,FLOWDROP_TEST_REPORT_DIR:reports}});
  try{
    await harness.writeReport('report.json',{token:'report-fixture',passed:true});
    await assert.rejects(harness.writeReport('../escape.json',{}));
    await harness.cleanup();assert.deepEqual(JSON.parse(await readFile(path.join(reports,'report.json'),'utf8')),{token:'[REDACTED]',passed:true});
    assert.equal(redactCapabilities('"localToken":"fixture"'),'"localToken":"[REDACTED]"');
  }finally{await harness.cleanup();await rm(parent,{recursive:true,force:true});}
});
