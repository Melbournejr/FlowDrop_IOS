import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import path from 'node:path';
import {createSecureContext} from 'node:tls';
import {deviceVault,DeviceSecurity} from '../scripts/device-security.mjs';
assert.equal(process.platform,'win32','This probe is Windows DPAPI only');
const directory=path.resolve(process.argv[2]);await mkdir(directory,{recursive:false});
try{
 const first=await deviceVault(directory,'synthetic-vault-device'),secret=randomBytes(32).toString('hex'),name='Thiết bị Tiếng Việt 中文 😀';
 createSecureContext(new DeviceSecurity({id:'synthetic-vault-device',name:'Synthetic',vault:first}).tlsOptions());
 first.value.trusted.synthetic={name,secret};await first.save();
 const sealed=await readFile(path.join(directory,'device-transport.dpapi'),'utf8');assert.ok(!sealed.includes(name)&&!sealed.includes(secret)&&!sealed.includes(first.value.passphrase));
 const second=await deviceVault(directory,'synthetic-vault-device');assert.equal(second.value.certificate,first.value.certificate);assert.ok(second.value.trusted.synthetic.name===name,'Unicode trust name must survive DPAPI');assert.ok(second.value.trusted.synthetic.secret===secret,'Trust secret must survive DPAPI');
 await writeFile(path.join(directory,'device-transport.dpapi'),'invalid corrupted fixture');await assert.rejects(deviceVault(directory,'synthetic-vault-device'),/kho danh tính/);
 console.log(JSON.stringify({status:'PASS',scope:'Actual Windows CurrentUser DPAPI',identityPersistent:true,unicodePreserved:true,secretNotPlaintext:true,corruptionFailsClosed:true}));
}finally{await rm(directory,{recursive:true,force:true});}
