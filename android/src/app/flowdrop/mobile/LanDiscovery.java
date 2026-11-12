package app.flowdrop.mobile;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** LAN discovery independent of Android's NSD resolver; shared with real UDP JVM tests. */
public final class LanDiscovery implements Closeable {
  public static final int PORT=53317;
  public static final String GROUP="239.255.77.77";
  public interface Adapter {
    List<NetworkInterface> interfaces()throws Exception;
    void bind(DatagramSocket socket)throws Exception;
    HttpURLConnection open(URL url)throws Exception;
  }
  private final String id,platform,version;
  private volatile String name;
  private final int port;
  private final Adapter adapter;
  private final MulticastSocket socket;
  private final Map<String,Peer> peers=new LinkedHashMap<>();
  private final Map<String,Long> attempts=new HashMap<>();
  private final Set<String> pending=new HashSet<>();
  private final Set<String> members=new HashSet<>();
  private final ExecutorService checks=Executors.newFixedThreadPool(2,r->{Thread t=new Thread(r,"flowdrop-lan-check");t.setDaemon(true);return t;});
  private volatile boolean closed=false;
  private volatile boolean query=true;
  private static final class Peer{JSONObject value;long seen,verified;Peer(JSONObject v){value=v;seen=verified=System.currentTimeMillis();}}
  public LanDiscovery(String id,String name,String platform,String version,int port,Adapter adapter)throws Exception{
    this.id=id;this.name=name;this.platform=platform;this.version=version;this.port=port;this.adapter=adapter;
    MulticastSocket created=new MulticastSocket((SocketAddress)null);
    try{created.setReuseAddress(true);created.setBroadcast(true);created.bind(new InetSocketAddress(PORT));adapter.bind(created);created.setTimeToLive(1);created.setSoTimeout(700);socket=created;}
    catch(Exception e){created.close();checks.shutdownNow();throw e;}
    Thread receive=new Thread(()->loop(),"flowdrop-lan");receive.setDaemon(true);receive.start();
  }
  public void rename(String value){name=value;query=true;}
  private byte[] packet(String kind)throws Exception{return new JSONObject().put("app","flowdrop").put("discovery",1).put("kind",kind).put("id",id).put("name",name.length()>100?name.substring(0,100):name).put("platform",platform).put("port",port).put("version",version).toString().getBytes(StandardCharsets.UTF_8);}
  private void send(byte[] bytes,InetAddress address,int targetPort){if(closed)return;try{socket.send(new DatagramPacket(bytes,bytes.length,address,targetPort));}catch(Exception ignored){}}
  private void broadcast(String kind){
    try{byte[] bytes=packet(kind);InetAddress group=InetAddress.getByName(GROUP);Set<InetAddress> broadcasts=new HashSet<>();broadcasts.add(InetAddress.getByName("255.255.255.255"));
      for(NetworkInterface iface:adapter.interfaces()){
        try{if(members.add(iface.getName()))socket.joinGroup(new InetSocketAddress(group,PORT),iface);socket.setNetworkInterface(iface);send(bytes,group,PORT);}catch(Exception ignored){}
        for(InterfaceAddress address:iface.getInterfaceAddresses())if(address.getBroadcast()!=null)broadcasts.add(address.getBroadcast());
      }
      for(InetAddress address:broadcasts)send(bytes,address,PORT);
    }catch(Exception ignored){}
  }
  private void loop(){
    long last=0;byte[] buffer=new byte[1201];
    while(!closed){
      long now=System.currentTimeMillis();if(query||now-last>=3000){broadcast(query?"query":"hello");query=false;last=now;}
      try{DatagramPacket datagram=new DatagramPacket(buffer,buffer.length);socket.receive(datagram);if(datagram.getLength()<=1200)process(new JSONObject(new String(datagram.getData(),datagram.getOffset(),datagram.getLength(),StandardCharsets.UTF_8)),datagram.getAddress(),datagram.getPort());}
      catch(SocketTimeoutException ignored){}catch(Exception ignored){}
      synchronized(this){Iterator<Peer> iterator=peers.values().iterator();while(iterator.hasNext())if(System.currentTimeMillis()-iterator.next().seen>20000)iterator.remove();}
    }
  }
  private void process(JSONObject message,InetAddress address,int senderPort)throws Exception{
    String other=message.optString("id"),kind=message.optString("kind");Object rawPort=message.opt("port");int sourcePort=message.optInt("port");
    if(!(address instanceof Inet4Address)||!"flowdrop".equals(message.optString("app"))||message.optInt("discovery")!=1||!Arrays.asList("query","hello","bye").contains(kind)||!other.matches("[a-zA-Z0-9-]{1,80}")||other.equals(id)||!(rawPort instanceof Number)||sourcePort<1||sourcePort>65535)return;
    String origin="http://"+address.getHostAddress()+":"+sourcePort;long now=System.currentTimeMillis();
    if("query".equals(kind))send(packet("hello"),address,senderPort);
    final String key=other+"@"+origin;
    synchronized(this){Peer old=peers.get(other);
      if("bye".equals(kind)){if(old!=null&&origin.equals(old.value.optString("url")))peers.remove(other);return;}
      if(old!=null&&origin.equals(old.value.optString("url"))){old.seen=now;if(now-old.verified<8000)return;}
      if(pending.contains(key)||now-attempts.getOrDefault(key,0L)<2000||pending.size()>=16)return;
      if(attempts.size()>=128){attempts.entrySet().removeIf(e->now-e.getValue()>20000);if(attempts.size()>=128)return;}
      attempts.put(key,now);pending.add(key);
    }
    checks.submit(()->{
      try{JSONObject config=verify(adapter.open(new URL(origin+"/api/config")));if(!"FlowDrop".equals(config.optString("name"))||!other.equals(config.optString("deviceId"))||id.equals(other))return;
        String label=config.optString("deviceName",message.optString("name","Thiết bị"));if(label.length()>100)label=label.substring(0,100);
        JSONObject peer=new JSONObject().put("id",other).put("name",label).put("platform",config.optString("platform",message.optString("platform"))).put("version",config.optString("version")).put("url",origin).put("address",address.getHostAddress()).put("port",sourcePort);
        synchronized(this){if(!closed)peers.put(other,new Peer(peer));}
      }catch(Exception e){synchronized(this){Peer old=peers.get(other);if(old!=null&&origin.equals(old.value.optString("url"))&&System.currentTimeMillis()-old.verified>16000)peers.remove(other);}}
      finally{synchronized(this){pending.remove(key);}}
    });
  }
  public static JSONObject verify(HttpURLConnection connection)throws Exception{
    connection.setConnectTimeout(2500);connection.setReadTimeout(2500);connection.setInstanceFollowRedirects(false);
    try{if(connection.getResponseCode()!=200)throw new IOException("Không kết nối được FlowDrop.");try(InputStream input=connection.getInputStream();ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
      byte[] buffer=new byte[2048];int n;while((n=input.read(buffer))!=-1){if(bytes.size()+n>32768)throw new IOException("Thông tin thiết bị quá lớn.");bytes.write(buffer,0,n);}return new JSONObject(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
    }}finally{connection.disconnect();}
  }
  public synchronized JSONArray peers()throws Exception{JSONArray result=new JSONArray();for(Peer peer:peers.values())if(System.currentTimeMillis()-peer.seen<20000)result.put(new JSONObject(peer.value.toString()));return result;}
  public void rescan(){query=true;}
  @Override public void close(){if(closed)return;broadcast("bye");closed=true;socket.close();checks.shutdownNow();synchronized(this){peers.clear();}}
}
