import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {DeviceName,validateDeviceName} from '../scripts/device-name.mjs';
test('device labels persist Unicode names, validate codepoints and serialize writes',async()=>{
 const dir=await mkdtemp(path.join(tmpdir(),'flowdrop-name-'));
 try{const identity=new DeviceName(dir,'My PC');assert.equal(await identity.load(),'My PC');assert.equal(validateDeviceName('  Điện thoại 📱  '),'Điện thoại 📱');assert.equal([...validateDeviceName('📱'.repeat(50))].length,50);
 for(const value of [null,42,'','   ','📱'.repeat(51),'a\nb','a\x00b','a\u2028b'])assert.throws(()=>validateDeviceName(value));
 await Promise.all([identity.save('Tên đầu'),identity.save('Tên cuối 📱')]);assert.equal(await new DeviceName(dir,'Fallback').load(),'Tên cuối 📱');
 }finally{await rm(dir,{recursive:true,force:true});}
});
