package app.flowdrop.mobile;

import android.content.Context;
import android.net.Network;
import android.net.nsd.*;
import android.net.wifi.WifiManager;
import android.os.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Wi-Fi-bound NSD with bounded resolution, plus the host's independent LAN discovery. */
public final class DeviceDiscovery {
  public interface Listener{void onFound(String id,String name,String url);void onLost(String id);void onError(String message);}
  private final Context context;
  private final NsdManager nsd;
  private final Listener listener;
  private final Handler main=new Handler(Looper.getMainLooper());
  private ExecutorService checks;
  private Network scanNetwork;
  private final LinkedHashMap<String,NsdServiceInfo> services=new LinkedHashMap<>();
  private final ArrayDeque<String> queue=new ArrayDeque<>();
  private final HashMap<String,String> serviceIds=new HashMap<>();
  private final LinkedHashMap<String,Peer> peers=new LinkedHashMap<>();
  private final Set<String> checking=new HashSet<>();
  private NsdManager.DiscoveryListener discovery;
  private NsdManager.ServiceInfoCallback modern;
  private NsdManager.ResolveListener legacy;
  private WifiManager.MulticastLock multicast;
  private boolean active;
  private int epoch,resolution;
  private String resolving;
  private long lastRefresh;
  private static final class Peer{String id,name,url;long verified;Peer(String id,String name,String url){this.id=id;this.name=name;this.url=url;verified=System.currentTimeMillis();}}
  public DeviceDiscovery(Context context,Listener listener){
    this.context=context.getApplicationContext();this.listener=listener;nsd=(NsdManager)context.getSystemService(Context.NSD_SERVICE);
    try{WifiManager wifi=(WifiManager)this.context.getSystemService(Context.WIFI_SERVICE);if(wifi!=null){multicast=wifi.createMulticastLock("flowdrop-device-scan");multicast.setReferenceCounted(false);}}catch(RuntimeException ignored){}
  }
  private String ownId(){HostService host=HostService.current;return host!=null&&host.transfers()!=null?host.transfers().getDeviceId():"";}
  private boolean self(String name){HostService host=HostService.current;return host!=null&&name.equalsIgnoreCase(host.getName());}
  public void start(){if(active)return;active=true;epoch++;checks=Executors.newFixedThreadPool(4,r->{Thread t=new Thread(r,"flowdrop-nsd-check");t.setDaemon(true);return t;});scanNetwork=WifiNetwork.find(context);lastRefresh=System.currentTimeMillis();try{if(multicast!=null)multicast.acquire();}catch(RuntimeException ignored){}startNsd();main.post(tick);}
  private void startNsd(){
    if(!active||nsd==null)return;final int generation=epoch;
    discovery=new NsdManager.DiscoveryListener(){
      public void onDiscoveryStarted(String type){}
      public void onDiscoveryStopped(String type){}
      public void onStartDiscoveryFailed(String type,int error){main.post(()->{if(active&&generation==epoch){try{nsd.stopServiceDiscovery(this);}catch(RuntimeException ignored){}discovery=null;listener.onError("Đang tìm trực tiếp qua Wi-Fi; dịch vụ dò tên chưa sẵn sàng.");}});}
      public void onStopDiscoveryFailed(String type,int error){}
      public void onServiceFound(NsdServiceInfo info){main.post(()->{if(!active||generation!=epoch||!info.getServiceType().contains("_flowdrop._tcp")||self(info.getServiceName()))return;String key=info.getServiceName();if(services.size()>=64&&!services.containsKey(key))return;services.put(key,info);enqueue(key);});}
      public void onServiceLost(NsdServiceInfo info){main.post(()->{if(!active||generation!=epoch)return;String key=info.getServiceName();services.remove(key);serviceIds.remove(key);queue.remove(key);if(key.equals(resolving))finishResolve(resolution);});}
    };
    try{Network wifi=WifiNetwork.find(context);if(Build.VERSION.SDK_INT>=33&&wifi!=null)nsd.discoverServices("_flowdrop._tcp.",NsdManager.PROTOCOL_DNS_SD,wifi,command->main.post(command),discovery);else nsd.discoverServices("_flowdrop._tcp.",NsdManager.PROTOCOL_DNS_SD,discovery);}
    catch(RuntimeException e){discovery=null;listener.onError("Đang dò thiết bị trực tiếp trong Wi-Fi.");}
  }
  private void enqueue(String key){if(!queue.contains(key)&&!key.equals(resolving))queue.add(key);next();}
  private void next(){
    if(!active||resolving!=null||queue.isEmpty()||nsd==null)return;String key=queue.removeFirst();NsdServiceInfo info=services.get(key);if(info==null||self(key)){next();return;}
    resolving=key;final int attempt=++resolution,generation=epoch;
    // A single unresolved/self service must never block every later device.
    main.postDelayed(()->{if(active&&generation==epoch&&attempt==resolution&&resolving!=null)finishResolve(attempt);},4500);
    try{
      if(Build.VERSION.SDK_INT>=34){
        modern=new NsdManager.ServiceInfoCallback(){
          public void onServiceInfoCallbackRegistrationFailed(int code){main.post(()->finishResolve(attempt));}
          public void onServiceUpdated(NsdServiceInfo service){main.post(()->resolved(service,key,generation,attempt));}
          public void onServiceLost(){main.post(()->finishResolve(attempt));}
          public void onServiceInfoCallbackUnregistered(){}
        };nsd.registerServiceInfoCallback(info,command->main.post(command),modern);
      }else{
        legacy=new NsdManager.ResolveListener(){public void onResolveFailed(NsdServiceInfo service,int error){main.post(()->finishResolve(attempt));}public void onServiceResolved(NsdServiceInfo service){main.post(()->resolved(service,key,generation,attempt));}};nsd.resolveService(info,legacy);
      }
    }catch(RuntimeException e){finishResolve(attempt);}
  }
  private void finishResolve(int attempt){
    if(attempt!=resolution)return;
    if(modern!=null&&Build.VERSION.SDK_INT>=34)try{nsd.unregisterServiceInfoCallback(modern);}catch(RuntimeException ignored){}modern=null;
    if(legacy!=null&&Build.VERSION.SDK_INT>=34)try{nsd.stopServiceResolution(legacy);}catch(RuntimeException ignored){}legacy=null;
    resolving=null;resolution++;if(active)main.post(()->next());
  }
  private void resolved(NsdServiceInfo info,String key,int generation,int attempt){
    if(!active||epoch!=generation||resolution!=attempt||!key.equals(resolving))return;
    try{
      byte[] tag=info.getAttributes().get("app");if(tag!=null&&!"flowdrop".equals(new String(tag,java.nio.charset.StandardCharsets.UTF_8))){finishResolve(attempt);return;}
      byte[] identity=info.getAttributes().get("id");if(identity!=null&&ownId().equals(new String(identity,java.nio.charset.StandardCharsets.UTF_8))){finishResolve(attempt);return;}
      List<InetAddress> addresses=new ArrayList<>();if(Build.VERSION.SDK_INT>=34)addresses.addAll(info.getHostAddresses());else if(info.getHost()!=null)addresses.add(info.getHost());
      // Windows can advertise VPN/Ethernet before its reachable Wi-Fi address.
      // Older Android NSD only returns one host, so also accept IPv4 candidates
      // explicitly advertised in TXT, and verify every candidate over Wi-Fi.
      byte[] extra=info.getAttributes().get("ipv4");
      if(extra!=null)for(String ip:new String(extra,java.nio.charset.StandardCharsets.UTF_8).split(","))if(ip.matches("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}"))try{addresses.add(InetAddress.getByName(ip));}catch(Exception ignored){}
      HashSet<String> candidates=new HashSet<>();
      for(InetAddress address:addresses)if(address instanceof Inet4Address&&!address.isLoopbackAddress()&&!address.isAnyLocalAddress()&&info.getPort()>0&&info.getPort()<=65535&&candidates.size()<12)candidates.add("http://"+address.getHostAddress()+":"+info.getPort());
      for(String origin:candidates)probe(origin,key,attempt);
      // Modern callbacks may deliver TXT before IPv4; keep watching until an
      // address update arrives or the resolver's bounded timeout advances us.
      if(Build.VERSION.SDK_INT<34)finishResolve(attempt);
    }catch(Exception ignored){finishResolve(attempt);}
  }
  private void probe(String origin,String service){
    probe(origin,service,-1);
  }
  private void probe(String origin,String service,int attempt){
    if(!active||checking.size()>=16||!checking.add(origin))return;final int generation=epoch;
    checks.submit(()->{try{
      JSONObject config=LanDiscovery.verify(WifiNetwork.open(context,new URL(origin+"/api/config")));String id=config.optString("deviceId");if(!"FlowDrop".equals(config.optString("name"))||id.isEmpty()||id.equals(ownId()))return;
      String name=config.optString("deviceName","Thiết bị");main.post(()->{if(!active||epoch!=generation)return;if(service!=null&&services.containsKey(service))serviceIds.put(service,id);remember(id,name,origin);if(attempt>=0)finishResolve(attempt);});
    }catch(Exception ignored){}finally{main.post(()->{if(epoch==generation)checking.remove(origin);});}});
  }
  private void remember(String id,String name,String origin){
    if(id.equals(ownId()))return;Peer old=peers.get(id);peers.put(id,new Peer(id,name,origin));
    if(old==null||!old.name.equals(name)||!old.url.equals(origin))listener.onFound(id,name,origin.endsWith("/")?origin:origin+"/");
  }
  private final Runnable tick=new Runnable(){public void run(){
    if(!active)return;long now=System.currentTimeMillis();Network wifi=WifiNetwork.find(context);
    if(!java.util.Objects.equals(wifi,scanNetwork)){epoch++;checking.clear();scanNetwork=wifi;finishResolve(resolution);services.clear();queue.clear();if(discovery!=null){try{nsd.stopServiceDiscovery(discovery);}catch(RuntimeException ignored){}}discovery=null;startNsd();HostService host=HostService.current;if(host!=null)host.rescanLan();}
    HostService host=HostService.current;if(host!=null)try{JSONArray lan=host.lanPeers();for(int i=0;i<lan.length();i++){JSONObject peer=lan.getJSONObject(i);remember(peer.getString("id"),peer.getString("name"),peer.getString("url"));}}catch(Exception ignored){}
    for(Peer peer:new ArrayList<>(peers.values())){
      if(now-peer.verified>20000){peers.remove(peer.id);listener.onLost(peer.id);}
      else if(now-peer.verified>8000)probe(peer.url.endsWith("/")?peer.url.substring(0,peer.url.length()-1):peer.url,null);
    }
    if(now-lastRefresh>12000){lastRefresh=now;for(String key:services.keySet())enqueue(key);if(discovery==null)startNsd();}
    main.postDelayed(this,1000);
  }};
  public void stop(){
    active=false;epoch++;main.removeCallbacksAndMessages(null);finishResolve(resolution);services.clear();queue.clear();serviceIds.clear();checking.clear();peers.clear();
    if(discovery!=null){try{nsd.stopServiceDiscovery(discovery);}catch(RuntimeException ignored){}discovery=null;}
    if(multicast!=null&&multicast.isHeld())try{multicast.release();}catch(RuntimeException ignored){}if(checks!=null)checks.shutdownNow();
  }
}
