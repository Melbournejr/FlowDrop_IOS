'use strict';
const $ = (s) => document.querySelector(s);
const icon = (name) => '<svg aria-hidden="true"><use href="#i-' + name + '"/></svg>';

let selected = [], activeAbort = null, activeXHR = null, currentShare = null, view = 'send', localMode = false;
const nativeSaver=/FlowDropAndroid\//.test(navigator.userAgent);
let desktopSettings=null,savedIds=new Set();
let history = [];
try { history = JSON.parse(localStorage.getItem('flowdrop-history') || '[]'); if (!Array.isArray(history)) history = []; } catch { history = []; }
const size = n => {const units=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<units.length-1){n/=1024;i++;}return (i?n.toFixed(1):n)+' '+units[i];};
let uploadStarted=0;
const date = (n) => new Intl.DateTimeFormat('vi-VN', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(n));
const cleanCode = (s) => s.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0,8);
const formatCode = (s) => s.slice(0,4) + (s.length > 4 ? ' ' + s.slice(4) : '');
const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const desktopReady=nativeSaver?Promise.resolve():fetch('/api/desktop/settings').then(r=>r.ok?r.json():null).then(data=>{if(data?.token){desktopSettings=data;refreshSaveSettings();}}).catch(()=>{});
function refreshSaveSettings(){
  if(desktopSettings){document.querySelectorAll('.desktop-save-settings-trigger').forEach(b=>b.hidden=false);$('#save-destination').hidden=false;$('#save-destination-label').textContent=(desktopSettings.autoSave?'Tự động lưu: ':'Thư mục nhận: ')+desktopSettings.directory;}
  else if(nativeSaver){$('#save-destination').hidden=false;$('#save-destination-label').textContent='Ảnh/video → Album FlowDrop · File khác → Download/FlowDrop. Cài đặt ở nút Lưu file phía trên.';}
}
refreshSaveSettings();
function toast(message) { $('#toast span').textContent = message; $('#toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').hidden = true, 3600); }
function error(id, message = '') { const el = $(id); el.hidden = !message; el.textContent = message; }
async function desktopAction(route,body={}){return api('/api/desktop/'+route,{method:'POST',headers:{'X-Desktop-Token':desktopSettings.token},body:JSON.stringify(body)});}
document.querySelectorAll('.desktop-save-settings-trigger').forEach(button=>button.addEventListener('click',()=>{if(!desktopSettings)return;$('#receive-directory').value=desktopSettings.directory;$('#auto-save-enabled').checked=desktopSettings.autoSave;error('#save-settings-error');$('#save-settings-dialog').showModal();}));
$('#close-save-settings').addEventListener('click',()=>$('#save-settings-dialog').close());
$('#save-settings-form').addEventListener('submit',async event=>{event.preventDefault();try{const data=await desktopAction('settings',{directory:$('#receive-directory').value.trim(),autoSave:$('#auto-save-enabled').checked});desktopSettings={...desktopSettings,...data};refreshSaveSettings();$('#save-settings-dialog').close();toast('Đã lưu thư mục và cài đặt nhận file.');}catch(e){error('#save-settings-error',e.message);}});
$('#choose-receive-directory').addEventListener('click',async event=>{const button=event.currentTarget;button.disabled=true;error('#save-settings-error');try{const data=await desktopAction('choose-folder');if(data.directory)$('#receive-directory').value=data.directory;}catch(e){error('#save-settings-error',e.message);}finally{button.disabled=false;}});
$('#open-receive-directory').addEventListener('click',async()=>{try{await desktopAction('open-folder');}catch(e){error('#save-settings-error',e.message);}});
function saveHistory() { try { localStorage.setItem('flowdrop-history', JSON.stringify(history.slice(0,50))); } catch { toast('Trình duyệt không cho phép lưu lịch sử trên thiết bị.'); } renderHistory(); }
function addHistory(item) { item.fileCount=item.files.length;item.total=item.files.reduce((n,f)=>n+f.size,0);item.files=item.files.slice(0,1); const i = history.findIndex(h => h.code === item.code && h.direction === item.direction); if (i >= 0) history.splice(i,1); history.unshift(item); saveHistory(); }
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, { ...options, headers: { ...(options.body && typeof options.body === 'string' ? {'Content-Type':'application/json'} : {}), ...options.headers } }); }
  catch (e) { if (e.name === 'AbortError') throw e; throw new Error('Không thể kết nối. Kiểm tra Wi-Fi và thiết bị tạo phiên rồi thử lại.'); }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error || 'Không thể thực hiện yêu cầu. Vui lòng thử lại.');
  if (!data) throw new Error('Phiên đăng nhập cần được làm mới. Hãy tải lại trang.');
  return data;
}
function setView(next, focus = false) {
  view = next;
  document.body.classList.toggle('history-mode', next === 'history');
  document.body.classList.toggle('receive-mode', next === 'receive');
  document.querySelectorAll('[data-view]').forEach(el => { el.classList.toggle('active', el.dataset.view === next); el.setAttribute('aria-pressed', String(el.dataset.view === next)); });
  $('#page-label').textContent = next === 'history' ? 'Lịch sử chuyển file' : 'Chuyển file';
  $('#history-title').firstChild.textContent = next === 'history' ? 'Lịch sử chuyển file ' : 'Gần đây ';
  renderHistory();
  if (focus && next === 'receive') { $('#receive-card').scrollIntoView({behavior:'smooth',block:'nearest'}); $('#receive-code').focus({preventScroll:true}); }
}
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => setView(b.dataset.view, b.dataset.view === 'receive')));
$('#all-history').addEventListener('click', () => setView('history'));
document.querySelectorAll('.help-button').forEach(b => b.addEventListener('click', () => $('#help-dialog').showModal()));
for (const id of ['close-help','help-done']) $('#' + id).addEventListener('click', () => $('#help-dialog').close());
$('#help-dialog').addEventListener('click', e => { if (e.target === $('#help-dialog')) { const rect=e.target.getBoundingClientRect(); if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)e.target.close(); } });
const platform = /Android/i.test(navigator.userAgent) ? 'Điện thoại Android' : /iPad|iPhone|iPod/i.test(navigator.userAgent) ? 'iPhone / iPad' : /Mac/i.test(navigator.userAgent) ? 'Máy Mac của bạn' : /Windows/i.test(navigator.userAgent) ? 'Máy tính Windows' : 'Thiết bị của bạn';
$('#device-name').textContent = platform;
function connectivity() { const online=navigator.onLine||localMode; document.body.classList.toggle('offline',!online); $('#online-text').textContent=online?'Sẵn sàng kết nối':'Đang ngoại tuyến'; $('#connection-label').textContent=localMode?'Chia sẻ trong cùng Wi-Fi':online?'Đã kết nối Internet':'Chưa có Internet'; }
addEventListener('online',connectivity); addEventListener('offline',connectivity); connectivity();
function chooseFiles(files) {
  error('#send-error'); const issues=[];
  for (const file of files) {
    if (selected.some(f=>f.name===file.name&&f.size===file.size&&f.lastModified===file.lastModified)) continue;
    selected.push(file);
  }
  renderSelected(); if(issues.length)error('#send-error',issues.join(' '));
}
function renderSelected(){
  $('#selected-area').hidden=!selected.length;
  $('#selected-files').innerHTML=selected.slice(0,100).map((f,i)=>'<div class="file-row"><span class="file-type">'+icon('file')+'</span><div class="file-detail"><strong title="'+escape(f.name)+'">'+escape(f.name)+'</strong><span>'+size(f.size)+'</span></div><button class="file-remove" data-remove="'+i+'" aria-label="Bỏ '+escape(f.name)+'">'+icon('close')+'</button></div>').join('')+(selected.length>100?'<p class="download-note">Hiển thị 100 / '+selected.length+' file. Tất cả file đã chọn đều được gửi.</p>':'');
  $('#selection-total').textContent=selected.length+' file · '+size(selected.reduce((n,f)=>n+f.size,0));
  $('#selected-files').querySelectorAll('[data-remove]').forEach(b=>b.addEventListener('click',()=>{selected.splice(Number(b.dataset.remove),1);renderSelected();}));
}
$('#file-input').addEventListener('change',e=>{chooseFiles(e.target.files);e.target.value='';});
$('#clear-files').addEventListener('click',()=>{selected=[];renderSelected();error('#send-error');});
$('#dropzone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('#file-input').click();}});
for(const event of ['dragenter','dragover'])$('#dropzone').addEventListener(event,e=>{e.preventDefault();$('#dropzone').classList.add('dragging');});
for(const event of ['dragleave','drop'])$('#dropzone').addEventListener(event,e=>{e.preventDefault();$('#dropzone').classList.remove('dragging');});
$('#dropzone').addEventListener('drop',e=>chooseFiles(e.dataTransfer.files));
addEventListener('dragover',e=>{if(e.dataTransfer?.types.includes('Files'))e.preventDefault();});
addEventListener('drop',e=>{if(e.dataTransfer?.files.length)e.preventDefault();});
function uploadFile(session,file,index,base,total,signal){
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();activeXHR=xhr;
    const abort=()=>xhr.abort();signal.addEventListener('abort',abort,{once:true});
    xhr.open('PUT','/api/transfers/'+session.code+'/files/'+session.files[index].id);
    xhr.setRequestHeader('X-Upload-Token',session.token);
    xhr.setRequestHeader('Content-Type','application/octet-stream');
    xhr.timeout=0;
    xhr.upload.onprogress=e=>{if(e.lengthComputable){const elapsed=(performance.now()-uploadStarted)/1000,rate=(base+e.loaded)/Math.max(elapsed,.1);$('#upload-speed').textContent=size(base+e.loaded)+' / '+size(total)+' · '+size(rate)+'/s';const pct=total?Math.min(99,Math.round((base+e.loaded)/total*100)):0;$('#upload-progress').style.width=pct+'%';$('#upload-percent').textContent=pct+'%';}};
    const cleanup=()=>{signal.removeEventListener('abort',abort);activeXHR=null;};
    xhr.onload=()=>{cleanup();if(xhr.status>=200&&xhr.status<300)resolve();else{let message='Tải lên thất bại. Vui lòng thử lại.';try{message=JSON.parse(xhr.responseText).error||message;}catch{}reject(new Error(message));}};
    xhr.onerror=()=>{cleanup();reject(new Error('Mất kết nối khi tải lên. Kiểm tra Wi-Fi và thử lại.'));};
    xhr.ontimeout=()=>{cleanup();reject(new Error('Tải lên quá lâu. Hãy thử lại với kết nối ổn định hơn.'));};
    xhr.onabort=()=>{cleanup();reject(new DOMException('Đã hủy','AbortError'));};
    if(signal.aborted){cleanup();reject(new DOMException('Đã hủy','AbortError'));return;}
    xhr.send(file);
  });
}
function sendState(state){$('#send-select').hidden=state!=='select';$('#upload-state').hidden=state!=='upload';$('#share-state').hidden=state!=='share';}
$('#start-upload').addEventListener('click',async()=>{
  if(!selected.length||activeAbort)return;
  error('#send-error');sendState('upload');$('#upload-progress').style.width='0%';$('#upload-percent').textContent='0%';$('#upload-status').textContent='Đang chuẩn bị file';
  const controller=new AbortController();activeAbort=controller;let session=null;
  uploadStarted=performance.now();$('#upload-speed').textContent='';
  const files=[...selected],total=files.reduce((n,f)=>n+f.size,0);
  try{
    session=await api('/api/transfers',{method:'POST',signal:controller.signal,body:JSON.stringify({files:files.map(f=>({name:f.name,size:f.size,type:f.type}))})});
    let sent=0;
    for(let i=0;i<files.length;i++){
      $('#upload-status').textContent=files[i].name;$('#upload-count').textContent='File '+(i+1)+' / '+files.length;
      await uploadFile(session,files[i],i,sent,total,controller.signal);sent+=files[i].size;
    }
    $('#upload-status').textContent='Đang hoàn tất…';
    await api('/api/transfers/'+session.code+'/complete',{method:'POST',signal:controller.signal,headers:{'X-Upload-Token':session.token}});
    $('#upload-progress').style.width='100%';$('#upload-percent').textContent='100%';
    currentShare=session;$('#generated-code').textContent=formatCode(session.code);$('#share-expiry').textContent=files.length+' file · '+size(total)+' · Hết hạn lúc '+date(session.expiresAt);
    addHistory({code:session.code,token:session.token,files:session.files,direction:'send',createdAt:Date.now(),expiresAt:session.expiresAt});
    selected=[];renderSelected();sendState('share');toast('File đã sẵn sàng. Chia sẻ mã để nhận nhé!');
  }catch(e){
    if(session)fetch('/api/transfers/'+session.code,{method:'DELETE',headers:{'X-Upload-Token':session.token},keepalive:true}).catch(()=>{});
    sendState('select');if(e.name==='AbortError')toast('Đã hủy gửi file.');else error('#send-error',e.message);
  }finally{activeAbort=null;activeXHR=null;}
});
$('#cancel-upload').addEventListener('click',()=>activeAbort?.abort());
addEventListener('beforeunload',e=>{if(activeAbort){e.preventDefault();e.returnValue='';}});
$('#new-transfer').addEventListener('click',()=>{sendState('select');currentShare=null;error('#send-error');});
async function copy(text,message){try{await navigator.clipboard.writeText(text);toast(message);}catch{const area=document.createElement('textarea');area.value=text;area.style.position='fixed';area.style.opacity='0';document.body.append(area);area.select();const ok=document.execCommand('copy');area.remove();toast(ok?message:'Không thể sao chép tự động. Hãy chọn và sao chép mã.');}}
$('#copy-code').addEventListener('click',()=>{if(currentShare)copy(currentShare.code,'Đã sao chép mã chia sẻ.');});
$('#copy-link').addEventListener('click',()=>{if(currentShare)copy(location.origin+'/#receive='+currentShare.code,'Đã sao chép liên kết nhận file.');});
$('#receive-code').addEventListener('input',e=>{e.target.value=formatCode(cleanCode(e.target.value));error('#receive-error');});
let receivedTransfer=null;
function markSaved(code,id,path){
  if(receivedTransfer?.code!==code)return;savedIds.add(id);
  const label=document.querySelector('[data-save-status="'+id+'"]');if(label){label.textContent='Đã lưu · '+path;label.classList.remove('failed');}
  const link=document.querySelector('[data-save-file="'+id+'"]');if(link){link.classList.add('saved-file');link.innerHTML=icon('check');}
  addHistory({code,files:receivedTransfer.files.filter(f=>savedIds.has(f.id)),direction:'receive',saved:true,createdAt:Date.now(),expiresAt:receivedTransfer.expiresAt});
}
async function saveDesktop(code,fileId){
  error('#receive-error');const button=$('#save-all-files');if(button)button.disabled=true;for(const file of receivedTransfer?.files||[])if(!savedIds.has(file.id)&&(!fileId||fileId===file.id)){const label=document.querySelector('[data-save-status="'+file.id+'"]');if(label)label.textContent='Đang lưu…';}
  try{const result=await desktopAction('receive',{code,...(fileId?{fileId}:{})});for(const f of result.files)markSaved(code,f.id,f.path);toast('Đã lưu '+result.files.length+' file vào '+result.directory);}catch(e){error('#receive-error',e.message);for(const file of receivedTransfer?.files||[])if(!savedIds.has(file.id)){const label=document.querySelector('[data-save-status="'+file.id+'"]');if(label){label.textContent='Chưa lưu được · Bấm để thử lại';label.classList.add('failed');}}}finally{if(button)button.disabled=false;}
}
function saveNative(code,fileId,automatic=false){for(const file of receivedTransfer?.files||[])if(!savedIds.has(file.id)&&(!fileId||file.id===fileId)){const label=document.querySelector('[data-save-status="'+file.id+'"]');if(label)label.textContent='Đang lưu…';}location.href='flowdrop-save://'+code+'/'+(fileId||'all')+(automatic?'?auto=1':'');}
window.flowdropSaveResult=data=>{
  if(receivedTransfer?.code!==data.code)return;
  if(data.status==='saved'){markSaved(data.code,data.id,data.path);toast('Đã lưu: '+data.path);}
  else if(data.status==='skipped'){toast('Đã tắt lưu tự động. Bấm file để lưu.');document.querySelectorAll('.file-save-status').forEach(label=>{if(label.textContent==='Đang lưu…')label.textContent='';});}
  else if(data.status==='error'){error('#receive-error',data.error||'Chưa lưu được file. Bấm mũi tên để thử lại.');const labels=data.id?[document.querySelector('[data-save-status="'+data.id+'"]')]:document.querySelectorAll('.file-save-status');for(const label of labels)if(label&&!label.textContent.startsWith('Đã lưu')){label.textContent='Chưa lưu được · Bấm để thử lại';label.classList.add('failed');}}
};
async function receive(code){
  error('#receive-error');$('#receiver-files').hidden=true;
  if(code.length!==8){error('#receive-error','Nhập đủ 8 ký tự của mã chia sẻ nhé.');$('#receive-code').focus();return;}
  const button=$('#receive-submit');button.disabled=true;button.innerHTML='Đang tìm file…';
  try{
    const data=await api('/api/transfers/'+code);receivedTransfer=data;savedIds=new Set();await desktopReady;
    $('#receiver-files').innerHTML='<div class="selection-summary"><span>'+data.files.length+' file · '+size(data.files.reduce((n,f)=>n+f.size,0))+'</span><span class="status-pill">Sẵn sàng tải về</span></div>'+data.files.map(f=>'<div class="file-row"><span class="file-type">'+icon('file')+'</span><div class="file-detail"><strong title="'+escape(f.name)+'">'+escape(f.name)+'</strong><span>'+size(f.size)+'</span><span data-save-status="'+f.id+'" class="file-save-status"></span></div><a class="download-file" data-save-file="'+f.id+'" href="/api/transfers/'+code+'/files/'+f.id+'" download="'+escape(f.name)+'" aria-label="Tải '+escape(f.name)+'">'+icon('receive')+'</a></div>').join('')+(desktopSettings||nativeSaver?'<button id="save-all-files" class="secondary-button full-width save-all-button">Lưu tất cả file'+icon('receive')+'</button>':'')+'<p class="download-note">File đã lưu được giữ lại khi mã hết hạn · Mã hết hạn '+date(data.expiresAt)+'</p>';
    $('#receiver-files').hidden=false;
    $('#receiver-files').querySelectorAll('.download-file').forEach(a=>a.addEventListener('click',event=>{if(desktopSettings){event.preventDefault();saveDesktop(code,a.dataset.saveFile);}else if(nativeSaver){event.preventDefault();saveNative(code,a.dataset.saveFile);}else{addHistory({code:data.code,files:data.files,direction:'receive',createdAt:Date.now(),expiresAt:data.expiresAt});toast('Đã yêu cầu tải file về thiết bị.');}}));
    $('#save-all-files')?.addEventListener('click',()=>desktopSettings?saveDesktop(code):saveNative(code));
    toast('Đã tìm thấy '+data.files.length+' file.');
    if(desktopSettings?.autoSave)await saveDesktop(code);else if(nativeSaver&&window.flowdropNativeAutoSave!==false)saveNative(code,null,true);
  }catch(e){error('#receive-error',e.message);}finally{button.disabled=false;button.innerHTML='Nhận file'+icon('receive');}
}
$('#receive-form').addEventListener('submit',e=>{e.preventDefault();receive(cleanCode($('#receive-code').value));});
function renderHistory(){
  const list=$('#history-list');$('#history-count').textContent=history.length;
  if(!history.length){list.innerHTML='<div class="empty-history"><span>'+icon('clock')+'</span><div><strong>Chuyến đi đầu tiên bắt đầu từ đây.</strong><p>Những file bạn gửi và mở nhận sẽ xuất hiện ở đây.</p></div></div>';return;}
  const visible=view==='history'?history:history.slice(0,3);
  list.innerHTML=visible.map(h=>{const expired=h.revoked||h.expiresAt<=Date.now(),total=h.total??h.files.reduce((n,f)=>n+f.size,0);return '<div class="history-row"><span class="history-direction">'+icon(h.direction==='send'?'send':'receive')+'</span><div class="history-info"><strong>'+escape(h.files[0]?.name||'File')+((h.fileCount||h.files.length)>1?' và '+((h.fileCount||h.files.length)-1)+' file khác':'')+'</strong><span>'+(h.direction==='send'?'Đã gửi':h.saved?'Đã lưu':'Đã mở nhận')+' · '+date(h.createdAt)+' · '+size(total)+'</span></div><button class="history-code" data-code="'+h.code+'" aria-label="Mở mã '+h.code+'">'+formatCode(h.code)+icon('arrow')+'</button><span class="status-pill '+(expired?'expired':'')+'">'+(h.revoked?'Đã thu hồi':expired?'Mã hết hạn':'Mã còn hiệu lực')+'</span>'+(h.direction==='send'&&!expired?'<button class="history-revoke" data-revoke="'+h.code+'" aria-label="Thu hồi lượt gửi '+h.code+'" title="Thu hồi file">'+icon('trash')+'</button>':'')+'</div>';}).join('');
  list.querySelectorAll('[data-code]').forEach(b=>b.addEventListener('click',()=>{setView('receive',true);$('#receive-code').value=formatCode(b.dataset.code);receive(b.dataset.code);}));
  list.querySelectorAll('[data-revoke]').forEach(b=>b.addEventListener('click',async()=>{
    const item=history.find(h=>h.code===b.dataset.revoke&&h.direction==='send');if(!item)return;
    if(!confirm('Thu hồi lượt gửi '+formatCode(item.code)+'? Các file sẽ bị xóa và mã không còn sử dụng được.'))return;
    b.disabled=true;
    try{await api('/api/transfers/'+item.code,{method:'DELETE',headers:{'X-Upload-Token':item.token}});history.filter(h=>h.code===item.code).forEach(h=>h.revoked=true);saveHistory();if(currentShare?.code===item.code){currentShare=null;sendState('select');}toast('Đã thu hồi và xóa file.');}catch(e){toast(e.message);b.disabled=false;}
  }));
}
function receiveFromLink(){const match=location.hash.match(/^#receive=([a-z0-9]{8})$/i);if(match){setView('receive');$('#receive-code').value=formatCode(cleanCode(match[1]));receive(cleanCode(match[1]));}}
addEventListener('hashchange',receiveFromLink);renderHistory();receiveFromLink();
fetch('/api/config').then(r=>r.ok?r.json():null).then(config=>{if(config?.mode==='local'){
  localMode=true;connectivity();
  if(config.addresses?.length){const server=config.addresses.find(url=>url===location.origin)||config.addresses[0];$('#server-address').textContent='Địa chỉ dự phòng';$('#discovery-device-name').textContent=config.discoveryName||'FlowDrop - '+config.deviceName;$('#local-connect').hidden=false;$('#copy-server-address').addEventListener('click',()=>copy(server,'Đã sao chép địa chỉ dự phòng.'));}
  $('#help-network').textContent='Windows và Android: mở FlowDrop trên Windows rồi chọn tên máy ở Android. Hai Android: một máy bấm Tạo phiên, máy kia chọn tên điện thoại đó. Cả hai đều dùng Gửi file hoặc Nhận file để chuyển qua lại.';
  $('#help-access').textContent='Cùng Wi-Fi, không cần Internet hoặc tài khoản. Thiết bị tạo phiên cần duy trì chia sẻ; có thể dừng phiên Android bằng thông báo FlowDrop. Mã hết hạn sau 24 giờ, có thể thu hồi trong lịch sử. Lịch sử chỉ lưu trên trình duyệt này.';
  const note=$('#benefits>div:last-child p');note.innerHTML='<strong>Chia sẻ ngay trong Wi-Fi</strong><span>Chọn thiết bị được tìm thấy trên Android.</span>';
}}).catch(()=>{});
