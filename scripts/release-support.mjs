import {createHash,createPrivateKey,createPublicKey,sign} from 'node:crypto';
import {inflateRawSync} from 'node:zlib';
import {UPDATE_PUBLIC_KEY} from './release-config.mjs';
export const PRODUCTION_CERT='65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f';
export const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export function apkMembers(data){
 if(data.length>1024*1024*1024||data.length<22)throw Error('Invalid APK size');
 let end=-1;for(let i=data.length-22;i>=Math.max(0,data.length-65557);i--)if(data.readUInt32LE(i)===0x06054b50&&i+22+data.readUInt16LE(i+20)===data.length){end=i;break;}
 if(end<0||data.readUInt16LE(end+4)||data.readUInt16LE(end+6))throw Error('Invalid APK ZIP');
 const count=data.readUInt16LE(end+10),size=data.readUInt32LE(end+12),start=data.readUInt32LE(end+16);if(!count||count>512||start+size!==end||data.readUInt16LE(end+8)!==count)throw Error('Invalid APK directory');
 let pos=start,total=0;const rows=[];const names=new Set();
 for(let i=0;i<count;i++){
  if(pos+46>end||data.readUInt32LE(pos)!==0x02014b50)throw Error('Invalid APK entry');
  const flags=data.readUInt16LE(pos+8),method=data.readUInt16LE(pos+10),compressed=data.readUInt32LE(pos+20),length=data.readUInt32LE(pos+24),n=data.readUInt16LE(pos+28),extra=data.readUInt16LE(pos+30),comment=data.readUInt16LE(pos+32),offset=data.readUInt32LE(pos+42);
  if(pos+46+n+extra+comment>end)throw Error('Invalid APK name');const name=data.subarray(pos+46,pos+46+n).toString('utf8');
  if(!name||name.startsWith('/')||name.includes('\\')||name.includes(':')||name.includes('\0')||name.split('/').includes('..')||names.has(name)||flags&1||![0,8].includes(method)||length>64*1024*1024)throw Error('Unsafe APK entry');names.add(name);total+=length;if(total>128*1024*1024)throw Error('APK expansion too large');
  if(offset+30>start||data.readUInt32LE(offset)!==0x04034b50)throw Error('Invalid APK offset');const body=offset+30+data.readUInt16LE(offset+26)+data.readUInt16LE(offset+28);if(body+compressed>start)throw Error('APK body escapes directory');
  const raw=data.subarray(body,body+compressed),bytes=method===8?inflateRawSync(raw,{maxOutputLength:Math.max(1,length)}):raw;if(bytes.length!==length)throw Error('APK length mismatch');
  rows.push({path:name,size:length,sha256:sha(bytes)});pos+=46+n+extra+comment;
 }
 if(pos!==end)throw Error('Invalid APK directory length');return rows;
}
export function checkApkContents(bytes,proof){
 if(proof.package!=='app.flowdrop.mobile'||proof.version!=='1.14.0'||proof.versionCode!==15||proof.minSdk!==29||proof.targetSdk!==35||!Array.isArray(proof.entries))throw Error('Not a production 1.14.0 APK proof');
 const actual=apkMembers(bytes).filter(x=>!/^META-INF\/(?:[A-Za-z0-9_-]+\.(?:SF|RSA|DSA|EC)|MANIFEST\.MF)$/.test(x.path));
 if(actual.length!==proof.entries.length)throw Error('Signed APK payload changed');const expected=new Map(proof.entries.map(x=>[x.path,x]));
 if(expected.size!==proof.entries.length||!expected.has('AndroidManifest.xml')||!expected.has('classes.dex'))throw Error('Incomplete APK proof');
 for(const row of actual){const old=expected.get(row.path);if(!old||old.size!==row.size||old.sha256!==row.sha256)throw Error('Signed APK payload changed');}return actual;
}
export function checkProductionSigner(output){
 const values=[...output.matchAll(/Signer #\d+ certificate SHA-256 digest: ([a-f0-9]{64})/gi)].map(m=>m[1].toLowerCase());
 if(!/^Verifies\s*$/m.test(output)||values.length!==1||values[0]!==PRODUCTION_CERT)throw Error('APK must use the original 1.13.0 certificate');return values[0];
}
// Test fixtures may supply their own expected public key; the release CLI never does.
export function signedEnvelope(payload,keyBytes,passphrase,expectedPublicKey=UPDATE_PUBLIC_KEY){
 const key=createPrivateKey({key:keyBytes,passphrase:passphrase||undefined});
 if(key.asymmetricKeyType!=='rsa'||!createPublicKey(key).export({type:'spki',format:'der'}).equals(createPublicKey(expectedPublicKey).export({type:'spki',format:'der'})))throw Error('Use the original pinned RSA update key');
 return {payload,signature:sign('RSA-SHA256',Buffer.from(payload,'utf8'),key).toString('base64')};
}
