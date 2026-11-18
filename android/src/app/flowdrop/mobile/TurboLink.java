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
  private volatile WifiP2pManager.Channel channel;
  private final Handler main=new Handler(Looper.getMainLooper());
  private final TransferServer host;
  private volatile LanDiscovery discovery;
  private volatile String expected="",interfaceName="",status="LAN · chưa tạo Turbo",mode="auto";
  private volatile String ssid="",passphrase="";
  private volatile boolean creating,stopping,closed,ready,blocked,polling;
  private final LinkDiagnostics trace;
  private int generation,queryEpoch,channelEpoch,recoveries,channelRetries;
  private long missingSince=-1,formingUntil,queryStarted;
  private long now(){return SystemClock.elapsedRealtime();}
  private void event(LinkDiagnostics.Event type,int detail){trace.event(type,detail);}
  private volatile int frequency;
  public TurboLink(Context context,TransferServer host){this(context,host,new LinkDiagnostics());}
  public TurboLink(Context context,TransferServer host,LinkDiagnostics trace){this.context=context;this.host=host;this.trace=trace;manager=(WifiP2pManager)context.getSystemService(Context.WIFI_P2P_SERVICE);openChannel();main.post(tick);}
  private void openChannel(){
    if(closed||manager==null)return;final int epoch=++channelEpoch;
    try{channel=manager.initialize(context,Looper.getMainLooper(),()->{if(closed||epoch!=channelEpoch)return;channel=null;ready=false;polling=false;queryEpoch++;event(LinkDiagnostics.Event.CHANNEL_LOST,channelRetries);status="Đang nối lại dịch vụ Wi-Fi Direct…";
      if(channelRetries++<2)main.postDelayed(()->{if(!closed&&epoch==channelEpoch){openChannel();event(LinkDiagnostics.Event.CHANNEL_REOPEN,channelRetries);inspect();}},2000);else status="Dịch vụ Wi-Fi Direct đã ngắt. Dừng chia sẻ rồi mở lại; có thể sao chép chẩn đoán.";
    });}catch(RuntimeException error){channel=null;event(LinkDiagnostics.Event.API_FAILURE,1);status="Chưa mở được dịch vụ Wi-Fi Direct.";}
  }
  public JSONObject snapshot()throws Exception{return new JSONObject().put("mode",mode).put("status",status).put("ssid",ready?ssid:"").put("passphrase",ready?passphrase:"").put("frequencyMHz",frequency).put("band",frequency>=5000&&frequency<5925?"5 GHz":frequency>=2400&&frequency<2500?"2.4 GHz":"Chưa xác minh").put("owned",!expected.isEmpty()).put("creating",creating).put("ready",ready&&!stopping&&!closed).put("recoveries",recoveries);}
  public void mode(String value){if(!Arrays.asList("auto","lan","turbo").contains(value))throw new IllegalArgumentException("Invalid link mode");mode=value;if(value.equals("lan"))stop();}
  public boolean supported(){return manager!=null&&channel!=null&&context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_WIFI_DIRECT);}
  public JSONObject diagnostics()throws Exception{return new JSONObject().put("mode",mode).put("ready",ready).put("ownedLease",!expected.isEmpty()).put("creating",creating).put("stopping",stopping).put("closed",closed).put("channelAvailable",channel!=null).put("frequencyMHz",frequency).put("recoveryAttempts",recoveries).put("events",trace.report());}
  public void start(){
    if(closed||creating||stopping||!expected.isEmpty())return;if(!supported()){status="Máy chưa sẵn sàng Wi-Fi Direct · dùng LAN";return;}
    String permission=Build.VERSION.SDK_INT>=33?"android.permission.NEARBY_WIFI_DEVICES":"android.permission.ACCESS_FINE_LOCATION";
    if(context.checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED){status="Cần quyền thiết bị Wi-Fi ở gần để kết nối trực tiếp";return;}
    final int lease=++generation;creating=true;blocked=false;recoveries=0;missingSince=-1;formingUntil=now()+30000;
    status="Đang chuẩn bị mạng trực tiếp…";event(LinkDiagnostics.Event.CREATE_REQUEST,0);
    try{manager.requestGroupInfo(channel,existing->{if(closed||lease!=generation)return;if(existing!=null){creating=false;blocked=true;status="Đã có nhóm Wi-Fi Direct sẵn có. Dừng nhóm trong Cài đặt Wi-Fi rồi thử lại; FlowDrop không tự xóa nhóm chưa xác minh.";event(LinkDiagnostics.Event.FOREIGN_GROUP,0);return;}
      expected="DIRECT-fd-FlowDrop-"+UUID.randomUUID().toString().substring(0,8);ssid=expected;passphrase=UUID.randomUUID().toString().replace("-","").substring(0,20);createOwned(lease,expected,passphrase);
    });}catch(RuntimeException error){creating=false;event(LinkDiagnostics.Event.API_FAILURE,2);status="Chưa mở được Wi-Fi Direct. Thử lại hoặc sao chép chẩn đoán.";}
  }
  private void createOwned(final int lease,final String network,final String password){
    if(closed||lease!=generation||mode.equals("lan")||channel==null)return;creating=true;formingUntil=now()+30000;missingSince=-1;
    try{WifiManager wifi=(WifiManager)context.getApplicationContext().getSystemService(Context.WIFI_SERVICE);WifiP2pConfig config=new WifiP2pConfig.Builder().setNetworkName(network).setPassphrase(password).setGroupOperatingBand(wifi!=null&&wifi.is5GHzBandSupported()?WifiP2pConfig.GROUP_OWNER_BAND_5GHZ:WifiP2pConfig.GROUP_OWNER_BAND_AUTO).build();
      manager.createGroup(channel,config,new WifiP2pManager.ActionListener(){
        public void onSuccess(){if(closed||lease!=generation||mode.equals("lan")){cleanupCancelled(network,password,0);return;}creating=false;event(LinkDiagnostics.Event.CREATE_ACCEPTED,recoveries);status="Đang xác nhận mạng trực tiếp…";inspect();}
        public void onFailure(int reason){if(lease!=generation||closed)return;creating=false;formingUntil=0;event(LinkDiagnostics.Event.CREATE_FAILED,reason);status="Chưa tạo được mạng (API "+reason+"). Bấm Thử lại hoặc sao chép chẩn đoán.";if(recoveries==0){clearOwned();blocked=true;}}
      });
    }catch(RuntimeException error){creating=false;formingUntil=0;blocked=true;event(LinkDiagnostics.Event.API_FAILURE,3);status="Hệ điều hành từ chối tạo mạng trực tiếp.";}
  }
  private void inspect(){
    if(closed||stopping||expected.isEmpty()||channel==null||polling)return;
    final int lease=generation,ticket=++queryEpoch;polling=true;queryStarted=now();
    try{manager.requestGroupInfo(channel,group->{if(lease!=generation||ticket!=queryEpoch||closed||stopping)return;polling=false;
      if(group==null){
        if(missingSince<0){missingSince=now();event(LinkDiagnostics.Event.GROUP_QUERY_EMPTY,0);}
        if(now()<formingUntil||now()-missingSince<9000){status=ready?"Đang kiểm tra lại Wi-Fi Direct…":"Đang chờ mạng trực tiếp sẵn sàng…";return;}
        if(ready)event(LinkDiagnostics.Event.GROUP_LOST,0);ready=false;releaseDiscovery();interfaceName="";frequency=0;
        if(!blocked&&!mode.equals("lan")&&recoveries<2){recoveries++;event(LinkDiagnostics.Event.RECOVERY_REQUEST,recoveries);status="Đang khôi phục mạng trực tiếp · lần "+recoveries+" / 2";createOwned(lease,expected,passphrase);}
        else {if(!blocked)event(LinkDiagnostics.Event.RECOVERY_EXHAUSTED,recoveries);blocked=true;status="Mạng trực tiếp đã mất. Bấm Thử lại; có thể sao chép chẩn đoán để kiểm tra.";}return;
      }
      if(!group.isGroupOwner()||!expected.equals(group.getNetworkName())||!passphrase.equals(group.getPassphrase())){if(!blocked)event(LinkDiagnostics.Event.FOREIGN_GROUP,(!group.isGroupOwner()?1:0)|(!expected.equals(group.getNetworkName())?2:0)|(!passphrase.equals(group.getPassphrase())?4:0));ready=false;blocked=true;releaseDiscovery();interfaceName="";frequency=0;status="Nhóm Wi-Fi Direct đã đổi · giữ nguyên nhóm chưa xác minh";return;}
      missingSince=-1;formingUntil=0;creating=false;if(!ready)event(LinkDiagnostics.Event.GROUP_READY,recoveries);ready=true;frequency=group.getFrequency();interfaceName=group.getInterface();status="Wi-Fi Direct · "+(frequency>=5000&&frequency<5925?"5 GHz":frequency>=2400&&frequency<2500?"2.4 GHz":"băng tần chưa xác minh")+" · TLS";
      if(discovery==null&&!interfaceName.isEmpty())try{discovery=new LanDiscovery(host.getDeviceId(),"FlowDrop Turbo","android","1.14.0",host.getPort(),new LanDiscovery.Adapter(){public List<NetworkInterface> interfaces()throws Exception{NetworkInterface iface=NetworkInterface.getByName(interfaceName);return iface==null?Collections.emptyList():Collections.singletonList(iface);}public void bind(DatagramSocket socket){}public HttpURLConnection open(URL url)throws Exception{return (HttpURLConnection)url.openConnection();}});}catch(Exception ignored){status+=" · tìm kiếm dự phòng bằng LAN";}
    });}catch(RuntimeException error){polling=false;event(LinkDiagnostics.Event.API_FAILURE,4);status="Chưa đọc được trạng thái Wi-Fi Direct · đang thử lại";}
  }
  private void cleanupCancelled(String network,String password,int attempt){
    if(channel==null||(!closed&&network.equals(expected)))return;
    try{manager.requestGroupInfo(channel,group->{if(group!=null&&group.isGroupOwner()&&network.equals(group.getNetworkName())&&password.equals(group.getPassphrase())){
      if(!closed&&network.equals(expected))return;event(LinkDiagnostics.Event.LATE_CLEANUP,attempt);manager.removeGroup(channel,new WifiP2pManager.ActionListener(){public void onSuccess(){}public void onFailure(int reason){event(LinkDiagnostics.Event.REMOVE_FAILED,reason);}});
    }else if(group==null&&attempt<2)main.postDelayed(()->cleanupCancelled(network,password,attempt+1),2000);});}catch(RuntimeException ignored){event(LinkDiagnostics.Event.API_FAILURE,5);}
  }
  public JSONArray peers()throws Exception{LanDiscovery active=discovery;return active==null?new JSONArray():active.peers();}
  public boolean routes(String hostName){try{if(!ready||expected.isEmpty()||interfaceName.isEmpty()||!hostName.matches("[0-9.]+"))return false;NetworkInterface iface=NetworkInterface.getByName(interfaceName);if(iface==null)return false;byte[] target=InetAddress.getByName(hostName).getAddress();for(InterfaceAddress local:iface.getInterfaceAddresses()){byte[] address=local.getAddress().getAddress();if(address.length!=4||target.length!=4)continue;int bits=local.getNetworkPrefixLength();if(bits<8||bits>30)continue;boolean same=true;for(int i=0;i<4;i++){int n=Math.min(8,Math.max(0,bits-i*8)),mask=(255<<(8-n))&255;if((address[i]&mask)!=(target[i]&mask))same=false;}if(same)return true;}}catch(Exception ignored){}return false;}
  private final Runnable tick=new Runnable(){public void run(){if(closed)return;
    if(polling&&now()-queryStarted>=6000){polling=false;queryEpoch++;event(LinkDiagnostics.Event.QUERY_TIMEOUT,0);}
    if(creating&&now()>=formingUntil){creating=false;event(LinkDiagnostics.Event.QUERY_TIMEOUT,1);}inspect();main.postDelayed(this,3000);
  }};
  private void releaseDiscovery(){if(discovery!=null){discovery.close();discovery=null;}}
  private void clearOwned(){expected="";ssid="";passphrase="";interfaceName="";frequency=0;ready=false;creating=false;missingSince=-1;formingUntil=0;}
  public void stop(){
    if(stopping)return;final int lease=++generation;queryEpoch++;polling=false;ready=false;releaseDiscovery();event(LinkDiagnostics.Event.STOP_REQUEST,closed?1:0);final String owned=expected,ownedPass=passphrase;if(owned.isEmpty()||manager==null){clearOwned();return;}if(channel==null){creating=false;status="Dịch vụ Wi-Fi Direct đã ngắt; dừng chia sẻ rồi mở lại.";return;}stopping=true;
    main.postDelayed(()->{if(lease==generation&&stopping){stopping=false;event(LinkDiagnostics.Event.QUERY_TIMEOUT,2);status="Chưa xác nhận dừng được mạng. Bấm Dừng để thử lại.";}},6000);
    try{manager.requestGroupInfo(channel,group->{
      if(lease!=generation)return;
      if(group==null||!group.isGroupOwner()||!owned.equals(group.getNetworkName())||!ownedPass.equals(group.getPassphrase())){if(owned.equals(expected))clearOwned();stopping=false;return;}
      event(LinkDiagnostics.Event.REMOVE_REQUEST,closed?1:0);try{manager.removeGroup(channel,new WifiP2pManager.ActionListener(){public void onSuccess(){if(lease!=generation)return;if(owned.equals(expected))clearOwned();stopping=false;event(LinkDiagnostics.Event.REMOVED,0);status="Đã dừng Turbo do FlowDrop tạo · LAN";}public void onFailure(int reason){if(lease!=generation)return;stopping=false;event(LinkDiagnostics.Event.REMOVE_FAILED,reason);status="Chưa dừng được Turbo (API "+reason+"). Mạng vẫn được giữ; bấm Dừng Turbo để thử lại.";}});}catch(RuntimeException error){stopping=false;status="Chưa dừng được Turbo. Kiểm tra Wi-Fi Direct rồi thử lại.";}
    });}catch(RuntimeException error){stopping=false;status="Chưa dừng được Turbo. Kiểm tra Wi-Fi Direct rồi thử lại.";}
  }
  public void close(){closed=true;main.removeCallbacks(tick);stop();}
}
