package app.flowdrop.mobile;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.wifi.*;
import android.net.wifi.p2p.*;
import android.os.*;
import org.json.*;
import java.net.*;
import java.util.*;

/** Public Android Wi-Fi Direct API. Only the uniquely named group created here may be removed. */
public final class TurboLink {
  private final Context context;
  private final WifiP2pManager manager;
  private final WifiP2pManager.Channel channel;
  private final Handler main=new Handler(Looper.getMainLooper());
  private final TransferServer host;
  private volatile LanDiscovery discovery;
  private volatile String expected="",interfaceName="",status="LAN · chưa tạo Turbo",mode="auto";
  private volatile String ssid="",passphrase="";
  private volatile boolean creating,stopping,closed;
  private volatile int frequency;
  public TurboLink(Context context,TransferServer host){this.context=context;this.host=host;manager=(WifiP2pManager)context.getSystemService(Context.WIFI_P2P_SERVICE);channel=manager==null?null:manager.initialize(context,Looper.getMainLooper(),()->{status="Turbo mất kết nối API · tiếp tục dùng LAN";});main.post(tick);}
  public JSONObject snapshot()throws Exception{return new JSONObject().put("mode",mode).put("status",status).put("ssid",ssid).put("passphrase",passphrase).put("frequencyMHz",frequency).put("band",frequency>=5000&&frequency<5925?"5 GHz":frequency>=2400&&frequency<2500?"2.4 GHz":"Chưa xác minh").put("owned",!expected.isEmpty()).put("creating",creating);}
  public void mode(String value){if(!Arrays.asList("auto","lan","turbo").contains(value))throw new IllegalArgumentException("Invalid link mode");mode=value;if(value.equals("lan"))stop();}
  public boolean supported(){return manager!=null&&channel!=null&&context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_WIFI_DIRECT);}
  public void start(){
    if(closed||creating||stopping||!expected.isEmpty())return;if(!supported()){status="Máy không có Wi-Fi Direct · dùng LAN";return;}
    String permission=Build.VERSION.SDK_INT>=33?"android.permission.NEARBY_WIFI_DEVICES":"android.permission.ACCESS_FINE_LOCATION";
    if(context.checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED){status="Cần quyền thiết bị Wi-Fi ở gần để bật Turbo";return;}
    creating=true;status="Đang kiểm tra Wi-Fi Direct…";
    try{manager.requestGroupInfo(channel,existing->{if(closed){creating=false;return;}if(existing!=null){creating=false;status="Đã có nhóm Wi-Fi Direct sẵn có. Dừng nhóm trong Cài đặt Wi-Fi rồi thử lại; FlowDrop không tự xóa nhóm chưa xác minh.";return;}
      String suffix=UUID.randomUUID().toString().substring(0,8);String network="DIRECT-fd-FlowDrop-"+suffix;String password=UUID.randomUUID().toString().replace("-","").substring(0,20);WifiManager wifi=(WifiManager)context.getApplicationContext().getSystemService(Context.WIFI_SERVICE);boolean supports5=wifi!=null&&wifi.is5GHzBandSupported();
      try{WifiP2pConfig config=new WifiP2pConfig.Builder().setNetworkName(network).setPassphrase(password).setGroupOperatingBand(supports5?WifiP2pConfig.GROUP_OWNER_BAND_5GHZ:WifiP2pConfig.GROUP_OWNER_BAND_AUTO).build();manager.createGroup(channel,config,new WifiP2pManager.ActionListener(){public void onSuccess(){creating=false;expected=network;ssid=network;passphrase=password;status="Turbo đã tạo · đang xác minh băng tần";if(closed||mode.equals("lan")){stop();return;}inspect();}public void onFailure(int reason){creating=false;status="Không tạo được Turbo (API "+reason+") · dùng LAN; bảo mật TLS giữ nguyên";}});}catch(RuntimeException e){creating=false;status="Hệ điều hành từ chối Turbo · dùng LAN";}
    });}catch(RuntimeException e){creating=false;status="Không mở được Wi-Fi Direct · dùng LAN";}
  }
  private void inspect(){if(closed||stopping||expected.isEmpty())return;try{manager.requestGroupInfo(channel,group->{if(closed||stopping)return;if(group==null){status="Turbo mất kết nối · dùng LAN";releaseDiscovery();expected="";ssid="";passphrase="";interfaceName="";frequency=0;return;}if(!group.isGroupOwner()||!expected.equals(group.getNetworkName())){status="Nhóm Wi-Fi Direct đã đổi · không can thiệp";releaseDiscovery();expected="";return;}
    frequency=group.getFrequency();interfaceName=group.getInterface();status="Wi-Fi Direct · "+(frequency>=5000&&frequency<5925?"5 GHz":frequency>=2400&&frequency<2500?"2.4 GHz":"băng tần chưa xác minh")+" · TLS";
    if(discovery==null&&!interfaceName.isEmpty())try{discovery=new LanDiscovery(host.getDeviceId(),"FlowDrop Turbo","android","1.14.0",host.getPort(),new LanDiscovery.Adapter(){public List<NetworkInterface> interfaces()throws Exception{NetworkInterface iface=NetworkInterface.getByName(interfaceName);return iface==null?Collections.emptyList():Collections.singletonList(iface);}public void bind(DatagramSocket socket){}public HttpURLConnection open(URL url)throws Exception{return (HttpURLConnection)url.openConnection();}});}catch(Exception ignored){status+=" · tìm kiếm dự phòng bằng LAN";}
  });}catch(RuntimeException ignored){status="Không xác minh được Turbo · dùng LAN";}}
  public JSONArray peers()throws Exception{LanDiscovery active=discovery;return active==null?new JSONArray():active.peers();}
  public boolean routes(String hostName){try{if(expected.isEmpty()||interfaceName.isEmpty()||!hostName.matches("[0-9.]+"))return false;NetworkInterface iface=NetworkInterface.getByName(interfaceName);if(iface==null)return false;byte[] target=InetAddress.getByName(hostName).getAddress();for(InterfaceAddress local:iface.getInterfaceAddresses()){byte[] address=local.getAddress().getAddress();if(address.length!=4||target.length!=4)continue;int bits=local.getNetworkPrefixLength();if(bits<8||bits>30)continue;boolean same=true;for(int i=0;i<4;i++){int n=Math.min(8,Math.max(0,bits-i*8)),mask=(255<<(8-n))&255;if((address[i]&mask)!=(target[i]&mask))same=false;}if(same)return true;}}catch(Exception ignored){}return false;}
  // Keep the owned link alive across completed/failed transfers until explicit stop.
  private final Runnable tick=new Runnable(){public void run(){if(closed)return;inspect();main.postDelayed(this,3000);}};
  private void releaseDiscovery(){if(discovery!=null){discovery.close();discovery=null;}}
  private void clearOwned(){expected="";ssid="";passphrase="";interfaceName="";frequency=0;}
  public void stop(){
    releaseDiscovery();final String owned=expected,ownedPass=passphrase;if(owned.isEmpty()||manager==null||stopping)return;stopping=true;
    try{manager.requestGroupInfo(channel,group->{
      if(group==null||!group.isGroupOwner()||!owned.equals(group.getNetworkName())||!ownedPass.equals(group.getPassphrase())){if(owned.equals(expected))clearOwned();stopping=false;return;}
      try{manager.removeGroup(channel,new WifiP2pManager.ActionListener(){public void onSuccess(){if(owned.equals(expected))clearOwned();stopping=false;status="Đã dừng Turbo do FlowDrop tạo · LAN";}public void onFailure(int reason){stopping=false;status="Chưa dừng được Turbo (API "+reason+"). Mạng vẫn được giữ; bấm Dừng Turbo để thử lại.";}});}catch(RuntimeException error){stopping=false;status="Chưa dừng được Turbo. Kiểm tra Wi-Fi Direct rồi thử lại.";}
    });}catch(RuntimeException error){stopping=false;status="Chưa dừng được Turbo. Kiểm tra Wi-Fi Direct rồi thử lại.";}
  }
  public void close(){closed=true;main.removeCallbacks(tick);stop();}
}
