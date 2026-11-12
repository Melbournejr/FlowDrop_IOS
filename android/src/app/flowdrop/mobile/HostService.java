package app.flowdrop.mobile;

import android.app.*;
import android.content.*;
import android.net.nsd.*;
import android.net.*;
import android.net.wifi.WifiManager;
import java.net.*;
import android.os.*;
import java.io.File;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

/** Keeps the phone's sharing session alive while its file picker or Downloads is open. */
public final class HostService extends Service {
  public interface Listener {void onReady(String name,String url);void onFailure(String text);void onStopped();}
  public static final String STOP="app.flowdrop.mobile.STOP_HOST";
  public static volatile boolean running=false;
  public static volatile HostService current;
  public TransferServer transfers(){return server;}
  public org.json.JSONArray sessions()throws Exception{return server==null?new org.json.JSONArray():server.sessions();}
  private static final String CHANNEL="flowdrop-sharing";
  private final CopyOnWriteArrayList<Listener> listeners=new CopyOnWriteArrayList<>();
  private final Handler main=new Handler(Looper.getMainLooper());
  private final LocalBinder binder=new LocalBinder();
  private volatile TransferServer server;
  private volatile boolean stopped=false;
  private String name,error,displayName;
  private int registrationGeneration;
  private LanDiscovery lan;
  private Network lanNetwork;
  private ConnectivityManager connectivity;
  private ConnectivityManager.NetworkCallback networkCallback;
  private WifiManager.MulticastLock lanLock;
  public org.json.JSONArray lanPeers()throws Exception{return lan==null?new org.json.JSONArray():lan.peers();}
  public void rescanLan(){restartLan();if(lan!=null)lan.rescan();}
  private void restartLan(){
    if(stopped||server==null)return;
    Network next=WifiNetwork.find(this);if(next!=null&&next.equals(lanNetwork)&&lan!=null)return;
    if(lan!=null){lan.close();lan=null;}lanNetwork=next;if(next==null){if(lanLock!=null&&lanLock.isHeld())lanLock.release();return;}
    try{
      if(lanLock!=null&&!lanLock.isHeld())lanLock.acquire();
      final Network chosen=next;
      lan=new LanDiscovery(server.getDeviceId(),displayName,"android","1.13.0",server.getPort(),new LanDiscovery.Adapter(){
        public java.util.List<NetworkInterface> interfaces()throws Exception{return WifiNetwork.interfaces(HostService.this,chosen);}
        public void bind(DatagramSocket socket)throws Exception{chosen.bindSocket(socket);}
        public HttpURLConnection open(URL url)throws Exception{return (HttpURLConnection)chosen.openConnection(url);}
      });
    }catch(Exception e){lan=null;}
  }
  private NsdManager nsd;
  private NsdManager.RegistrationListener registration;
  public final class LocalBinder extends Binder {public HostService getService(){return HostService.this;}}
  public boolean isReady(){return server!=null&&!stopped;}
  public org.json.JSONArray pendingOffers()throws Exception{return server==null?new org.json.JSONArray():server.pendingOffers();}
  public org.json.JSONObject answerOffer(String id,boolean accept)throws Exception{if(server==null)throw new java.io.IOException("Phiên chia sẻ đã dừng.");return server.answerOffer(id,accept);}
  public String getName(){return name;}
  public String getUrl(){return isReady()?server.getLocalUrl():null;}
  public void addListener(Listener listener){listeners.add(listener);if(error!=null)listener.onFailure(error);else if(isReady())listener.onReady(name,getUrl());}
  public void removeListener(Listener listener){listeners.remove(listener);}
  @Override public void onCreate(){
    super.onCreate();running=true;current=this;
    TransferClient.setConnections(url->WifiNetwork.open(this,url));
    try{WifiManager wifi=(WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);if(wifi!=null){lanLock=wifi.createMulticastLock("flowdrop-lan-presence");lanLock.setReferenceCounted(false);}}catch(RuntimeException ignored){}
    connectivity=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
    networkCallback=new ConnectivityManager.NetworkCallback(){@Override public void onAvailable(Network network){main.post(()->restartLan());}@Override public void onLost(Network network){main.post(()->restartLan());}@Override public void onLinkPropertiesChanged(Network network,LinkProperties properties){main.post(()->restartLan());}};
    if(connectivity!=null)try{connectivity.registerNetworkCallback(new NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(),networkCallback);}catch(RuntimeException ignored){}
    NotificationManager notifications=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
    notifications.createNotificationChannel(new NotificationChannel(CHANNEL,"Phiên chia sẻ FlowDrop",NotificationManager.IMPORTANCE_LOW));
    Intent open=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP);
    PendingIntent openAction=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    PendingIntent stopAction=PendingIntent.getService(this,1,new Intent(this,HostService.class).setAction(STOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    Notification notification=new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_upload_done).setContentTitle("FlowDrop đang chia sẻ qua Wi-Fi").setContentText("Thiết bị khác có thể gửi và nhận file. Bấm Dừng để tắt phiên.").setContentIntent(openAction).setOngoing(true).addAction(new Notification.Action.Builder(null,"Dừng",stopAction).build()).build();
    startForeground(120,notification);
    SharedPreferences preferences=getSharedPreferences("host",MODE_PRIVATE);String id=preferences.getString("id",null);
    if(id==null){id=UUID.randomUUID().toString().substring(0,4).toUpperCase(java.util.Locale.ROOT);preferences.edit().putString("id",id).apply();}
    String model=Build.MODEL==null?"Android":Build.MODEL.replaceAll("[\\x00-\\x1f\\x7f]"," ");StringBuilder shortName=new StringBuilder();
    for(int i=0;i<model.length();){int point=model.codePointAt(i);String next=new String(Character.toChars(point));if((shortName.toString()+next).getBytes(java.nio.charset.StandardCharsets.UTF_8).length>32)break;shortName.append(next);i+=Character.charCount(point);}
    final String device=shortName.toString()+" · "+id;displayName=preferences.getString("deviceName",device);try{displayName=DeviceLabel.validate(displayName);}catch(IllegalArgumentException e){displayName=device;}name=DeviceLabel.serviceName(displayName);
    new Thread(()->{
      try{
        TransferServer created=new TransferServer(new File(getFilesDir(),"flowdrop-transfers"),null,device,5173);
        main.post(()->{if(stopped){created.close();return;}server=created;TransferClient.setLocalUploadCapability(created.getLocalUrl(),created.getUploadCapability());created.setDeviceName(displayName);created.setConnections(url->WifiNetwork.open(HostService.this,url));register();restartLan();for(Listener listener:listeners)listener.onReady(name,created.getLocalUrl());});
      }catch(Exception e){main.post(()->{if(stopped)return;error="Chưa tạo được phiên. Kiểm tra bộ nhớ trống và thử lại.";for(Listener listener:listeners)listener.onFailure(error);stopSharing();});}
    },"flowdrop-start-host").start();
  }
  public String getDisplayName(){return displayName;}
  public void renameDevice(String value){
    displayName=DeviceLabel.validate(value);getSharedPreferences("host",MODE_PRIVATE).edit().putString("deviceName",displayName).apply();
    name=DeviceLabel.serviceName(displayName);if(server!=null){server.setDeviceName(displayName);register();}if(lan!=null)lan.rename(displayName);
  }
  private void register(){
    final int generation=++registrationGeneration;
    if(registration!=null&&nsd!=null)try{nsd.unregisterService(registration);}catch(RuntimeException ignored){}

    nsd=(NsdManager)getSystemService(NSD_SERVICE);if(nsd==null)return;
    NsdServiceInfo service=new NsdServiceInfo();service.setServiceName(name);service.setServiceType("_flowdrop._tcp.");service.setPort(server.getPort());service.setAttribute("app","flowdrop");service.setAttribute("label",displayName);service.setAttribute("version","1.13.0");service.setAttribute("id",server.getDeviceId());service.setAttribute("platform","android");service.setAttribute("direct","1");service.setAttribute("protocol","1");
    registration=new NsdManager.RegistrationListener(){
      @Override public void onServiceRegistered(NsdServiceInfo info){main.post(()->{if(stopped||generation!=registrationGeneration){try{nsd.unregisterService(this);}catch(RuntimeException ignored){}return;}name=info.getServiceName();server.setDiscoveryName(name);});}
      @Override public void onRegistrationFailed(NsdServiceInfo info,int code){main.post(()->{if(!stopped&&generation==registrationGeneration)for(Listener listener:listeners)listener.onFailure("Phiên đã mở nhưng chưa phát hiện tự động được. Kiểm tra Wi-Fi hoặc dùng địa chỉ dự phòng.");});}
      @Override public void onServiceUnregistered(NsdServiceInfo info){}
      @Override public void onUnregistrationFailed(NsdServiceInfo info,int code){}
    };
    try{nsd.registerService(service,NsdManager.PROTOCOL_DNS_SD,registration);}catch(RuntimeException e){for(Listener listener:listeners)listener.onFailure("Không bật được tìm thiết bị tự động. Dùng địa chỉ dự phòng hoặc tạo lại phiên.");}
  }
  @Override public IBinder onBind(Intent intent){return binder;}
  @Override public int onStartCommand(Intent intent,int flags,int startId){if(intent!=null&&STOP.equals(intent.getAction()))stopSharing();return START_NOT_STICKY;}
  public void stopSharing(){
    if(stopped)return;stopped=true;running=false;if(current==this)current=null;
    if(registration!=null&&nsd!=null){try{nsd.unregisterService(registration);}catch(RuntimeException ignored){}registration=null;}
    if(lan!=null){lan.close();lan=null;}
    if(connectivity!=null&&networkCallback!=null)try{connectivity.unregisterNetworkCallback(networkCallback);}catch(RuntimeException ignored){}
    if(lanLock!=null&&lanLock.isHeld())try{lanLock.release();}catch(RuntimeException ignored){}
    TransferClient.setConnections(null);TransferClient.setLocalUploadCapability(null,null);
    if(server!=null){server.close();server=null;}
    stopForeground(STOP_FOREGROUND_REMOVE);for(Listener listener:listeners)listener.onStopped();stopSelf();
  }
  @Override public void onTimeout(int startId,int type){stopSharing();}
  @Override public void onDestroy(){stopSharing();listeners.clear();main.removeCallbacksAndMessages(null);super.onDestroy();}
}
