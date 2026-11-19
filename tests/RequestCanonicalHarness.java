package app.flowdrop.mobile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/** Public synthetic vectors only; no device vault, network or real credentials. */
public final class RequestCanonicalHarness {
 public static void main(String[] args)throws Exception{
  java.lang.reflect.Method method=DeviceSecurity.class.getDeclaredMethod("signature",String.class,String.class,String.class,String.class,String.class,String.class);method.setAccessible(true);
  try(BufferedReader in=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))){
   for(String line;(line=in.readLine())!=null;){JSONObject v=new JSONObject(line);
    System.out.println(method.invoke(null,v.getString("secret"),v.getString("method"),v.getString("route"),v.getString("time"),v.getString("nonce"),v.getString("token")));
   }
  }
 }
}
