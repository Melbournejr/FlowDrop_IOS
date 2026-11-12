package app.flowdrop.mobile;
import java.io.*;
import java.net.*;
import java.util.*;
import org.json.*;
public final class LanHostHarness {
 public static void main(String[] args)throws Exception{
  TransferServer host=new TransferServer(new File(args[0]),null,"Điện thoại cùng tên",0);
  LanDiscovery.Adapter adapter=new LanDiscovery.Adapter(){
   public List<NetworkInterface> interfaces()throws Exception{return Collections.singletonList(NetworkInterface.getByInetAddress(InetAddress.getByName(args[1])));}
   public void bind(DatagramSocket socket){}
   public HttpURLConnection open(URL url)throws Exception{return (HttpURLConnection)url.openConnection();}
  };
  String displayName="Điện thoại cùng tên";
  LanDiscovery lan=new LanDiscovery(host.getDeviceId(),"Điện thoại cùng tên","android","1.9.0",host.getPort(),adapter);
  System.out.println(new JSONObject().put("id",host.getDeviceId()).put("url",host.getLocalUrl()).put("localToken",host.getUploadCapability()));System.out.flush();
  BufferedReader input=new BufferedReader(new InputStreamReader(System.in,"UTF-8"));String line;
  while((line=input.readLine())!=null)try{JSONObject command=new JSONObject(line),result=new JSONObject();switch(command.getString("action")){
   case "peers":result.put("peers",lan.peers());break;
   case "stop":lan.close();break;
   case "start":lan=new LanDiscovery(host.getDeviceId(),"Điện thoại cùng tên","android","1.9.0",host.getPort(),adapter);break;
   case "rename":displayName=DeviceLabel.validate(command.getString("name"));host.setDeviceName(displayName);lan.rename(displayName);break;
   case "rescan":lan.rescan();break;
  }System.out.println(result);System.out.flush();}catch(Exception e){System.out.println(new JSONObject().put("error",e.toString()));System.out.flush();}
  lan.close();host.close();
 }
}
