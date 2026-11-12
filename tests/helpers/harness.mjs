import assert from 'node:assert/strict';
import {spawn,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir,mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {StringDecoder} from 'node:string_decoder';
import {fileURLToPath} from 'node:url';

export const root=fileURLToPath(new URL('../../',import.meta.url));
export const javaCommand=process.env.FLOWDROP_TEST_JAVA||'java';
export const pythonCommand=process.env.FLOWDROP_TEST_PYTHON||'python3';
export const JSON_JAR_SHA256='3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed';

export function jsonJarPath(env=process.env){
  return path.resolve(env.FLOWDROP_TEST_JSON_JAR||path.join(env.FLOWDROP_BUILD_TOOLS||path.join(tmpdir(),'flowdrop-test-tools'),'downloads','json-test.jar'));
}

export function javaCompileArguments(sources,classes,jar){
  assert.ok(Array.isArray(sources)&&sources.length>0,'Provide individual Java source paths');
  const files=sources.map(source=>{
    const file=path.resolve(root,source);
    assert.ok(file.startsWith(root)&&file.endsWith('.java'),'Java sources must be inside the repository');
    assert.ok(!path.relative(root,file).split(path.sep).slice(0,-1).some(part=>part.endsWith('.java')),'Pass each Java source as its own argument');
    return file;
  });
  return ['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-classpath',jar,'-d',classes,...files];
}

export function redactCapabilities(text){
  return String(text).replace(/(["'](?:token|localToken|desktopToken|statusToken)["']\s*:\s*["'])[^"'\r\n]+/gi,'$1[REDACTED]').replace(/\b(?:[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}){1,2}\b/gi,'[REDACTED_UUID]');
}

export async function stopChild(child,{graceMs=1500,killMs=1500}={}){
  if(!child.pid||child.exitCode!==null||child.signalCode!==null)return;
  await new Promise((resolve,reject)=>{
    let hardTimer;
    const done=error=>{
      clearTimeout(softTimer);clearTimeout(hardTimer);
      child.off('exit',exited);child.off('error',failed);
      error?reject(error):resolve();
    };
    const exited=()=>done(),failed=()=>done();
    child.once('exit',exited);child.once('error',failed);
    const softTimer=setTimeout(()=>{
      child.kill('SIGKILL');
      hardTimer=setTimeout(()=>done(new Error('Test child did not exit after SIGKILL')),killMs);
    },graceMs);
    child.kill('SIGTERM');
    if(child.exitCode!==null||child.signalCode!==null)done();
  });
}

export async function createHarness(label,{env=process.env}={}){
  assert.match(label,/^[a-z0-9-]+$/);
  const parent=path.resolve(env.FLOWDROP_TEST_TMPDIR||tmpdir());
  await mkdir(parent,{recursive:true});
  const directory=await mkdtemp(path.join(parent,'flowdrop-'+label+'-'));
  const children=new Set();let cleanupTask;
  return {
    directory,
    spawn(command,args,options={}){
      const child=spawn(command,args,{cwd:root,...options});
      // Keep a missing executable from becoming an unhandled event before readiness is awaited.
      child.on('error',()=>{});children.add(child);return child;
    },
    async compileJava(sources){
      const jar=jsonJarPath(env);
      let bytes;
      try{bytes=await readFile(jar);}catch{throw new Error('Missing test org.json JAR. Set FLOWDROP_TEST_JSON_JAR to org.json:json:20240303; see docs/testing/REGRESSION-HARNESS.md');}
      assert.equal(createHash('sha256').update(bytes).digest('hex'),JSON_JAR_SHA256,'Test org.json JAR SHA-256 differs from the audited baseline');
      const compiled=path.join(directory,'classes');await mkdir(compiled,{recursive:true});
      const result=spawnSync(javaCommand,javaCompileArguments(sources,compiled,jar),{cwd:root,encoding:'utf8',timeout:60000,maxBuffer:1024*1024});
      if(result.error)throw new Error('Java test compilation could not run: '+result.error.code);
      assert.equal(result.status,0,redactCapabilities(result.stderr));
      return {compiled,jar,classpath:compiled+path.delimiter+jar};
    },
    async writeReport(name,value){
      assert.equal(path.basename(name),name,'Test report must be a filename');
      const destination=env.FLOWDROP_TEST_REPORT_DIR?path.resolve(env.FLOWDROP_TEST_REPORT_DIR):directory;
      await mkdir(destination,{recursive:true});
      await writeFile(path.join(destination,name),redactCapabilities(typeof value==='string'?value:JSON.stringify(value,null,2)));
    },
    cleanup(){
      return cleanupTask??=(async()=>{
        const stopped=await Promise.allSettled([...children].map(child=>stopChild(child)));
        const errors=stopped.filter(r=>r.status==='rejected').map(r=>r.reason);
        if(errors.length)throw new AggregateError(errors,'Test child cleanup failed; scratch data retained');
        await rm(directory,{recursive:true,force:true});
      })();
    },
  };
}

export function waitForHost(child,kind,{timeoutMs=15000}={}){
  assert.ok(['desktop','android','node-web'].includes(kind),'Unknown host readiness format');
  return new Promise((resolve,reject)=>{
    let pending='',errors='';const decoder=new StringDecoder('utf8');
    const finish=(error,value)=>{
      clearTimeout(timer);child.stdout.off('data',output);child.stderr.off('data',stderr);
      child.off('exit',exited);child.off('error',failed);
      error?reject(error):resolve(value);
    };
    const failed=error=>finish(new Error('Test host could not start: '+error.code));
    const exited=(code,signal)=>finish(new Error('Test host exited before readiness ('+(signal||code)+'): '+redactCapabilities(errors)));
    const stderr=chunk=>{errors=(errors+chunk.toString()).slice(-8192);};
    const output=chunk=>{
      pending+=typeof chunk==='string'?chunk:decoder.write(chunk);
      let end;
      while((end=pending.indexOf('\n'))>=0){
        const line=pending.slice(0,end).replace(/\r$/,'');pending=pending.slice(end+1);
        if(kind==='node-web'){
          const match=line.match(/^FlowDrop: (http:\/\/127\.0\.0\.1:\d+)$/);
          if(match){finish(null,{origin:new URL(match[1]).origin,header:null,token:null});return;}
          continue;
        }
        if(kind==='desktop'&&!line.startsWith('FLOWDROP_READY '))continue;
        if(kind==='android'&&!line.startsWith('{'))continue;
        let ready;
        try{ready=JSON.parse(kind==='desktop'?line.slice('FLOWDROP_READY '.length):line);}catch{finish(new Error('Malformed test host readiness JSON'));return;}
        try{
          const token=kind==='desktop'?ready.token:ready.localToken;
          const url=new URL(kind==='desktop'?'http://127.0.0.1:'+ready.port:ready.url);
          assert.ok(url.protocol==='http:'&&url.hostname==='127.0.0.1'&&Number(url.port)>0&&Number(url.port)<=65535&&!url.username&&!url.password);
          assert.ok(typeof token==='string'&&token.length>0&&token.length<=1024);
          finish(null,{origin:url.origin,header:kind==='desktop'?'X-Desktop-Token':'X-Local-Token',token});return;
        }catch{finish(new Error('Invalid test host loopback address or local capability'));return;}
      }
      if(pending.length>65536)finish(new Error('Test host readiness line exceeds 64 KiB'));
    };
    const timer=setTimeout(()=>finish(new Error('Test host readiness timeout: '+redactCapabilities(errors))),timeoutMs);
    child.stdout.on('data',output);child.stderr.on('data',stderr);
    child.once('error',failed);child.once('exit',exited);
    if(child.exitCode!==null||child.signalCode!==null)exited(child.exitCode,child.signalCode);
  });
}

export function localFetch(host,route,options={}){
  assert.ok(typeof route==='string'&&route.startsWith('/')&&!route.startsWith('//'),'Use a path on this local host');
  const url=new URL(route,host.origin);
  assert.equal(url.origin,host.origin,'Never forward a local capability to another origin');
  assert.ok(url.protocol==='http:'&&url.hostname==='127.0.0.1','Use the loopback host from the private startup pipe');
  const headers=new Headers(options.headers);
  if(host.header){assert.ok(host.token,'Missing local capability');headers.set(host.header,host.token);}
  return fetch(url,{...options,headers,redirect:'error'});
}
