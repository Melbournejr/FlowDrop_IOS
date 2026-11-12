package app.flowdrop.mobile;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.SecureRandom;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.*;

/** A streaming HTTP/file server shared by the Android host and JVM integration tests. */
public final class TransferServer implements Closeable {
  public interface Connections{HttpURLConnection open(URL url)throws Exception;}
  private volatile Connections networkConnections;
  public void setConnections(Connections provider){networkConnections=provider;}
  public interface Assets { InputStream open(String name) throws IOException; }
  private static final long MAX_EXACT_SIZE=9007199254740991L, TTL=86400000L;
  private static final int MAX_MANIFEST=8*1024*1024;
  private static final Pattern ROUTE=Pattern.compile("^/api/transfers/([A-Z2-9]{8})(?:/(complete|files/([a-f0-9-]{36})))?$");
  private static final String ALPHABET="ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  private final Path directory;
  private final Assets assets;
  private final ServerSocket socket;
  private final ThreadPoolExecutor clients;
  private final ScheduledExecutorService cleanup;
  private final SecureRandom random=new SecureRandom();
  private final Object[] locks=new Object[64];
  private final Set<Socket> connections=Collections.newSetFromMap(new ConcurrentHashMap<Socket,Boolean>());
  private volatile boolean closed=false;
  private volatile String deviceName,discoveryName;
  private final String deviceId,offerKey=UUID.randomUUID().toString();
  private final Map<String,JSONObject> offers=new LinkedHashMap<>(),outgoing=new LinkedHashMap<>();
  private final Semaphore incomingChecks=new Semaphore(2);
  private final Set<String> polling=new HashSet<>();
  private final ExecutorService statusWorkers=Executors.newFixedThreadPool(2,r->{Thread t=new Thread(r,"flowdrop-status");t.setDaemon(true);return t;});
  public String getDeviceId(){return deviceId;}
  private static boolean ended(String state){return Arrays.asList("completed","rejected","failed","expired","untracked").contains(state);}
  private static void state(JSONObject item,String state){try{item.put("state",state).put("updatedAt",System.currentTimeMillis());if(ended(state))item.put("finishedAt",System.currentTimeMillis());}catch(Exception e){throw new IllegalStateException(e);}}
  private static JSONObject visible(JSONObject item)throws Exception{
    JSONObject result=new JSONObject();for(String key:new String[]{"id","direction","name","code","count","size","bytes","filesDone","currentName","state","createdAt","startedAt","updatedAt","finishedAt","error","connectionError"})if(item.has(key))result.put(key,item.get(key));
    return result;
  }
  public synchronized JSONArray pendingOffers()throws Exception{pruneOffers();JSONArray result=new JSONArray();for(JSONObject item:offers.values())if("pending".equals(item.optString("state")))result.put(visible(item).put("origin",item.getString("origin")));return result;}
  private synchronized void pruneOffers(){
    long now=System.currentTimeMillis();for(JSONObject item:offers.values())if("pending".equals(item.optString("state"))&&item.optLong("expiresAt")<now)state(item,"expired");
    for(Map<String,JSONObject> map:Arrays.asList(offers,outgoing)){
      for(JSONObject item:map.values())if(!ended(item.optString("state"))&&now-item.optLong("createdAt")>TTL)state(item,"expired");
      ArrayList<JSONObject> done=new ArrayList<>();for(JSONObject item:map.values())if(ended(item.optString("state")))done.add(item);
      done.sort((x,y)->Long.compare(y.optLong("createdAt"),x.optLong("createdAt")));for(int i=0;i<done.size();i++)if(i>=50||now-done.get(i).optLong("createdAt")>TTL)map.remove(done.get(i).optString("id"));
    }
  }
  public synchronized JSONArray sessions()throws Exception{pruneOffers();ArrayList<JSONObject> items=new ArrayList<>(offers.values());items.addAll(outgoing.values());items.sort((a,b)->Long.compare(b.optLong("createdAt"),a.optLong("createdAt")));JSONArray result=new JSONArray();for(JSONObject item:items)result.put(visible(item));return result;}
  public synchronized String beginCodeReceive(String origin,JSONObject metadata,String selected)throws Exception{
    String code=metadata.getString("code");CodeLookup.validate(metadata,code);String base=origin.endsWith("/")?origin:origin+"/",selection=selected==null?"":selected;
    for(JSONObject old:offers.values())if(old.optBoolean("codeReceive")&&!ended(old.optString("state"))&&base.equals(old.optString("origin"))&&code.equals(old.optString("code"))&&selection.equals(old.optString("selection")))return old.getString("id");
    JSONArray files=metadata.getJSONArray("files");long size=0;int count=0;for(int i=0;i<files.length();i++){JSONObject file=files.getJSONObject(i);if(selected==null||selected.equals(file.getString("id"))){size+=file.getLong("size");count++;}}
    if(count==0)throw new IOException("Không tìm thấy file trong mã.");
    long now=System.currentTimeMillis();JSONObject item=new JSONObject().put("id",UUID.randomUUID().toString()).put("direction","receive").put("name","Nhận bằng mã · "+new URI(base).getHost()).put("origin",base).put("code",code).put("count",count).put("size",size).put("bytes",0).put("filesDone",0).put("state","accepted").put("createdAt",now).put("startedAt",now).put("updatedAt",now).put("statusToken",UUID.randomUUID().toString()).put("codeReceive",true).put("selection",selection);
    offers.put(item.getString("id"),item);return item.getString("id");
  }
  public synchronized JSONObject answerOffer(String id,boolean accept)throws Exception{
    pruneOffers();JSONObject item=offers.get(id);if(item==null||!"pending".equals(item.optString("state")))throw new IOException("Yêu cầu đã hết hạn hoặc đã xử lý.");
    state(item,accept?"accepted":"rejected");if(accept)item.put("startedAt",System.currentTimeMillis());return accept?new JSONObject(item.toString()):null;
  }
  public synchronized void receiveProgress(String id,long bytes,int filesDone,String current)throws Exception{
    JSONObject item=offers.get(id);if(item==null||ended(item.optString("state")))return;
    if(bytes<item.optLong("bytes")||bytes>item.getLong("size")||filesDone<item.optInt("filesDone")||filesDone>item.getInt("count"))throw new IOException("Tiến độ nhận không hợp lệ.");
    item.put("bytes",bytes).put("filesDone",filesDone).put("currentName",current);state(item,"transferring");
  }
  public synchronized void receiveFinished(String id,String error)throws Exception{
    JSONObject item=offers.get(id);if(item==null||ended(item.optString("state")))return;
    if(error!=null){item.put("error",error);state(item,"failed");return;}
    if(item.optLong("bytes")!=item.getLong("size")||item.optInt("filesDone")!=item.getInt("count"))throw new IOException("Chưa lưu đủ file để hoàn tất phiên.");
    item.put("currentName","");state(item,"completed");
  }
  private synchronized JSONObject sessionStatus(String id,String token)throws Exception{
    pruneOffers();JSONObject item=offers.get(id);if(item==null||token.isEmpty()||!RequestSecurity.secret(token,item.optString("statusToken")))throw new HttpError(403,"Không có quyền xem phiên truyền.");return visible(item);
  }
  public JSONObject offerTo(String target,String code)throws Exception{
    URI uri=new URI(target);if(!"http".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null)throw new IOException("Địa chỉ FlowDrop không hợp lệ.");
    String origin="http://"+uri.getRawAuthority(),statusToken=UUID.randomUUID().toString();JSONObject config=remoteJson(origin,"/api/config");
    if(!"FlowDrop".equals(config.optString("name"))||config.optString("offerKey").isEmpty()||deviceId.equals(config.optString("deviceId")))throw new IOException("Thiết bị nhận chưa sẵn sàng.");
    JSONObject transfer; synchronized(lock(code)){transfer=metadata(code);if(!"ready".equals(transfer.optString("status")))throw new IOException("File chưa chuẩn bị xong.");}
    JSONArray files=transfer.getJSONArray("files");long size=0;for(int i=0;i<files.length();i++)size+=files.getJSONObject(i).getLong("size");long now=System.currentTimeMillis();
    JSONObject item=new JSONObject().put("id",UUID.randomUUID().toString()).put("direction","send").put("name",RequestSecurity.label(config.optString("deviceName","Thiết bị"),100)).put("code",code).put("count",files.length()).put("size",size).put("bytes",0).put("filesDone",0).put("state","pending").put("createdAt",now).put("updatedAt",now).put("origin",origin).put("statusToken",statusToken);
    synchronized(this){outgoing.put(item.getString("id"),item);}
    try{
      JSONObject reply=remoteJson(origin,"/api/offers",new JSONObject().put("code",code).put("port",getPort()).put("deviceId",deviceId).put("offerKey",config.getString("offerKey")).put("statusToken",statusToken));
      synchronized(this){if(!reply.getString("id").matches("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"))throw new IOException("Mã phiên nhận không hợp lệ.");item.put("remoteId",reply.getString("id"));if(reply.optInt("tracking")!=1){item.put("error","Cập nhật FlowDrop 1.8 trên máy nhận để xem tiến độ.");state(item,"untracked");}}
      return reply.put("sessionId",item.getString("id"));
    }catch(Exception e){synchronized(this){item.put("error",e.getMessage());state(item,"failed");}throw e;}
  }
  private void pollSessions(){
    ArrayList<JSONObject> todo=new ArrayList<>();synchronized(this){pruneOffers();for(JSONObject item:outgoing.values())if(!ended(item.optString("state"))&&item.has("remoteId")&&polling.add(item.optString("id")))todo.add(item);}
    for(JSONObject item:todo)statusWorkers.submit(()->{try{
      JSONObject status=remoteJson(item.optString("origin"),"/api/offers/status",new JSONObject().put("id",item.getString("remoteId")).put("token",item.getString("statusToken")));
      long bytes=status.getLong("bytes");int done=status.getInt("filesDone");String next=status.getString("state");
      if(status.getLong("size")!=item.getLong("size")||status.getInt("count")!=item.getInt("count")||bytes<0||bytes>item.getLong("size")||done<0||done>item.getInt("count")||!Arrays.asList("pending","accepted","transferring","completed","rejected","failed","expired").contains(next)||"completed".equals(next)&&(bytes!=item.getLong("size")||done!=item.getInt("count")))throw new IOException("Máy nhận trả trạng thái không hợp lệ.");
      for(String key:new String[]{"startedAt","updatedAt","finishedAt"})if(status.has(key)){Object value=status.get(key);if(!(value instanceof Number)||((Number)value).doubleValue()!=((Number)value).longValue()||((Number)value).longValue()<0||((Number)value).longValue()>MAX_EXACT_SIZE)throw new IOException("Thời gian phiên truyền không hợp lệ.");}
      for(String key:new String[]{"currentName","error"})if(status.has(key)&&!(status.get(key) instanceof String))throw new IOException("Trạng thái phiên truyền không hợp lệ.");
      status.put("currentName",RequestSecurity.label(status.optString("currentName"),255));status.put("error",RequestSecurity.label(status.optString("error"),500));
      synchronized(this){for(String key:new String[]{"state","bytes","filesDone","currentName","startedAt","updatedAt","finishedAt","error"})item.put(key,status.opt(key));item.remove("connectionError");}
    }catch(Exception e){synchronized(this){try{item.put("connectionError","Mất kết nối · đang thử lại").put("error",e.getMessage());}catch(Exception ignored){}}}finally{synchronized(this){polling.remove(item.optString("id"));}}});
  }
  private JSONObject remoteJson(String origin,String route)throws Exception{return remoteJson(origin,route,null);}
  private JSONObject remoteJson(String origin,String route,JSONObject body)throws Exception{
    URL target=new URL(origin+route);Connections provider=networkConnections;HttpURLConnection connection=provider==null?(HttpURLConnection)target.openConnection():provider.open(target);connection.setConnectTimeout(3000);connection.setReadTimeout(5000);connection.setInstanceFollowRedirects(false);
    try{if(body!=null){connection.setRequestMethod("POST");connection.setDoOutput(true);connection.setRequestProperty("Content-Type","application/json");byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);connection.setFixedLengthStreamingMode(bytes.length);try(OutputStream out=connection.getOutputStream()){out.write(bytes);}}
      int status=connection.getResponseCode();if(status<200||status>=300)throw new IOException("Chưa lấy được trạng thái thiết bị nhận.");try(InputStream in=connection.getInputStream()){return new JSONObject(new String(readSmall(in,MAX_MANIFEST),StandardCharsets.UTF_8));}
    }finally{connection.disconnect();}
  }
  private void incomingOffer(Request request,OutputStream output,String address)throws Exception{
    JSONObject body=new JSONObject(new String(readSmall(request.body,16384),StandardCharsets.UTF_8));
    if(!offerKey.equals(body.optString("offerKey")))throw new HttpError(403,"Mở lại danh sách thiết bị rồi gửi lại.");
    String code=body.optString("code"),sender=body.optString("deviceId");int port=body.optInt("port");
    if(!address.matches("[0-9.]+")||port<1||port>65535||!code.matches("[A-Z2-9]{8}")||sender.isEmpty()||deviceId.equals(sender))throw new HttpError(400,"Thiết bị gửi không hợp lệ.");
    synchronized(this){pruneOffers();if(offers.values().stream().filter(i->!ended(i.optString("state"))).count()>=20)throw new HttpError(429,"Đang có nhiều yêu cầu nhận. Hãy thử lại sau.");}
    if(!incomingChecks.tryAcquire())throw new HttpError(429,"Đang xác minh nhiều yêu cầu. Thử lại sau.");
    try{
    String origin="http://"+address+":"+port;JSONObject config=remoteJson(origin,"/api/config");
    if(!"FlowDrop".equals(config.optString("name"))||!sender.equals(config.optString("deviceId")))throw new HttpError(400,"Không xác minh được thiết bị gửi.");
    JSONObject metadata=remoteJson(origin,"/api/transfers/"+code);CodeLookup.validate(metadata,code);JSONArray files=metadata.getJSONArray("files");long size=0;for(int i=0;i<files.length();i++)size+=files.getJSONObject(i).getLong("size");
    JSONObject item=new JSONObject().put("id",UUID.randomUUID().toString()).put("origin",origin+"/").put("code",code).put("name",RequestSecurity.label(config.optString("deviceName","Thiết bị"),100)).put("count",files.length()).put("size",size).put("expiresAt",System.currentTimeMillis()+120000).put("direction","receive").put("state","pending").put("bytes",0).put("filesDone",0).put("createdAt",System.currentTimeMillis()).put("updatedAt",System.currentTimeMillis()).put("statusToken",body.optString("statusToken",UUID.randomUUID().toString()));
    synchronized(this){pruneOffers();for(JSONObject previous:offers.values())if(!ended(previous.optString("state"))&&previous.optString("origin").equals(origin+"/")&&previous.optString("code").equals(code)&&previous.optString("statusToken").equals(body.optString("statusToken"))){sendJson(output,201,new JSONObject().put("id",previous.getString("id")).put("state",previous.optString("state")).put("tracking",1));return;}if(offers.values().stream().filter(i->!ended(i.optString("state"))).count()>=20)throw new HttpError(429,"Đang có nhiều yêu cầu nhận.");offers.put(item.getString("id"),item);}
    sendJson(output,201,new JSONObject().put("id",item.getString("id")).put("state","pending").put("tracking",1));    }finally{incomingChecks.release();}
  }

  public TransferServer(File directory,Assets assets,String deviceName,int preferredPort) throws IOException {
    this.directory=directory.toPath();this.assets=assets;this.deviceName=deviceName;this.discoveryName="FlowDrop - "+deviceName;
    Files.createDirectories(this.directory);
    Path idFile=this.directory.resolve("device-id");if(!Files.exists(idFile))Files.write(idFile,UUID.randomUUID().toString().getBytes(StandardCharsets.UTF_8));deviceId=new String(Files.readAllBytes(idFile),StandardCharsets.UTF_8).trim();
    for(int i=0;i<locks.length;i++)locks[i]=new Object();
    ServerSocket bound=new ServerSocket();bound.setReuseAddress(true);
    try{bound.bind(new InetSocketAddress(preferredPort),32);}catch(BindException conflict){bound.close();bound=new ServerSocket(0,32);}
    socket=bound;socketWatch.scheduleWithFixedDelay(()->{long now=System.nanoTime();for(Map.Entry<Socket,Long> entry:activity.entrySet())if(now-entry.getValue()>TimeUnit.SECONDS.toNanos(120))try{entry.getKey().close();}catch(IOException ignored){}},5,5,TimeUnit.SECONDS);
    // Keep short discovery/status requests responsive while large file streams run.
    clients=new ThreadPoolExecutor(8,16,30,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(32),r->{Thread t=new Thread(r,"flowdrop-client");t.setDaemon(true);return t;});
    cleanup=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"flowdrop-cleanup");t.setDaemon(true);return t;});
    cleanup.scheduleWithFixedDelay(()->cleanExpired(),0,10,TimeUnit.MINUTES);
    cleanup.scheduleWithFixedDelay(()->pollSessions(),1,1,TimeUnit.SECONDS);
    Thread accept=new Thread(()->acceptLoop(),"flowdrop-http");accept.setDaemon(true);accept.start();
  }
  private final java.util.concurrent.ConcurrentMap<Socket,Long> activity=new java.util.concurrent.ConcurrentHashMap<>();
  private final ScheduledExecutorService socketWatch=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"flowdrop-socket-watch");t.setDaemon(true);return t;});
  private final String uploadCapability=UUID.randomUUID().toString()+UUID.randomUUID().toString();
  public String getUploadCapability(){return uploadCapability;}
  public int getPort(){return socket.getLocalPort();}
  public String getLocalUrl(){return "http://127.0.0.1:"+getPort()+"/";}
  public void setDeviceName(String name){deviceName=name;}
  public void setDiscoveryName(String name){discoveryName=name;}
  private Object lock(String code){return locks[(code.hashCode()&0x7fffffff)%locks.length];}
  private void acceptLoop(){
    while(!closed)try{
      Socket client=socket.accept();client.setSoTimeout(10000);connections.add(client);activity.put(client,System.nanoTime());
      try{clients.execute(()->handle(client));}catch(RejectedExecutionException busy){connections.remove(client);activity.remove(client);client.close();}
    }catch(IOException error){if(!closed)close();}
  }
  private void handle(Socket client){
    try(Socket ignored=client){
      InputStream input=new BufferedInputStream(new FilterInputStream(client.getInputStream()){
        public int read()throws IOException{int n=in.read();if(n>=0)activity.put(client,System.nanoTime());return n;}
        public int read(byte[] bytes,int off,int length)throws IOException{int n=in.read(bytes,off,length);if(n>0)activity.put(client,System.nanoTime());return n;}
      });OutputStream output=new BufferedOutputStream(new FilterOutputStream(client.getOutputStream()){
        public void write(int value)throws IOException{out.write(value);activity.put(client,System.nanoTime());}
        public void write(byte[] bytes,int off,int length)throws IOException{out.write(bytes,off,length);activity.put(client,System.nanoTime());}
      });
      try{HeaderInput guarded=new HeaderInput(input,client);Request request=parse(guarded,output);guarded.finish();route(request,output,client.getInetAddress().getHostAddress());}catch(java.net.SocketTimeoutException timeout){sendJson(output,408,new JSONObject().put("error","Hết thời gian gửi header."));}catch(HttpError error){sendJson(output,error.status,new JSONObject().put("error",error.getMessage()));}
      catch(Exception error){sendJson(output,500,new JSONObject().put("error","Chưa thực hiện được. Kiểm tra kết nối và dung lượng trống trên điện thoại."));}
      output.flush();
    }catch(Exception ignored){}finally{connections.remove(client);activity.remove(client);}
  }
  private static final class HeaderInput extends FilterInputStream {
    final Socket socket;final long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(10);boolean headers=true;
    HeaderInput(InputStream input,Socket socket){super(input);this.socket=socket;}
    void deadline()throws IOException{if(headers){long left=java.util.concurrent.TimeUnit.NANOSECONDS.toMillis(deadline-System.nanoTime());if(left<=0)throw new SocketTimeoutException();socket.setSoTimeout((int)Math.max(1,left));}}
    void finish()throws IOException{headers=false;socket.setSoTimeout(120000);}
    public int read()throws IOException{deadline();return in.read();}
    public int read(byte[] bytes,int off,int len)throws IOException{deadline();return in.read(bytes,off,len);}
  }
  private static final class HttpError extends IOException {final int status;HttpError(int status,String text){super(text);this.status=status;}}
  private static final class Request {
    final String method,path;final Map<String,String> headers;final InputStream body;final long length;
    Request(String method,String path,Map<String,String> headers,InputStream body,long length){this.method=method;this.path=path;this.headers=headers;this.body=body;this.length=length;}
  }
  private static String line(InputStream in,int maximum)throws IOException{
    ByteArrayOutputStream bytes=new ByteArrayOutputStream();int c;
    while((c=in.read())!=-1){if(c=='\n'){byte[] data=bytes.toByteArray();int length=data.length;if(length<1||data[length-1]!='\r')throw new HttpError(400,"Header cần kết thúc CRLF.");length--;return new String(data,0,length,StandardCharsets.ISO_8859_1);}if(bytes.size()>=maximum)throw new HttpError(431,"Header quá lớn.");bytes.write(c);}
    throw new EOFException("Incomplete request");
  }
  private static Request parse(InputStream input,OutputStream output)throws Exception{
    String[] first=line(input,4096).split(" ");if(first.length!=3||!(first[2].equals("HTTP/1.1")||first[2].equals("HTTP/1.0")))throw new HttpError(400,"Yêu cầu không hợp lệ.");
    String path;try{URI uri=new URI(first[1]);if(uri.isAbsolute()||uri.getRawAuthority()!=null||!first[1].startsWith("/")||uri.getRawFragment()!=null)throw new Exception();path=uri.getRawPath();}catch(Exception e){throw new HttpError(400,"Đường dẫn không hợp lệ.");}
    Map<String,String> headers=new HashMap<>();int count=0;
    while(true){String header=line(input,8192);count+=header.length()+2;if(count>16384)throw new HttpError(431,"Header quá lớn.");if(header.isEmpty())break;int colon=header.indexOf(':');if(colon<1)throw new HttpError(400,"Header không hợp lệ.");String rawKey=header.substring(0,colon);if(!rawKey.matches("[!#$%&'*+.^_`|~0-9A-Za-z-]+"))throw new HttpError(400,"Header không hợp lệ.");String key=rawKey.toLowerCase(Locale.ROOT);if(headers.containsKey(key)&&("content-length".equals(key)||"transfer-encoding".equals(key)||"host".equals(key)||"origin".equals(key)||"x-local-token".equals(key)||"x-upload-token".equals(key)))throw new HttpError(400,"Header trùng lặp.");headers.put(key,header.substring(colon+1).trim());}
    String transfer=headers.get("transfer-encoding");long length=0;InputStream body;
    if(transfer!=null){if(!"chunked".equalsIgnoreCase(transfer)||headers.containsKey("content-length"))throw new HttpError(400,"Body không hợp lệ.");length=-1;body=new Chunked(input);}
    else{try{String declared=headers.getOrDefault("content-length","0");if(!declared.matches("[0-9]+"))throw new NumberFormatException();length=Long.parseLong(declared);}catch(NumberFormatException e){throw new HttpError(400,"Dung lượng không hợp lệ.");}if(length<0)throw new HttpError(413,"Dung lượng không hợp lệ.");body=new Limited(input,length);}
    if("100-continue".equalsIgnoreCase(headers.get("expect"))){output.write("HTTP/1.1 100 Continue\r\n\r\n".getBytes(StandardCharsets.US_ASCII));output.flush();output.flush();}
    return new Request(first[0],path,headers,body,length);
  }
  private static class Limited extends InputStream {
    final InputStream source;long left;Limited(InputStream source,long count){this.source=source;left=count;}
    @Override public int read()throws IOException{if(left==0)return -1;int n=source.read();if(n<0)throw new EOFException();left--;return n;}
    @Override public int read(byte[] bytes,int offset,int length)throws IOException{if(length==0)return 0;if(left==0)return -1;int n=source.read(bytes,offset,(int)Math.min(left,length));if(n<0)throw new EOFException();left-=n;return n;}
  }
  private static final class Chunked extends InputStream {
    final InputStream source;long left=0,total=0;boolean done=false,needsEnd=false;
    Chunked(InputStream source){this.source=source;}
    private boolean next()throws IOException{
      if(done)return false;if(left>0)return true;
      if(needsEnd){if(source.read()!='\r'||source.read()!='\n')throw new HttpError(400,"Chunk không hợp lệ.");needsEnd=false;}
      String size=line(source,128).split(";",2)[0].trim();try{if(!size.matches("[0-9a-fA-F]+"))throw new NumberFormatException();left=Long.parseLong(size,16);}catch(NumberFormatException e){throw new HttpError(400,"Chunk không hợp lệ.");}
      if(left<0||left>Long.MAX_VALUE-total)throw new HttpError(413,"Dung lượng không hợp lệ.");
      if(left==0){int count=0;String trailer;while(!(trailer=line(source,4096)).isEmpty()){count+=trailer.length();if(count>4096)throw new HttpError(400,"Trailer quá lớn.");}done=true;return false;}
      needsEnd=true;return true;
    }
    @Override public int read()throws IOException{byte[] bytes=new byte[1];return read(bytes,0,1)<0?-1:bytes[0]&255;}
    @Override public int read(byte[] bytes,int offset,int length)throws IOException{if(length==0)return 0;if(!next())return -1;int n=source.read(bytes,offset,(int)Math.min(left,length));if(n<0)throw new EOFException();left-=n;total+=n;return n;}
  }
  private static byte[] readSmall(InputStream input,int limit)throws IOException{
    ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[2048];int n;
    while((n=input.read(buffer))!=-1){if(bytes.size()+n>limit)throw new HttpError(413,"Dữ liệu quá lớn.");bytes.write(buffer,0,n);}return bytes.toByteArray();
  }
  private void route(Request request,OutputStream output,String remoteAddress)throws Exception{
    String path=request.path,method=request.method;
    if(!RequestSecurity.allowedHost(request.headers.get("host"),getPort()))throw new HttpError(403,"Địa chỉ truy cập không được phép.");
    if(path.startsWith("/api/")&&!RequestSecurity.browserAllowed(request.headers))throw new HttpError(403,"Yêu cầu từ website khác bị chặn.");
    if(path.equals("/api/transfers")&&method.equals("POST")&&(!InetAddress.getByName(remoteAddress).isLoopbackAddress()||!RequestSecurity.secret(request.headers.get("x-local-token"),uploadCapability)))throw new HttpError(403,"Chỉ ứng dụng FlowDrop trên máy này được tạo phiên gửi.");
    if("/api/config".equals(path)&&"GET".equals(method)){
      JSONArray addresses=new JSONArray();Enumeration<NetworkInterface> interfaces=NetworkInterface.getNetworkInterfaces();
      while(interfaces!=null&&interfaces.hasMoreElements()){NetworkInterface iface=interfaces.nextElement();Enumeration<InetAddress> list=iface.getInetAddresses();while(list.hasMoreElements()){InetAddress address=list.nextElement();if(address instanceof Inet4Address&&!address.isLoopbackAddress()&&!address.isLinkLocalAddress())addresses.put("http://"+address.getHostAddress()+":"+getPort());}}
      sendJson(output,200,new JSONObject().put("name","FlowDrop").put("version","1.13.0").put("deviceId",deviceId).put("offerKey",offerKey).put("direct",1).put("sessions",1).put("mode","local").put("platform","android").put("deviceName",deviceName).put("discoveryName",discoveryName).put("discovery","mdns+lan").put("addresses",addresses));return;
    }
    if("/api/offers/status".equals(path)&&"POST".equals(method)){JSONObject body=new JSONObject(new String(readSmall(request.body,16384),StandardCharsets.UTF_8));sendJson(output,200,sessionStatus(body.optString("id"),body.optString("token")));return;}
    if("/api/offers".equals(path)&&"POST".equals(method)){incomingOffer(request,output,remoteAddress);return;}
    if("/api/transfers".equals(path)&&"POST".equals(method)){create(request,output);return;}
    if(path.startsWith("/api/")){
      Matcher match=ROUTE.matcher(path);if(!match.matches())throw new HttpError(404,"Không tìm thấy đường dẫn.");
      String code=match.group(1);synchronized(lock(code)){transfer(request,output,code,match.group(2),match.group(3));}return;
    }
    if(!"GET".equals(method)&&!"HEAD".equals(method))throw new HttpError(405,"Phương thức không được hỗ trợ.");
    if(assets==null){if("/".equals(path)){sendBytes(output,200,"text/plain; charset=utf-8","FlowDrop Native Android — mở ứng dụng FlowDrop để gửi và nhận file.".getBytes(StandardCharsets.UTF_8),"HEAD".equals(method));return;}throw new HttpError(404,"Ứng dụng Android dùng giao diện native.");}
    String asset,type;
    if("/".equals(path)){asset="index.html";type="text/html; charset=utf-8";}
    else if("/app.js".equals(path)){asset="app.js";type="text/javascript; charset=utf-8";}
    else if("/style.css".equals(path)){asset="style.css";type="text/css; charset=utf-8";}
    else if(path.matches("/assets/fonts/BeVietnamPro-(Regular|Medium|Bold)\\.ttf")){asset=path.substring(1);type="font/ttf";}
    else if("/favicon.svg".equals(path)){sendBytes(output,200,"image/svg+xml","<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 48 48\"><rect width=\"48\" height=\"48\" rx=\"12\" fill=\"#1b654e\"/><path d=\"M13 18a12 12 0 0 1 21-3l2 2m0-9v9h-9M35 30a12 12 0 0 1-21 3l-2-2m0 9v-9h9\" stroke=\"white\" stroke-width=\"3\" fill=\"none\"/></svg>".getBytes(StandardCharsets.UTF_8),false);return;}
    else if("/manifest.webmanifest".equals(path)){sendJson(output,200,new JSONObject().put("name","FlowDrop").put("short_name","FlowDrop").put("start_url","/").put("display","standalone"));return;}
    else throw new HttpError(404,"Không tìm thấy trang.");
    try(InputStream input=assets.open(asset)){sendBytes(output,200,type,readSmall(input,1024*1024),"HEAD".equals(method));}
  }
  private String code(){StringBuilder code=new StringBuilder();for(int i=0;i<8;i++)code.append(ALPHABET.charAt(random.nextInt(32)));return code.toString();}
  private Path folder(String code){return directory.resolve(code);}
  private Path file(String code,String id){return folder(code).resolve(id);}
  private JSONObject metadata(String code)throws Exception{Path path=folder(code).resolve("meta.json");if(!Files.exists(path))throw new HttpError(404,"Không tìm thấy mã hoặc mã đã được thu hồi.");return new JSONObject(new String(Files.readAllBytes(path),StandardCharsets.UTF_8));}
  private void save(String code,JSONObject metadata)throws Exception{
    Path temporary=folder(code).resolve("meta.tmp");Files.write(temporary,metadata.toString().getBytes(StandardCharsets.UTF_8));move(temporary,folder(code).resolve("meta.json"));
  }
  private static void move(Path source,Path target)throws IOException{try{Files.move(source,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}catch(AtomicMoveNotSupportedException e){Files.move(source,target,StandardCopyOption.REPLACE_EXISTING);}}
  private static JSONObject publicMetadata(JSONObject metadata)throws Exception{return new JSONObject().put("code",metadata.getString("code")).put("files",metadata.getJSONArray("files")).put("createdAt",metadata.getLong("createdAt")).put("expiresAt",metadata.getLong("expiresAt"));}
  private void create(Request request,OutputStream output)throws Exception{
    JSONObject input;try{input=new JSONObject(new String(readSmall(request.body,MAX_MANIFEST),StandardCharsets.UTF_8));}catch(HttpError e){throw e;}catch(Exception e){throw new HttpError(400,"Dữ liệu không hợp lệ.");}
    JSONArray files=input.optJSONArray("files");if(files==null||files.length()<1)throw new HttpError(400,"Chọn ít nhất một file.");
    long total=0;JSONArray result=new JSONArray();
    for(int i=0;i<files.length();i++){
      JSONObject f=files.optJSONObject(i);if(f==null)throw new HttpError(400,"File không hợp lệ.");Object rawName=f.opt("name"),rawSize=f.opt("size");
      if(!(rawName instanceof String)||!(rawSize instanceof Number))throw new HttpError(400,"Tên hoặc dung lượng không hợp lệ.");
      String name=(String)rawName;double exact=((Number)rawSize).doubleValue();long size=((Number)rawSize).longValue();
      if(name.trim().isEmpty()||name.length()>255||Pattern.compile("[\\x00-\\x1f\\x7f]").matcher(name).find()||size<0||size>MAX_EXACT_SIZE||exact!=size)throw new HttpError(400,"Tên hoặc dung lượng không hợp lệ.");
      if(size>MAX_EXACT_SIZE-total)throw new HttpError(400,"Dung lượng vượt phạm vi biểu diễn của giao thức.");total+=size;String type=f.optString("type","");if(type.length()>150)type=type.substring(0,150);
      result.put(new JSONObject().put("id",UUID.randomUUID().toString()).put("name",name).put("size",size).put("type",type));
    }
    if(directory.toFile().getUsableSpace()<total+20L*1024*1024)throw new HttpError(507,"Điện thoại không đủ dung lượng trống.");
    if(result.toString().getBytes(StandardCharsets.UTF_8).length>MAX_MANIFEST-4096)throw new HttpError(413,"Danh sách tên file quá dài. Hãy chia thành các lượt nhỏ hơn.");
    String code=null;for(int i=0;i<10;i++){String candidate=code();try{Files.createDirectory(folder(candidate));code=candidate;break;}catch(FileAlreadyExistsException ignored){}}
    if(code==null)throw new HttpError(503,"Chưa tạo được mã. Hãy thử lại.");
    long now=System.currentTimeMillis();String token=UUID.randomUUID().toString()+UUID.randomUUID().toString();
    JSONObject metadata=new JSONObject().put("code",code).put("token",token).put("files",result).put("createdAt",now).put("expiresAt",now+TTL).put("status","uploading");
    synchronized(lock(code)){save(code,metadata);}sendJson(output,201,publicMetadata(metadata).put("token",token));
  }
  private void transfer(Request request,OutputStream output,String code,String action,String id)throws Exception{
    JSONObject metadata=metadata(code);String method=request.method;
    if(metadata.getLong("expiresAt")<=System.currentTimeMillis()){remove(code);throw new HttpError(410,"Mã đã hết hạn. Hãy yêu cầu gửi lại file.");}
    boolean authorized=RequestSecurity.secret(request.headers.get("x-upload-token"),metadata.getString("token"));
    JSONArray files=metadata.getJSONArray("files");
    if(action==null&&"GET".equals(method)){if(!"ready".equals(metadata.getString("status")))throw new HttpError(409,"File đang tải lên. Vui lòng đợi hoàn tất.");sendJson(output,200,publicMetadata(metadata));return;}
    if(action==null&&"DELETE".equals(method)){if(!authorized)throw new HttpError(403,"Không có quyền thu hồi.");remove(code);sendJson(output,200,new JSONObject().put("ok",true));return;}
    if("complete".equals(action)&&"POST".equals(method)){
      if(!authorized)throw new HttpError(403,"Không có quyền hoàn tất.");
      for(int i=0;i<files.length();i++){JSONObject f=files.getJSONObject(i);Path target=file(code,f.getString("id"));if(!Files.exists(target)||Files.size(target)!=f.getLong("size"))throw new HttpError(409,"Có file chưa tải lên hoàn tất.");}
      metadata.put("status","ready");save(code,metadata);sendJson(output,200,publicMetadata(metadata));return;
    }
    if(id!=null){
      JSONObject selected=null;for(int i=0;i<files.length();i++)if(id.equals(files.getJSONObject(i).getString("id")))selected=files.getJSONObject(i);
      if(selected==null)throw new HttpError(404,"Không tìm thấy file.");Path target=file(code,id);long size=selected.getLong("size");
      if("PUT".equals(method)){
        if(!authorized||!"uploading".equals(metadata.getString("status")))throw new HttpError(403,"Không có quyền tải lên.");
        if(request.length>=0&&request.length!=size)throw new HttpError(400,"Dung lượng file không khớp.");
        Path temporary=file(code,id+".upload-"+UUID.randomUUID());long received=0;
        try{
          try(OutputStream disk=Files.newOutputStream(temporary)){byte[] buffer=new byte[65536];int n;while((n=request.body.read(buffer))!=-1){received+=n;if(received>size)throw new HttpError(413,"File vượt quá dung lượng cho phép.");disk.write(buffer,0,n);}}
          if(received!=size)throw new HttpError(400,"File chưa được tải lên đầy đủ.");move(temporary,target);
        }catch(EOFException e){throw new HttpError(400,"Kết nối bị ngắt khi tải file.");}finally{Files.deleteIfExists(temporary);}
        sendJson(output,200,new JSONObject().put("ok",true));return;
      }
      if("GET".equals(method)){
        if(!"ready".equals(metadata.getString("status")))throw new HttpError(409,"File chưa sẵn sàng.");if(!Files.exists(target))throw new HttpError(404,"File không còn khả dụng.");
        String name=selected.getString("name"),ascii=name.replaceAll("[^\\x20-\\x7e]|[\"\\\\]","_");String encoded=URLEncoder.encode(name,"UTF-8").replace("+","%20").replace("*","%2A");
        Map<String,String> headers=new LinkedHashMap<>();headers.put("Content-Disposition","attachment; filename=\""+ascii+"\"; filename*=UTF-8''"+encoded);headers(output,200,"application/octet-stream",size,headers);
        try(InputStream disk=Files.newInputStream(target)){byte[] buffer=new byte[65536];int n;while((n=disk.read(buffer))!=-1)output.write(buffer,0,n);}return;
      }
    }
    throw new HttpError(405,"Phương thức không được hỗ trợ.");
  }
  private void remove(String code)throws IOException{Path folder=folder(code);if(!Files.exists(folder))return;try(DirectoryStream<Path> files=Files.newDirectoryStream(folder)){for(Path file:files)Files.deleteIfExists(file);}Files.deleteIfExists(folder);}
  private void cleanExpired(){try(DirectoryStream<Path> folders=Files.newDirectoryStream(directory)){for(Path folder:folders){String code=folder.getFileName().toString();if(!code.matches("[A-Z2-9]{8}"))continue;synchronized(lock(code)){try{JSONObject meta=metadata(code);if(meta.getLong("expiresAt")<=System.currentTimeMillis())remove(code);}catch(Exception ignored){}}}}catch(IOException ignored){}}
  private static void sendJson(OutputStream output,int status,JSONObject json)throws IOException{sendBytes(output,status,"application/json; charset=utf-8",json.toString().getBytes(StandardCharsets.UTF_8),false);}
  private static void sendBytes(OutputStream output,int status,String type,byte[] bytes,boolean head)throws IOException{headers(output,status,type,bytes.length,Collections.emptyMap());if(!head)output.write(bytes);}
  private static void headers(OutputStream output,int status,String type,long length,Map<String,String> extra)throws IOException{
    StringBuilder header=new StringBuilder("HTTP/1.1 "+status+" "+(status<400?"OK":"Error")+"\r\nContent-Type: "+type+"\r\nContent-Length: "+length+"\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n");
    for(Map.Entry<String,String> item:extra.entrySet())header.append(item.getKey()).append(": ").append(item.getValue()).append("\r\n");header.append("\r\n");output.write(header.toString().getBytes(StandardCharsets.ISO_8859_1));
  }
  @Override public void close(){if(closed)return;closed=true;try{socket.close();}catch(IOException ignored){}for(Socket client:connections)try{client.close();}catch(IOException ignored){}clients.shutdownNow();cleanup.shutdownNow();socketWatch.shutdownNow();activity.clear();statusWorkers.shutdownNow();}
}
