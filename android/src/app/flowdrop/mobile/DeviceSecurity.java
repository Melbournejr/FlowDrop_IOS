package app.flowdrop.mobile;

import org.json.*;
import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.*;
import java.security.interfaces.RSAPublicKey;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Standard TLS + explicit two-screen commit/reveal pairing, independent of APK signing. */
public final class DeviceSecurity {
  public interface Vault {JSONObject trusted();void save()throws Exception;default String diagnostic(){return "portable vault";}}
  public String diagnostic(){return vault.diagnostic();}
  public interface Connections {HttpURLConnection open(URL url)throws Exception;}
  private final String id,name,certificate,fingerprint;
  private final SSLContext serverContext;
  private final Vault vault;
  private final Connections raw;
  private final SecureRandom random=new SecureRandom();
  private final Map<String,JSONObject> candidates=new LinkedHashMap<>(),pairs=new LinkedHashMap<>(),sessions=new LinkedHashMap<>(),remoteSessions=new HashMap<>(),attempts=new LinkedHashMap<>();
  private final Map<String,Long> nonces=new LinkedHashMap<>();
  private volatile boolean legacy=false;
  private volatile int listenPort;
  private final Map<String,JSONObject> proposals=new LinkedHashMap<>();
  private final Map<java.net.Socket,String> activeSockets=new java.util.concurrent.ConcurrentHashMap<>();
  private final Map<HttpURLConnection,String> activeRequests=new java.util.concurrent.ConcurrentHashMap<>();
  public void track(String peerId,java.net.Socket socket){activeSockets.keySet().removeIf(java.net.Socket::isClosed);activeSockets.put(socket,peerId);}
  public DeviceSecurity(String id,String name,SSLContext serverContext,X509Certificate cert,Vault vault,Connections raw)throws Exception{
    this.id=id;this.name=name;this.serverContext=serverContext;this.vault=vault;this.raw=raw;certificate=Base64.getEncoder().encodeToString(cert.getEncoded());fingerprint=hash(cert.getEncoded());validateCertificate(certificate,id);
  }
  public SSLServerSocket serverSocket()throws Exception{SSLServerSocket socket=(SSLServerSocket)serverContext.getServerSocketFactory().createServerSocket(0,32);ArrayList<String> supported=new ArrayList<>();for(String p:socket.getSupportedProtocols())if(p.equals("TLSv1.2")||p.equals("TLSv1.3"))supported.add(p);socket.setEnabledProtocols(supported.toArray(new String[0]));return socket;}
  public void legacy(boolean value){legacy=value;}
  public boolean legacy(){return legacy;}
  public static String hash(byte[] bytes)throws Exception{StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
  private static String hash(String value)throws Exception{return hash(value.getBytes(StandardCharsets.UTF_8));}
  public static String identityName(String id)throws Exception{return "flowdrop-"+hash(id).substring(0,24)+".local";}
  private String random(){byte[] b=new byte[32];random.nextBytes(b);StringBuilder s=new StringBuilder();for(byte x:b)s.append(String.format(Locale.ROOT,"%02x",x&255));return s.toString();}
  private static boolean hex(String value){return value!=null&&value.matches("[a-f0-9]{64}");}
  private static X509Certificate validateCertificate(String encoded,String id)throws Exception{
    if(id==null||!id.matches("[a-zA-Z0-9-]{1,100}")||encoded.length()>12000)throw new IOException("Danh tính TLS không hợp lệ.");
    X509Certificate cert=(X509Certificate)CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(Base64.getDecoder().decode(encoded)));cert.checkValidity();cert.verify(cert.getPublicKey());
    if(!(cert.getPublicKey() instanceof RSAPublicKey)||((RSAPublicKey)cert.getPublicKey()).getModulus().bitLength()<2048||!cert.getSubjectX500Principal().equals(cert.getIssuerX500Principal())||!cert.getSubjectX500Principal().getName().equalsIgnoreCase("CN="+identityName(id)))throw new CertificateException("Danh tính TLS không hợp lệ.");return cert;
  }
  public synchronized JSONObject config(int port)throws Exception{listenPort=port;return new JSONObject().put("protocol",2).put("port",port).put("certificate",certificate).put("fingerprint",fingerprint);}
  public synchronized JSONObject candidate(String peerId,String origin,String encoded,String peerName)throws Exception{
    X509Certificate cert=validateCertificate(encoded,peerId);String fp=hash(cert.getEncoded());JSONObject trust=vault.trusted().optJSONObject(peerId);
    if(peerId.equals(id)||!new URI(origin).getScheme().equals("https"))throw new IOException("Thiết bị không hợp lệ.");
    if(trust!=null&&!RequestSecurity.secret(fp,trust.getString("fingerprint")))throw new IOException("Danh tính thiết bị đã đổi. Xóa ghép nối cũ sau khi kiểm tra.");
    JSONObject p=new JSONObject().put("id",peerId).put("origin",origin).put("certificate",encoded).put("fingerprint",fp).put("name",RequestSecurity.label(peerName,100));
    if(candidates.size()>=128&&!candidates.containsKey(peerId))candidates.remove(candidates.keySet().iterator().next());candidates.put(peerId,p);return p;
  }
  public synchronized void observe(String origin,JSONObject config)throws Exception{
    if(!config.has("secure"))return;JSONObject s=config.getJSONObject("secure");URI old=new URI(origin);candidate(config.getString("deviceId"),"https://"+old.getHost()+":"+s.getInt("port"),s.getString("certificate"),config.optString("deviceName","Thiết bị")).put("bootstrap",origin);
  }
  private synchronized JSONObject peer(URL url)throws Exception{for(JSONObject p:candidates.values())if(new URL(p.getString("origin")).getHost().equals(url.getHost())&&(url.getProtocol().equals("http")&&p.optString("bootstrap").equals("http://"+url.getAuthority())||url.getProtocol().equals("https")&&new URL(p.getString("origin")).getPort()==url.getPort()))return p;return null;}
  private static String transcript(JSONObject a,JSONObject b)throws Exception{return new JSONArray().put("FlowDropPair1").put(a.getString("id")).put(a.getString("fingerprint")).put(b.getString("id")).put(b.getString("fingerprint")).toString();}
  private static String commit(String transcript,String nonce)throws Exception{return hash(new JSONArray().put(transcript).put(nonce).toString());}
  private static String sas(String transcript,String a,String b)throws Exception{return String.format(Locale.ROOT,"%06d",Long.parseLong(hash(new JSONArray().put(transcript).put(a).put(b).toString()).substring(0,8),16)%1000000);}
  private JSONObject own()throws Exception{return new JSONObject().put("id",id).put("fingerprint",fingerprint);}
  private synchronized void prune(){long now=System.currentTimeMillis();pairs.values().removeIf(p->p.optLong("until")<now);sessions.values().removeIf(p->p.optLong("until")<now);attempts.values().removeIf(p->p.optLong("until")<now);nonces.values().removeIf(t->t<now);proposals.values().removeIf(p->p.optLong("until")<now);}
  public synchronized JSONObject snapshot()throws Exception{prune();JSONArray trusted=new JSONArray(),pending=new JSONArray();for(Iterator<String> keys=vault.trusted().keys();keys.hasNext();){String key=keys.next();JSONObject t=vault.trusted().getJSONObject(key);trusted.put(new JSONObject().put("id",key).put("name",t.optString("name")).put("fingerprint",t.optString("fingerprint")));}for(Map.Entry<String,JSONObject> row:pairs.entrySet()){JSONObject p=row.getValue();pending.put(new JSONObject().put("id",row.getKey()).put("name",p.getJSONObject("peer").optString("name")).put("code",p.optString("code")).put("direction",p.optString("direction")).put("confirmed",p.optBoolean("local")).put("complete",p.optBoolean("complete")));}return new JSONObject().put("fingerprint",fingerprint).put("legacy",legacy).put("trusted",trusted).put("pairings",pending);}
  public synchronized void forget(String peerId)throws Exception{vault.trusted().remove(peerId);for(Map.Entry<java.net.Socket,String> entry:activeSockets.entrySet())if(entry.getValue().equals(peerId)){try{entry.getKey().close();}catch(IOException ignored){}activeSockets.remove(entry.getKey());}for(Map.Entry<HttpURLConnection,String> entry:activeRequests.entrySet())if(entry.getValue().equals(peerId)){entry.getKey().disconnect();activeRequests.remove(entry.getKey());}sessions.values().removeIf(p->p.optString("id").equals(peerId));remoteSessions.remove(peerId);pairs.values().removeIf(p->p.optJSONObject("peer").optString("id").equals(peerId));vault.save();}
  public JSONObject start(String peerId)throws Exception{
    JSONObject p; synchronized(this){prune();p=candidates.get(peerId);}if(p==null)throw new IOException("Tìm lại thiết bị trước khi ghép nối.");String nonce=random(),transcript=transcript(own(),p);
    synchronized(this){proposals.put(commit(transcript,nonce),new JSONObject().put("until",System.currentTimeMillis()+120000).put("fingerprint",p.getString("fingerprint")));}
    JSONObject r=json(p,"/api/secure/pair/start",new JSONObject().put("id",id).put("name",name).put("certificate",certificate).put("tlsPort",listenPort).put("commit",commit(transcript,nonce)),false,null);
    if(!hex(r.optString("id"))||!hex(r.optString("commit")))throw new IOException("Ghép nối không hợp lệ.");JSONObject reveal=json(p,"/api/secure/pair/reveal",new JSONObject().put("id",r.getString("id")).put("nonce",nonce),false,null);
    if(!hex(reveal.optString("nonce"))||!RequestSecurity.secret(commit(transcript,reveal.getString("nonce")),r.getString("commit")))throw new IOException("Cam kết ghép nối không khớp.");
    synchronized(this){pairs.put(r.getString("id"),new JSONObject().put("peer",p).put("nonce",nonce).put("transcript",transcript).put("code",sas(transcript,nonce,reveal.getString("nonce"))).put("until",System.currentTimeMillis()+120000).put("direction","outgoing"));return snapshot();}
  }
  public void confirm(String pairId,boolean accept)throws Exception{synchronized(this){prune();JSONObject p=pairs.get(pairId);if(p==null||p.optString("code").isEmpty())throw new IOException("Ghép nối đã hết hạn.");if(!accept){pairs.remove(pairId);return;}p.put("local",true);}refresh();}
  public void refresh()throws Exception{List<Map.Entry<String,JSONObject>> todo;synchronized(this){prune();todo=new ArrayList<>(pairs.entrySet());}for(Map.Entry<String,JSONObject> row:todo){JSONObject p=row.getValue();synchronized(this){if(!p.optString("direction").equals("outgoing")||!p.optBoolean("local")||p.optBoolean("complete")||p.optBoolean("polling"))continue;p.put("polling",true);}try{JSONObject reply=json(p.getJSONObject("peer"),"/api/secure/pair/status",new JSONObject().put("id",row.getKey()).put("nonce",p.getString("nonce")).put("confirmed",true),false,null);if(reply.optBoolean("confirmed")&&hex(reply.optString("secret"))){synchronized(this){JSONObject trust=new JSONObject(p.getJSONObject("peer").toString()).put("secret",reply.getString("secret"));vault.trusted().put(trust.getString("id"),trust);vault.save();p.put("complete",true);}}}finally{synchronized(this){p.put("polling",false);}}}}
  public synchronized JSONObject pairRoute(String route,JSONObject body,String address)throws Exception{
    prune();if(route.endsWith("/prove")){JSONObject proposal=proposals.get(body.optString("commit"));if(proposal==null||!RequestSecurity.secret(proposal.optString("fingerprint"),body.optString("targetFingerprint")))throw new IOException("Không có đề nghị ghép nối tương ứng.");return new JSONObject().put("commit",body.getString("commit"));}if(route.endsWith("/start")){JSONObject n=attempts.get(address);if(n==null)n=new JSONObject().put("until",System.currentTimeMillis()+300000).put("count",0);n.put("count",n.getInt("count")+1);if(n.getInt("count")>3||pairs.size()>=20||attempts.size()>=512)throw new IOException("Quá nhiều lần ghép nối. Chờ 5 phút.");attempts.put(address,n);
      String peerId=body.getString("id"),encoded=body.getString("certificate");X509Certificate cert=validateCertificate(encoded,peerId);if(peerId.equals(id)||!hex(body.optString("commit")))throw new IOException("Ghép nối không hợp lệ.");JSONObject peer=new JSONObject().put("id",peerId).put("name",RequestSecurity.label(body.optString("name","Thiết bị"),100)).put("certificate",encoded).put("fingerprint",hash(cert.getEncoded()));JSONObject old=vault.trusted().optJSONObject(peerId);if(old!=null)throw new IOException("Thiết bị đã tin cậy. Xóa ghép nối cũ trên cả hai máy trước khi ghép lại.");
      int tlsPort=body.optInt("tlsPort");if(tlsPort<1||tlsPort>65535||!address.matches("[0-9.]+"))throw new IOException("Cổng TLS không hợp lệ.");peer.put("origin","https://"+address+":"+tlsPort);JSONObject proof=json(peer,"/api/secure/pair/prove",new JSONObject().put("commit",body.getString("commit")).put("targetFingerprint",fingerprint),false,null);if(!RequestSecurity.secret(proof.optString("commit"),body.getString("commit")))throw new IOException("Không chứng minh được danh tính thiết bị gửi.");
      String pairId=random(),nonce=random(),transcript=transcript(peer,own());pairs.put(pairId,new JSONObject().put("peer",peer).put("nonce",nonce).put("transcript",transcript).put("commit",body.getString("commit")).put("direction","incoming").put("until",System.currentTimeMillis()+120000));return new JSONObject().put("id",pairId).put("commit",commit(transcript,nonce));
    }
    JSONObject p=pairs.get(body.optString("id"));if(p==null||!p.optString("direction").equals("incoming")||!hex(body.optString("nonce"))||!RequestSecurity.secret(commit(p.getString("transcript"),body.getString("nonce")),p.getString("commit")))throw new IOException("Ghép nối đã hết hạn hoặc không hợp lệ.");
    if(route.endsWith("/reveal")){p.put("remoteNonce",body.getString("nonce")).put("code",sas(p.getString("transcript"),body.getString("nonce"),p.getString("nonce")));return new JSONObject().put("nonce",p.getString("nonce"));}
    if(!route.endsWith("/status")||!p.has("code")||!RequestSecurity.secret(p.optString("remoteNonce"),body.getString("nonce")))throw new IOException("Ghép nối không hợp lệ.");
    if(p.optBoolean("local")&&body.optBoolean("confirmed")){if(!p.has("secret"))p.put("secret",random());JSONObject trust=new JSONObject(p.getJSONObject("peer").toString()).put("secret",p.getString("secret"));vault.trusted().put(trust.getString("id"),trust);vault.save();p.put("complete",true);return new JSONObject().put("confirmed",true).put("secret",p.getString("secret"));}return new JSONObject().put("confirmed",false);
  }
  private static String signature(String secret,String method,String route,String time,String nonce,String token)throws Exception{byte[] key=new byte[32];for(int i=0;i<32;i++)key[i]=(byte)Integer.parseInt(secret.substring(i*2,i*2+2),16);Mac m=Mac.getInstance("HmacSHA256");m.init(new SecretKeySpec(key,"HmacSHA256"));String value=new JSONArray().put("FlowDropRequest1").put(method).put(route).put(time).put(nonce).put(token).toString();StringBuilder out=new StringBuilder();for(byte b:m.doFinal(value.getBytes(StandardCharsets.UTF_8)))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
  private synchronized Map<String,String> headers(String peerId,String method,String route,String token)throws Exception{JSONObject t=vault.trusted().optJSONObject(peerId);if(t==null)throw new IOException("Ghép nối thiết bị trước khi gửi hoặc nhận mã.");String time=Long.toString(System.currentTimeMillis()),nonce=random();Map<String,String> h=new HashMap<>();h.put("x-fd-id",id);h.put("x-fd-time",time);h.put("x-fd-nonce",nonce);h.put("x-fd-session",token);h.put("x-fd-mac",signature(t.getString("secret"),method,route,time,nonce,token));return h;}
  public synchronized String authorize(String method,String route,Map<String,String> h,boolean session)throws Exception{prune();String peerId=h.get("x-fd-id"),time=h.get("x-fd-time"),nonce=h.get("x-fd-nonce"),token=h.getOrDefault("x-fd-session","");JSONObject trust=vault.trusted().optJSONObject(peerId==null?"":peerId);
    if(trust==null||time==null||!time.matches("[0-9]{13}")||Math.abs(System.currentTimeMillis()-Long.parseLong(time))>120000||!hex(nonce)||nonces.containsKey(peerId+nonce)||!RequestSecurity.secret(h.get("x-fd-mac"),signature(trust.getString("secret"),method,route,time,nonce,token)))throw new IOException("Không có quyền truy cập thiết bị.");
    if(session&&(!sessions.containsKey(token)||!sessions.get(token).optString("id").equals(peerId)))throw new IOException("Phiên bảo mật đã hết hạn.");if(nonces.size()>=4096)throw new IOException("Có quá nhiều yêu cầu bảo mật.");nonces.put(peerId+nonce,System.currentTimeMillis()+240000);return peerId;
  }
  public synchronized JSONObject session(Map<String,String> h)throws Exception{String peerId=authorize("POST","/api/secure/session",h,false);if(sessions.size()>=512)throw new IOException("Có quá nhiều phiên.");String token=random();long until=System.currentTimeMillis()+600000;sessions.put(token,new JSONObject().put("id",peerId).put("until",until));return new JSONObject().put("token",token).put("until",until);}
  private HttpsURLConnection tls(JSONObject peer,String route)throws Exception{
    URL url=new URL(peer.getString("origin")+route);if(!url.getProtocol().equals("https")||!url.getHost().equals(new URL(peer.getString("origin")).getHost()))throw new IOException("Địa chỉ TLS không hợp lệ.");
    final X509Certificate pinned=validateCertificate(peer.getString("certificate"),peer.getString("id"));final String expected=peer.getString("fingerprint");
    X509TrustManager manager=new X509TrustManager(){public X509Certificate[] getAcceptedIssuers(){return new X509Certificate[]{pinned};}public void checkClientTrusted(X509Certificate[] chain,String auth)throws CertificateException{throw new CertificateException("Client certificate not used");}public void checkServerTrusted(X509Certificate[] chain,String auth)throws CertificateException{try{if(chain.length!=1)throw new CertificateException("Invalid chain");chain[0].checkValidity();chain[0].verify(chain[0].getPublicKey());if(!RequestSecurity.secret(hash(chain[0].getEncoded()),expected))throw new CertificateException("TLS pin mismatch");}catch(Exception e){throw new CertificateException("Không xác minh được danh tính TLS.",e);}}};
    SSLContext context=SSLContext.getInstance("TLS");context.init(null,new TrustManager[]{manager},random);HttpsURLConnection c=(HttpsURLConnection)raw.open(url);c.setSSLSocketFactory(context.getSocketFactory());c.setHostnameVerifier((host,session)->{try{X509Certificate cert=(X509Certificate)session.getPeerCertificates()[0];return host.equals(url.getHost())&&RequestSecurity.secret(hash(cert.getEncoded()),expected)&&cert.getSubjectX500Principal().equals(pinned.getSubjectX500Principal());}catch(Exception e){return false;}});c.setInstanceFollowRedirects(false);return c;
  }
  private JSONObject json(JSONObject peer,String route,JSONObject body,boolean authenticated,Map<String,String> supplied)throws Exception{
    HttpURLConnection c=tls(peer,route);c.setConnectTimeout(8000);c.setReadTimeout(8000);String method=body==null?"GET":"POST";c.setRequestMethod(method);Map<String,String> h=supplied;if(authenticated)h=authHeaders(peer,method,route);if(h!=null)for(Map.Entry<String,String> e:h.entrySet())c.setRequestProperty(e.getKey(),e.getValue());if(body!=null){byte[] b=body.toString().getBytes(StandardCharsets.UTF_8);c.setDoOutput(true);c.setFixedLengthStreamingMode(b.length);c.setRequestProperty("Content-Type","application/json");try(OutputStream out=c.getOutputStream()){out.write(b);}}try{int status=c.getResponseCode();InputStream stream=status<400?c.getInputStream():c.getErrorStream();try(InputStream in=stream;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while(in!=null&&(n=in.read(b))!=-1){if(out.size()+n>8*1024*1024)throw new IOException("Phản hồi quá lớn.");out.write(b,0,n);}JSONObject result=new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));if(status>=400)throw new IOException(result.optString("error","Thiết bị từ chối yêu cầu."));return result;}}finally{c.disconnect();}
  }
  private Map<String,String> authHeaders(JSONObject peer,String method,String route)throws Exception{String peerId=peer.getString("id");JSONObject s; synchronized(this){s=remoteSessions.get(peerId);}if(s==null||s.optLong("until")<System.currentTimeMillis()+30000){s=json(peer,"/api/secure/session",new JSONObject(),false,headers(peerId,"POST","/api/secure/session",""));if(!hex(s.optString("token"))||s.optLong("until")>System.currentTimeMillis()+660000)throw new IOException("Phiên bảo mật không hợp lệ.");synchronized(this){remoteSessions.put(peerId,s);}}return headers(peerId,method,route,s.getString("token"));}
  public HttpURLConnection open(URL url)throws Exception{
    // Explicit user-selected, warned 1.13 mode. Never entered on a TLS failure.
    if(legacy&&url.getProtocol().equals("http"))return raw.open(url);
    if(url.getProtocol().equals("http")&&(url.getHost().equals("127.0.0.1")||url.getHost().equals("localhost")||url.getHost().equals("::1")))return raw.open(url);
    if(url.getProtocol().equals("http")&&url.getPath().equals("/api/config"))return raw.open(url);
    JSONObject p=peer(url);if(p==null&&url.getProtocol().equals("http")){HttpURLConnection c=raw.open(new URL("http://"+url.getAuthority()+"/api/config"));c.setConnectTimeout(2000);c.setReadTimeout(3000);c.setInstanceFollowRedirects(false);try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){if(out.size()+n>32768)throw new IOException("Phản hồi quá lớn.");out.write(b,0,n);}observe("http://"+url.getAuthority(),new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8)));}finally{c.disconnect();}p=peer(url);}
    if(p==null){if(legacy&&url.getProtocol().equals("http"))return raw.open(url);throw new IOException("Thiết bị cũ: cần cập nhật hoặc bật tương thích có cảnh báo.");}
    final JSONObject chosen=p;
    // HttpURLConnection callers select POST after open. A wrapper recomputes authentication before connect.
    return new SecureConnection(tls(chosen,url.getFile()),chosen,url.getFile(),null);
  }
  private final class SecureConnection extends HttpURLConnection {
    final HttpURLConnection delegate;final JSONObject peer;final String route;boolean prepared;
    SecureConnection(HttpURLConnection delegate,JSONObject peer,String route,Map<String,String> ignored){super(delegate.getURL());this.delegate=delegate;this.peer=peer;this.route=route;}
    private void prepare()throws IOException{if(prepared)return;try{delegate.setRequestMethod(method);for(Map.Entry<String,String> e:authHeaders(peer,method,route).entrySet())delegate.setRequestProperty(e.getKey(),e.getValue());delegate.setConnectTimeout(getConnectTimeout());delegate.setReadTimeout(getReadTimeout());delegate.setInstanceFollowRedirects(false);delegate.setDoOutput(getDoOutput());activeRequests.put(delegate,peer.getString("id"));prepared=true;}catch(Exception e){throw new IOException(e.getMessage(),e);}}
    public void connect()throws IOException{prepare();delegate.connect();}public void disconnect(){activeRequests.remove(delegate);delegate.disconnect();}public boolean usingProxy(){return delegate.usingProxy();}
    public void setRequestProperty(String k,String v){if(k.toLowerCase(Locale.ROOT).startsWith("x-fd-"))throw new IllegalArgumentException("Reserved authentication header");delegate.setRequestProperty(k,v);}
    public void setFixedLengthStreamingMode(long n){delegate.setFixedLengthStreamingMode(n);}public void setFixedLengthStreamingMode(int n){delegate.setFixedLengthStreamingMode(n);}public void setChunkedStreamingMode(int n){delegate.setChunkedStreamingMode(n);}
    public InputStream getInputStream()throws IOException{prepare();return delegate.getInputStream();}public OutputStream getOutputStream()throws IOException{prepare();return delegate.getOutputStream();}public int getResponseCode()throws IOException{prepare();return delegate.getResponseCode();}public InputStream getErrorStream(){return delegate.getErrorStream();}public String getHeaderField(String name){try{prepare();}catch(IOException e){return null;}return delegate.getHeaderField(name);}public long getContentLengthLong(){try{prepare();}catch(IOException e){return -1;}return delegate.getContentLengthLong();}
  }
}
