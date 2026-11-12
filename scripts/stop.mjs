import {readFile,unlink} from 'node:fs/promises';
import path from 'node:path';
import {setTimeout} from 'node:timers/promises';
const folder=process.env.FLOWDROP_DATA_DIR||(process.platform==='win32'?path.join(process.env.LOCALAPPDATA,'FlowDrop','Data'):'.local-data');
const stateFile=path.join(folder,'desktop-state.json');
try{const state=JSON.parse(await readFile(stateFile,'utf8'));const response=await fetch('http://127.0.0.1:'+state.port+'/api/desktop/stop',{method:'POST',headers:{'X-Desktop-Token':state.token},signal:AbortSignal.timeout(3000)});if(response.ok){await unlink(stateFile).catch(()=>{});await setTimeout(600);}}catch{}
