package app.flowdrop.mobile;
import java.util.concurrent.CopyOnWriteArrayList;
import java.net.*;
import java.io.*;
import java.security.MessageDigest;
import org.json.*;
/** Calls the production Java resolver while the first LAN candidate arrives later. */
public final class CodeLookupLateHarness {
 public static void main(String[] args)throws Exception{
  CopyOnWriteArrayList<String> peers=new CopyOnWriteArrayList<>();
  Thread discovery=new Thread(()->{try{Thread.sleep(250);peers.add(args[0]);}catch(InterruptedException e){Thread.currentThread().interrupt();}});discovery.start();
  long start=System.nanoTime();CodeLookup.Found found=CodeLookup.find(args[1],peers,null,url->(HttpURLConnection)url.openConnection());
  JSONArray files=found.metadata.getJSONArray("files"),hashes=new JSONArray();
  for(int i=0;i<files.length();i++){JSONObject f=files.getJSONObject(i);HttpURLConnection c=(HttpURLConnection)new URL(found.origin+"api/transfers/"+found.metadata.getString("code")+"/files/"+f.getString("id")).openConnection();c.setConnectTimeout(3000);c.setReadTimeout(10000);MessageDigest digest=MessageDigest.getInstance("SHA-256");long size=0;try(InputStream in=c.getInputStream()){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){digest.update(b,0,n);size+=n;}}finally{c.disconnect();}if(size!=f.getLong("size"))throw new AssertionError("Truncated code download");StringBuilder hex=new StringBuilder();for(byte b:digest.digest())hex.append(String.format("%02x",b&255));hashes.put(new JSONObject().put("size",size).put("sha256",hex.toString()));}
  discovery.join();System.out.println(new JSONObject().put("passed",true).put("files",hashes).put("elapsedMs",(System.nanoTime()-start)/1000000));
 }
}
