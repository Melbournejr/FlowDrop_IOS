import {spawnSync} from 'node:child_process';
import {readdir} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHarness,javaCommand,root} from './helpers/harness.mjs';
async function sources(dir){let result=[];for(const f of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,f.name);if(f.isDirectory())result.push(...await sources(p));else if(f.name.endsWith('.java'))result.push(p);}return result;}
const harness=await createHarness('android-discovery');
try{
 const files=[...await sources(path.join(root,'tests/nsd-stubs')),'android/src/app/flowdrop/mobile/DeviceDiscovery.java','android/src/app/flowdrop/mobile/WifiNetwork.java','android/src/app/flowdrop/mobile/LanDiscovery.java','tests/NsdDiscoveryHarness.java'];
 const {classpath}=await harness.compileJava(files);
 const test=spawnSync(javaCommand,['-cp',classpath,'app.flowdrop.mobile.NsdDiscoveryHarness'],{encoding:'utf8',timeout:20000});assert.equal(test.status,0,test.stdout+test.stderr);console.log(test.stdout.trim());await harness.writeReport('android-discovery-state-verification-1.9.txt',test.stdout);
}finally{await harness.cleanup();}
