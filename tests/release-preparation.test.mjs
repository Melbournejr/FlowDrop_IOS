import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync,verify} from 'node:crypto';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {apkMembers,checkApkContents,checkProductionSigner,signedEnvelope,sha,PRODUCTION_CERT} from '../scripts/release-support.mjs';
test('encrypted synthetic RSA signs exact payload and rejects a different key/password',()=>{
 const key=generateKeyPairSync('rsa',{modulusLength:2048});const other=generateKeyPairSync('rsa',{modulusLength:2048});
 const pem=key.privateKey.export({type:'pkcs8',format:'pem',cipher:'aes-256-cbc',passphrase:'synthetic-only-password'}),pub=key.publicKey.export({type:'spki',format:'pem'}),payload='{"raw":"bytes / Unicode Việt"}';
 const envelope=signedEnvelope(payload,pem,'synthetic-only-password',pub);assert.equal(envelope.payload,payload);assert.equal(verify('RSA-SHA256',Buffer.from(payload),pub,Buffer.from(envelope.signature,'base64')),true);
 assert.equal(verify('RSA-SHA256',Buffer.from(payload+' '),pub,Buffer.from(envelope.signature,'base64')),false);
 assert.throws(()=>signedEnvelope(payload,pem,'wrong',pub));assert.throws(()=>signedEnvelope(payload,pem,'synthetic-only-password',other.publicKey.export({type:'spki',format:'pem'})));assert.throws(()=>signedEnvelope(payload,pem,'synthetic-only-password'),'CLI default remains original production pin');
});
test('signer parser requires verified result and exactly the original public fingerprint',()=>{
 assert.equal(checkProductionSigner('Verifies\nSigner #1 certificate SHA-256 digest: '+PRODUCTION_CERT+'\n'),PRODUCTION_CERT);
 for(const value of ['DOES NOT VERIFY\nSigner #1 certificate SHA-256 digest: '+PRODUCTION_CERT,'Verifies\nSigner #1 certificate SHA-256 digest: '+'a'.repeat(64),'Verifies\nSigner #1 certificate SHA-256 digest: '+PRODUCTION_CERT+'\nSigner #2 certificate SHA-256 digest: '+PRODUCTION_CERT])assert.throws(()=>checkProductionSigner(value));
});
test('synthetic ZIP attestation rejects changed payload, traversal and duplicates',async()=>{
 const dir=await mkdtemp(path.join(tmpdir(),'flowdrop-release-unit-'));try{
  const file=path.join(dir,'fixture.zip');const result=spawnSync('python3',['-c','import sys,zipfile\nwith zipfile.ZipFile(sys.argv[1],"w",zipfile.ZIP_DEFLATED) as z:\n z.writestr("AndroidManifest.xml",b"synthetic manifest")\n z.writestr("classes.dex",b"synthetic dex")',file],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);
  const bytes=await readFile(file),entries=apkMembers(bytes),proof={package:'app.flowdrop.mobile',version:'1.14.0',versionCode:15,minSdk:29,targetSdk:35,entries};assert.equal(checkApkContents(bytes,proof).length,2);
  assert.throws(()=>checkApkContents(bytes,{...proof,package:'app.flowdrop.preview'}));assert.throws(()=>checkApkContents(bytes,{...proof,entries:entries.map(x=>({...x,sha256:'a'.repeat(64)}))}));
  const corrupt=Buffer.from(bytes);corrupt[0]=0;assert.throws(()=>apkMembers(corrupt));assert.throws(()=>apkMembers(Buffer.alloc(20)));
  for(const mode of ['traversal','duplicate']){const p=spawnSync('python3',['-c','import sys,zipfile,warnings\nwarnings.simplefilter("ignore")\nwith zipfile.ZipFile(sys.argv[1],"w") as z:\n z.writestr("../outside" if sys.argv[2]=="traversal" else "same",b"x")\n if sys.argv[2]=="duplicate": z.writestr("same",b"y")',file,mode],{encoding:'utf8'});assert.equal(p.status,0);const bad=await readFile(file);assert.throws(()=>apkMembers(bad));}
 }finally{await rm(dir,{recursive:true,force:true});}
});
