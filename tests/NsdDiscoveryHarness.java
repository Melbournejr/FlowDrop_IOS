package app.flowdrop.mobile;
import android.content.Context;
import android.net.*;
import android.net.nsd.*;
import android.os.*;
import android.net.wifi.WifiManager;
import java.net.*;
import java.util.*;
import org.json.*;
/** Runs production DeviceDiscovery with deterministic Android API callbacks, not an Android OS emulator. */
public final class NsdDiscoveryHarness {
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 static NsdServiceInfo info(String name,String id,String ip)throws Exception{NsdServiceInfo s=new NsdServiceInfo(name);s.attributes.put("app","flowdrop".getBytes("UTF-8"));s.attributes.put("id",id.getBytes("UTF-8"));s.addresses.add(InetAddress.getByName(ip));Network.ids.put(ip,id);return s;}
 static final class Capture implements DeviceDiscovery.Listener{Map<String,String> found=new HashMap<>();int events;public void onFound(String id,String name,String url){found.put(id,url);events++;}public void onLost(String id){found.remove(id);}public void onError(String text){}}
 static void await(Capture capture,String id)throws Exception{for(int i=0;i<100;i++){Handler.drain();if(capture.found.containsKey(id))return;Thread.sleep(10);}throw new AssertionError("No verified peer "+id);}
 public static void main(String[] args)throws Exception{
  HostService.current=new HostService();Context c=new Context();Capture capture=new Capture();DeviceDiscovery d=new DeviceDiscovery(c,capture);
  HostService.current.peers.put(new JSONObject().put("id","phone-two").put("name","Phone").put("url","http://10.1.1.2:5182"));HostService.current.peers.put(new JSONObject().put("id","windows").put("name","PC").put("url","http://10.1.1.3:45678"));HostService.current.peers.put(new JSONObject().put("id","self").put("name","Me").put("url","http://10.1.1.1:5173"));
  d.start();Handler.drain();check(capture.found.size()==2,"LAN fallback did not display both phone and PC without any NSD callbacks");check(c.nsd.selected==c.connectivity.wifi,"NSD was not bound to Wi-Fi");int events=capture.events;Handler.advance(1000);check(capture.events==events,"Duplicate LAN peers emitted repeatedly");d.stop();check(WifiManager.held==0,"Multicast lock leaked");
  HostService.current.peers=new JSONArray();c=new Context();capture=new Capture();d=new DeviceDiscovery(c,capture);d.start();Handler.drain();
  c.nsd.listener.onServiceFound(info("FlowDrop - self","self","10.2.2.1"));Handler.drain();check(c.nsd.callbacks.isEmpty(),"Own service consumed the resolver");
  NsdServiceInfo hung=info("FlowDrop - hanging","hung","10.2.2.2"),pc=info("FlowDrop - PC","pc","10.2.2.3");c.nsd.listener.onServiceFound(hung);c.nsd.listener.onServiceFound(pc);Handler.drain();check(c.nsd.callbacks.size()==1,"Resolution was not queued");NsdManager.ServiceInfoCallback late=c.nsd.callbacks.get(hung.name);
  Handler.advance(4600);check(c.nsd.callbacks.containsKey(pc.name),"Hung resolve blocked all later devices");late.onServiceUpdated(hung);Handler.drain();check(!capture.found.containsKey("hung"),"Late timeout callback changed device list");NsdManager.ServiceInfoCallback pcCallback=c.nsd.callbacks.get(pc.name);int cancelled=c.nsd.unregistered;pcCallback.onServiceUpdated(new NsdServiceInfo(pc.name));Handler.drain();check(c.nsd.unregistered==cancelled,"TXT-only update cancelled resolution before IPv4 arrived");pcCallback.onServiceUpdated(pc);await(capture,"pc");check(c.connectivity.wifi.opens==1&&c.connectivity.cellular.opens==0,"Device verification went over cellular instead of Wi-Fi");
  NsdManager.DiscoveryListener old=c.nsd.listener;Network previous=c.connectivity.wifi;c.connectivity.wifi=new Network(1);Handler.advance(1000);check(c.nsd.selected==c.connectivity.wifi&&c.nsd.selected!=previous,"Wi-Fi switch did not rebind discovery");int registered=c.nsd.callbacks.size();old.onServiceFound(info("Old network","old","10.2.2.4"));Handler.drain();check(c.nsd.callbacks.size()==registered,"Callback from old Wi-Fi scan was accepted");
  NsdServiceInfo multi=info("FlowDrop - multi","pc-multi","10.8.8.3");multi.addresses.add(0,InetAddress.getByName("10.8.8.99"));c.nsd.listener.onServiceFound(multi);Handler.drain();c.nsd.callbacks.get(multi.name).onServiceUpdated(multi);await(capture,"pc-multi");check(capture.found.get("pc-multi").contains("10.8.8.3"),"Unreachable VPN address hid reachable Wi-Fi address");
  d.stop();int atStop=capture.events;late.onServiceUpdated(hung);Handler.drain();check(capture.events==atStop,"Callback escaped stop");d.start();Handler.drain();NsdServiceInfo phone=info("FlowDrop - phone","phone-new","10.3.3.3");c.nsd.listener.onServiceFound(phone);Handler.drain();c.nsd.callbacks.get(phone.name).onServiceUpdated(phone);await(capture,"phone-new");d.stop();
  Build.VERSION.SDK_INT=29;c=new Context();capture=new Capture();d=new DeviceDiscovery(c,capture);d.start();Handler.drain();c.nsd.listener.onServiceFound(hung);c.nsd.listener.onServiceFound(phone);Handler.drain();Handler.advance(4600);check(c.nsd.legacyCalls==2,"Legacy Android resolution had no timeout");NsdServiceInfo legacyHint=info(phone.name,"phone-new","10.9.9.99");Network.ids.remove("10.9.9.99");legacyHint.attributes.put("ipv4","10.9.9.99,10.3.3.3".getBytes("UTF-8"));c.nsd.legacy.get(phone.name).onServiceResolved(legacyHint);await(capture,"phone-new");d.stop();check(WifiManager.held==0,"Legacy scan leaked multicast lock");
  System.out.println("PASS: production Android discovery uses Wi-Fi, merges LAN fallback without NSD callbacks, excludes self, survives hung resolution and late callbacks, rebinds on Wi-Fi change, restarts safely, probes every advertised IPv4 when a VPN address fails, and uses TXT address hints on Android 10.");
 }
}
