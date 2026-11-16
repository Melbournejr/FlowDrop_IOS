// Actual Windows bundled Node process, actual app TLS identity; no signing material.
import assert from 'node:assert/strict';
import https from 'node:https';
import {checkServerIdentity} from 'node:tls';
import {readFile} from 'node:fs/promises';
import {X509Certificate} from 'node:crypto';
import {identityName,digest} from '../scripts/device-security.mjs';
const config=JSON.parse(await readFile(process.argv[2],'utf8'));
const certificate=new X509Certificate(Buffer.from(config.secure.certificate,'base64'));
assert.equal(digest(certificate.raw),config.secure.fingerprint);
assert.ok(certificate.verify(certificate.publicKey));assert.equal(certificate.checkHost(identityName(config.deviceId)),identityName(config.deviceId));
function probe(pin){return new Promise((resolve,reject)=>{
 const request=https.get({host:'127.0.0.1',port:config.secure.port,path:'/api/transfers/ABCDEFGH',servername:identityName(config.deviceId),ca:certificate.toString(),agent:false,minVersion:'TLSv1.2',rejectUnauthorized:true,checkServerIdentity:(name,cert)=>checkServerIdentity(name,cert)||(digest(cert.raw)!==pin?Error('TLS pin mismatch'):undefined)},response=>{const version=response.socket.getProtocol();response.resume();response.on('end',()=>resolve({status:response.statusCode,tlsVersion:version}));});
 request.setTimeout(8000,()=>request.destroy(Error('TLS probe timeout')));request.once('error',reject);
});}
const result=await probe(config.secure.fingerprint);assert.equal(result.status,403);assert.ok(['TLSv1.2','TLSv1.3'].includes(result.tlsVersion));await assert.rejects(probe('0'.repeat(64)),/TLS pin mismatch/);
console.log(JSON.stringify({status:'PASS',scope:'Actual native app TLS listener, not cross-device pairing',fingerprint:config.secure.fingerprint,tlsVersion:result.tlsVersion,unauthenticatedStatus:result.status,wrongPinRejected:true}));
