const MAX_MANIFEST=8*1024*1024,TTL=24*60*60*1000;
const assets=globalThis.__FLOWDROP_ASSETS__||{};
async function manifestText(request){
  if(!request.body)return '';
  const reader=request.body.getReader(),decoder=new TextDecoder();let bytes=0,text='';
  try{for(;;){const {done,value}=await reader.read();if(done)break;bytes+=value.byteLength;if(bytes>MAX_MANIFEST){await reader.cancel();throw new RangeError('MANIFEST_TOO_LARGE');}text+=decoder.decode(value,{stream:true});}return text+decoder.decode();}finally{reader.releaseLock();}
}
function json(value,status=200){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cross-Origin-Resource-Policy':'same-origin','Referrer-Policy':'no-referrer','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});}
function fail(message,status=400){return json({error:message},status);}
function randomCode(){const alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';return Array.from(crypto.getRandomValues(new Uint8Array(8)),x=>alphabet[x%32]).join('');}
const metaKey=code=>'transfers/'+code+'/meta.json';
const fileKey=(code,id)=>'transfers/'+code+'/files/'+id;
async function readMeta(bucket,code){const object=await bucket.get(metaKey(code));return object?object.json():null;}
async function writeMeta(bucket,meta){await bucket.put(metaKey(meta.code),JSON.stringify(meta),{httpMetadata:{contentType:'application/json'}});}
async function removeTransfer(bucket,meta){await bucket.delete(meta.files.map(f=>fileKey(meta.code,f.id)));await bucket.delete(metaKey(meta.code));await bucket.delete('expiry/'+String(meta.expiresAt)+'/'+meta.code);}
async function cleanup(bucket){
  const batch=await bucket.list({prefix:'expiry/',limit:25});
  for(const entry of batch.objects){const [,timestamp,code]=entry.key.split('/');if(Number(timestamp)>Date.now())break;const meta=await readMeta(bucket,code);if(meta&&meta.expiresAt<=Date.now())await removeTransfer(bucket,meta);else if(!meta)await bucket.delete(entry.key);}
}
const publicMeta=meta=>({code:meta.code,files:meta.files,createdAt:meta.createdAt,expiresAt:meta.expiresAt});
async function handleApi(request,env,ctx,url){
  if(url.pathname==='/api/config'&&request.method==='GET')return json({name:'FlowDrop',mode:'hosted',version:'1.5.0'});
  const bucket=env.BUCKET;
  if(!bucket)return fail('Kho lưu trữ chưa được kết nối. Vui lòng thử lại sau.',503);
  const origin=request.headers.get('Origin');
  if(origin&&origin!==url.origin||request.headers.get('Sec-Fetch-Site')&& !['same-origin','none'].includes(request.headers.get('Sec-Fetch-Site')))return fail('Yêu cầu không hợp lệ.',403);
  // Expiry is enforced on every read; physical cleanup also runs on traffic.
  if(ctx?.waitUntil)ctx.waitUntil(cleanup(bucket).catch(()=>{}));
  if(url.pathname==='/api/transfers'&&request.method==='POST'){
    if(Number(request.headers.get('Content-Length'))>MAX_MANIFEST)return fail('Danh sách tên file quá dài. Hãy chia thành các lượt nhỏ hơn.',413);
    let text;try{text=await manifestText(request);}catch(error){if(error instanceof RangeError)return fail('Danh sách tên file quá dài. Hãy chia thành các lượt nhỏ hơn.',413);return fail('Chưa nhận đủ danh sách file.');}
    let input;try{input=JSON.parse(text);}catch{return fail('Dữ liệu không hợp lệ.');}
    if(!Array.isArray(input.files)||input.files.length<1)return fail('Chọn ít nhất một file.');
    let total=0;
    for(const f of input.files){if(!f||typeof f.name!=='string'||!f.name.trim()||f.name.length>255||/[\x00-\x1f\x7f]/.test(f.name)||!Number.isSafeInteger(f.size)||f.size<0)return fail('Tên hoặc dung lượng file không hợp lệ.');total+=f.size;}
    if(!Number.isSafeInteger(total))return fail('Dung lượng vượt phạm vi biểu diễn của giao thức.');
    if(bucket.availableSpace){const available=await bucket.availableSpace();if(available!==null&&total+20*1024*1024>available)return fail('Thiết bị tạo phiên không đủ dung lượng trống.',507);}
    let code;
    for(let i=0;i<5;i++){const candidate=randomCode();if(!await bucket.head(metaKey(candidate))){code=candidate;break;}}
    if(!code)return fail('Chưa tạo được mã. Hãy thử lại.',503);
    const now=Date.now();
    const meta={code,token:crypto.randomUUID()+crypto.randomUUID(),createdAt:now,expiresAt:now+TTL,status:'uploading',files:input.files.map(f=>({id:crypto.randomUUID(),name:f.name,size:f.size,type:typeof f.type==='string'?f.type.slice(0,150):''}))};
    if(new TextEncoder().encode(JSON.stringify(meta)).byteLength>MAX_MANIFEST-4096)return fail('Danh sách tên file quá dài. Hãy chia thành các lượt nhỏ hơn.',413);
    await writeMeta(bucket,meta);await bucket.put('expiry/'+String(meta.expiresAt)+'/'+code,'');
    return json({...publicMeta(meta),token:meta.token},201);
  }
  const match=url.pathname.match(/^\/api\/transfers\/([A-Z2-9]{8})(?:\/(complete|files\/([a-f0-9-]{36})))?$/);
  if(!match)return fail('Không tìm thấy đường dẫn.',404);
  const [,code,action,id]=match,meta=await readMeta(bucket,code);
  if(!meta)return fail('Không tìm thấy mã. Kiểm tra lại mã hoặc mã đã được thu hồi.',404);
  if(meta.expiresAt<=Date.now()){if(ctx?.waitUntil)ctx.waitUntil(removeTransfer(bucket,meta));return fail('Mã này đã hết hạn. Hãy yêu cầu gửi lại file.',410);}
  const authorized=request.headers.get('X-Upload-Token')===meta.token;
  if(request.method==='DELETE'&&!action){if(!authorized)return fail('Bạn không có quyền thu hồi lượt gửi này.',403);await removeTransfer(bucket,meta);return json({ok:true});}
  if(request.method==='GET'&&!action){if(meta.status!=='ready')return fail('File đang được tải lên. Vui lòng chờ người gửi hoàn tất.',409);return json(publicMeta(meta));}
  if(request.method==='POST'&&action==='complete'){
    if(!authorized)return fail('Không có quyền hoàn tất lượt gửi.',403);
    for(const file of meta.files){const head=await bucket.head(fileKey(code,file.id));if(!head||head.size!==file.size)return fail('Có file chưa tải lên hoàn tất. Vui lòng gửi lại.',409);}
    meta.status='ready';await writeMeta(bucket,meta);return json(publicMeta(meta));
  }
  if(id){
    const file=meta.files.find(f=>f.id===id);if(!file)return fail('Không tìm thấy file.',404);
    if(request.method==='PUT'){
      if(!authorized||meta.status!=='uploading')return fail('Không có quyền tải file lên.',403);
      const contentLength=request.headers.get('Content-Length');
      if(contentLength!==null&&Number(contentLength)!==file.size)return fail('Dung lượng file không khớp.',400);
      let bytes=0;
      const stream=request.body?.pipeThrough(new TransformStream({transform(chunk,controller){bytes+=chunk.byteLength;if(bytes>file.size)throw new Error('TOO_LARGE');controller.enqueue(chunk);}}));
      try{
        const options={httpMetadata:{contentType:'application/octet-stream'}};
        if(stream&&typeof FixedLengthStream!=='undefined'){
          const fixed=new FixedLengthStream(file.size);
          await Promise.all([stream.pipeTo(fixed.writable),bucket.put(fileKey(code,id),fixed.readable,options)]);
        }else await bucket.put(fileKey(code,id),stream||new Uint8Array(0),options);
      }catch(error){await bucket.delete(fileKey(code,id));if(error.code==='ENOSPC')return fail('Thiết bị tạo phiên không đủ dung lượng trống.',507);return fail('Kết nối bị ngắt hoặc dữ liệu không khớp với file đã chọn.',413);}
      if(bytes!==file.size){await bucket.delete(fileKey(code,id));return fail('File chưa được tải lên đầy đủ.',400);}
      // A revoke can occur on another device while the upload is in flight.
      const stillActive=await readMeta(bucket,code);if(!stillActive||stillActive.expiresAt<=Date.now()){await bucket.delete(fileKey(code,id));return fail('Lượt gửi không còn hiệu lực.',410);}
      return json({ok:true});
    }
    if(request.method==='GET'){
      if(meta.status!=='ready')return fail('File chưa sẵn sàng.',409);
      const object=await bucket.get(fileKey(code,id));if(!object)return fail('File không còn khả dụng. Hãy yêu cầu gửi lại.',404);
      const asciiName=file.name.replace(/[^\x20-\x7e]|["\\]/g,'_');
      return new Response(object.body,{headers:{'Content-Type':'application/octet-stream','Content-Length':String(file.size),'Content-Disposition':'attachment; filename="'+asciiName+'"; filename*=UTF-8\'\''+encodeURIComponent(file.name).replace(/['()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase()),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}});
    }
  }
  return fail('Phương thức không được hỗ trợ.',405);
}
export default{
  async fetch(request,env,ctx){
    const url=new URL(request.url);
    try{
      if(url.pathname.startsWith('/api/'))return await handleApi(request,env,ctx,url);
      if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405});
      const asset=assets[url.pathname];if(!asset)return new Response('Không tìm thấy trang',{status:404});
      return new Response(request.method==='HEAD'?null:asset.base64?Uint8Array.from(atob(asset.base64),c=>c.charCodeAt(0)):asset.body,{headers:{'Content-Type':asset.type,'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"}});
    }catch(e){console.error('FlowDrop request failed',url.pathname,e?.message);return fail('Hệ thống đang bận. Vui lòng thử lại sau.',500);}
  }
};
