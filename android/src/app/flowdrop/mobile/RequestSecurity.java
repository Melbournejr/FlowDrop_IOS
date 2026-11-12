package app.flowdrop.mobile;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
public final class RequestSecurity {
  public static boolean secret(String input,String expected){return input!=null&&expected!=null&&input.length()==expected.length()&&MessageDigest.isEqual(input.getBytes(StandardCharsets.UTF_8),expected.getBytes(StandardCharsets.UTF_8));}
  public static String label(String value,int maximum){String clean=value==null?"":value.replaceAll("[\\x00-\\x1f\\x7f]"," ");return clean.length()>maximum?clean.substring(0,maximum):clean;}
  public static boolean allowedHost(String host,int port){
    try{if(host==null||!host.equals(host.trim()))return false;URI uri=new URI("http://"+host);if(uri.getHost()==null||uri.getRawUserInfo()!=null||uri.getRawQuery()!=null||uri.getRawFragment()!=null||uri.getRawPath()!=null&&!uri.getRawPath().isEmpty()||uri.getPort()!=port)return false;
      String name=uri.getHost().replace("[","").replace("]","");if(name.equals("localhost")||name.equals("127.0.0.1")||name.equals("::1"))return true;
      Enumeration<NetworkInterface> list=NetworkInterface.getNetworkInterfaces();while(list!=null&&list.hasMoreElements()){Enumeration<InetAddress> addresses=list.nextElement().getInetAddresses();while(addresses.hasMoreElements())if(addresses.nextElement().getHostAddress().equals(name))return true;}
    }catch(Exception ignored){}return false;
  }
  public static boolean browserAllowed(Map<String,String> headers){String origin=headers.get("origin"),site=headers.get("sec-fetch-site");return (origin==null||origin.equals("http://"+headers.get("host")))&&(site==null||site.equals("same-origin")||site.equals("none"));}
}
