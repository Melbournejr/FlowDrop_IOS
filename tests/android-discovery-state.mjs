import {spawnSync} from 'node:child_process';
import {mkdir,readdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const tools='/workspace/flowdrop-build',jar=tools+'/downloads/json-test.jar',compiled=tools+'/nsd-tests';await mkdir(compiled,{recursive:true});
async function sources(dir){let result=[];for(const f of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,f.name);if(f.isDirectory())result.push(...await sources(p));else if(f.name.endsWith('.java'))result.push(p);}return result;}
const files=[...await sources('tests/nsd-stubs'),'android/src/app/flowdrop/mobile/DeviceDiscovery.java','android/src/app/flowdrop/mobile/WifiNetwork.java','android/src/app/flowdrop/mobile/LanDiscovery.java','tests/NsdDiscoveryHarness.java'];
const built=spawnSync('java',['-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',jar,'-d',compiled,...files],{encoding:'utf8'});assert.equal(built.status,0,built.stderr);
const test=spawnSync('java',['-cp',compiled+path.delimiter+jar,'app.flowdrop.mobile.NsdDiscoveryHarness'],{encoding:'utf8',timeout:20000});assert.equal(test.status,0,test.stdout+test.stderr);console.log(test.stdout.trim());await writeFile(tools+'/android-discovery-state-verification-1.9.txt',test.stdout);
