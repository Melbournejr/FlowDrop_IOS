package app.flowdrop.mobile;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.cert.X509Certificate;
import javax.net.ssl.*;

/** Test driver uses only synthetic ephemeral device TLS material, never APK signing keys. */
public final class SecureHostHarness {
 public static void main(String[] args)throws Exception{
  final TransferServer host=new TransferServer(new File(args[0]),null,"Secure JVM phone",0);
  String pem=new String(Files.readAllBytes(Paths.get(args[1])),StandardCharsets.US_ASCII);byte[] keyBytes=java.util.Base64.getDecoder().decode(pem.replaceAll("-----[A-Z ]+-----","").replaceAll("\\s","").trim());PrivateKey key=KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(keyBytes));
  X509Certificate cert=(X509Certificate)java.security.cert.CertificateFactory.getInstance("X.509").generateCertificate(new FileInputStream(args[2]));
  KeyStore store=KeyStore.getInstance("JKS");store.load(null,null);char[] password=new char[0];store.setKeyEntry("temporary-device",key,password,new java.security.cert.Certificate[]{cert});KeyManagerFactory km=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());km.init(store,password);SSLContext context=SSLContext.getInstance("TLS");context.init(km.getKeyManagers(),null,new SecureRandom());
  JSONObject trusted=new JSONObject();DeviceSecurity security=new DeviceSecurity(host.getDeviceId(),"Secure JVM phone",context,cert,new DeviceSecurity.Vault(){public JSONObject trusted(){return trusted;}public void save(){}},url->(HttpURLConnection)url.openConnection());
  host.setConnections(url->security.open(url));
  host.enableSecurity(new TransferServer.SecureAccess(){public ServerSocket socket()throws Exception{return security.serverSocket();}public JSONObject config(int p)throws Exception{return security.config(p);}public boolean legacy(){return security.legacy();}public JSONObject pairing(String r,JSONObject b,String a)throws Exception{return security.pairRoute(r,b,a);}public JSONObject session(java.util.Map<String,String> h)throws Exception{return security.session(h);}public String authorize(String m,String p,java.util.Map<String,String> h)throws Exception{return security.authorize(m,p,h,true);}public void track(String id,java.net.Socket socket){security.track(id,socket);}});
  System.out.println(new JSONObject().put("url",host.getLocalUrl()).put("localToken",host.getUploadCapability()).put("id",host.getDeviceId()));System.out.flush();
  try(BufferedReader in=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))){String line;while((line=in.readLine())!=null){JSONObject answer;try{JSONObject b=new JSONObject(line);String op=b.getString("op");if(op.equals("expireSessions")){java.lang.reflect.Field field=DeviceSecurity.class.getDeclaredField("sessions");field.setAccessible(true);((java.util.Map<?,?>)field.get(security)).clear();answer=new JSONObject().put("ok",true);}else if(op.equals("invalidateRemote")){java.lang.reflect.Field field=DeviceSecurity.class.getDeclaredField("remoteSessions");field.setAccessible(true);for(Object value:((java.util.Map<?,?>)field.get(security)).values())((JSONObject)value).put("token",String.join("",java.util.Collections.nCopies(64,"0")));answer=new JSONObject().put("ok",true);}else if(op.equals("offers"))answer=new JSONObject().put("offers",host.pendingOffers());else if(op.equals("snapshot")){security.refresh();answer=security.snapshot();}else if(op.equals("observe")){security.observe(b.getString("origin"),b.getJSONObject("config"));answer=new JSONObject().put("ok",true);}else if(op.equals("start"))answer=security.start(b.getString("id"));else if(op.equals("confirm")){security.confirm(b.getString("id"),b.optBoolean("accept"));answer=security.snapshot();}else if(op.equals("request")){HttpURLConnection c=security.open(new URL(b.getString("url")));c.setRequestMethod("GET");c.setConnectTimeout(8000);c.setReadTimeout(8000);int status=c.getResponseCode();ByteArrayOutputStream out=new ByteArrayOutputStream();try(InputStream stream=status>=400?c.getErrorStream():c.getInputStream()){byte[] bytes=new byte[8192];int n;while(stream!=null&&(n=stream.read(bytes))!=-1){if(out.size()+n>8*1024*1024)throw new IOException("large");out.write(bytes,0,n);}}finally{c.disconnect();}answer=new JSONObject().put("status",status).put("size",out.size()).put("sha256",DeviceSecurity.hash(out.toByteArray()));}else if(op.equals("answer"))answer=host.answerOffer(b.getString("id"),b.optBoolean("accept"));else if(op.equals("send"))answer=host.offerTo(b.getString("origin"),b.getString("code"));else if(op.equals("forget")){security.forget(b.getString("id"));answer=security.snapshot();}else throw new IOException("unknown op");}catch(Exception e){answer=new JSONObject().put("error",e.getClass().getSimpleName()+": "+e.getMessage());}System.out.println(answer);System.out.flush();}}
  finally{host.close();}
 }
}
