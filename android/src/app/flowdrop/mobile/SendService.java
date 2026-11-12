package app.flowdrop.mobile;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Owns native, streaming uploads while the picker or another screen is open. */
public final class SendService extends Service {
  public static final String CANCEL="app.flowdrop.mobile.CANCEL_SEND";
  public interface Listener{void onState(JSONObject state);}
  private static final CopyOnWriteArrayList<Listener> listeners=new CopyOnWriteArrayList<>();
  private static volatile JSONObject snapshot=new JSONObject();
  public static JSONObject state(){return snapshot;}
  public static void addListener(Listener listener){listeners.add(listener);listener.onState(snapshot);}
  public static void removeListener(Listener listener){listeners.remove(listener);}
  public static void markRevoked(String origin,String code){try{JSONObject old=snapshot,transfer=old.optJSONObject("transfer");if(transfer!=null&&origin.equals(old.optString("origin"))&&code.equals(transfer.optString("code"))){JSONObject next=new JSONObject(old.toString()).put("status","revoked").put("message","Đã thu hồi mã gửi.");next.remove("transfer");snapshot=next;for(Listener listener:listeners)listener.onState(next);}}catch(JSONException ignored){}}
  public static boolean busy(){return "sending".equals(snapshot.optString("status"));}
  private final Handler main=new Handler(Looper.getMainLooper());
  private final ExecutorService worker=Executors.newSingleThreadExecutor();
  private final TransferClient.Cancellation cancellation=new TransferClient.Cancellation();
  private static final String CHANNEL="flowdrop-send";
  private String origin="",target="";private boolean started;private long began,lastNotification;
  private Notification notification(String text,boolean ongoing,int percent){PendingIntent open=PendingIntent.getActivity(this,3,new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);Notification.Builder b=new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_upload_done).setContentTitle("FlowDrop · Gửi file").setContentText(text).setContentIntent(open).setOngoing(ongoing);if(ongoing){PendingIntent cancel=PendingIntent.getService(this,4,new Intent(this,SendService.class).setAction(CANCEL),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);b.setProgress(100,percent,false).addAction(new Notification.Action.Builder(null,"Hủy gửi",cancel).build());}return b.build();}
  @Override public void onCreate(){super.onCreate();((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(new NotificationChannel(CHANNEL,"Gửi file FlowDrop",NotificationManager.IMPORTANCE_LOW));startForeground(140,notification("Đang chuẩn bị file…",true,0));}
  @Override public int onStartCommand(Intent intent,int flags,int startId){
    if(intent!=null&&CANCEL.equals(intent.getAction())){cancellation.cancel();if(!started)stopSelf();return START_NOT_STICKY;}if(started)return START_NOT_STICKY;started=true;
    String input=intent==null?null:intent.getStringExtra("origin"),raw=getSharedPreferences("native-send",MODE_PRIVATE).getString("request","[]");
    try{origin=TransferClient.base(input);String requested=intent.getStringExtra("target");target=requested==null||requested.isEmpty()?"":TransferClient.base(requested);}catch(Exception e){publish("error",e.getMessage(),null,0,0,0);stopSelf();return START_NOT_STICKY;}
    publish("sending","Đang chuẩn bị file…",null,0,0,0);began=SystemClock.elapsedRealtime();
    worker.submit(()->{
      ArrayList<File> archives=new ArrayList<>();
      try{
        JSONArray items=new JSONArray(raw);List<TransferClient.Source> sources=new ArrayList<>();
        for(int i=0;i<items.length();i++){
          JSONObject f=items.getJSONObject(i);Uri uri=Uri.parse(f.getString("uri"));if(!"content".equals(uri.getScheme()))throw new IOException("Chọn lại file bằng trình chọn file Android.");
          if(f.optBoolean("folder")){
            File temporary=File.createTempFile("flowdrop-folder-",".zip",getCacheDir());archives.add(temporary);
            FolderArchive.Result archive=FolderArchive.create(getContentResolver(),uri,temporary,cancellation,(bytes,current)->publish("sending","Đang đóng gói thư mục · "+current,null,0,bytes,0));
            sources.add(new TransferClient.Source(ReceiveFiles.safeName(archive.name),FolderPackage.MIME,archive.file.length(),()->new FileInputStream(archive.file)));
          }else sources.add(new TransferClient.Source(f.getString("name"),f.optString("type","application/octet-stream"),f.getLong("size"),()->getContentResolver().openInputStream(uri)));
        }
        JSONObject result=TransferClient.send(origin,sources,(index,sent,total)->{
          publish("sending","Đang chuẩn bị · "+sources.get(index).name,null,index,sent,total);long now=SystemClock.elapsedRealtime();
          if(now-lastNotification>1000){lastNotification=now;((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(140,notification((index+1)+" / "+sources.size()+" · "+sources.get(index).name,true,total==0?0:(int)(sent*100/total)));}
        },cancellation);
        TransferHistory.sent(this,origin,result);
        if(!target.isEmpty()){HostService host=HostService.current;if(host==null||host.transfers()==null)throw new IOException("Phiên Wi-Fi đã dừng. Mở lại ứng dụng để gửi lại.");host.transfers().offerTo(target,result.getString("code"));}
        publish("sent",target.isEmpty()?"File đã sẵn sàng để nhận.":"Đã gửi yêu cầu · Chấp nhận trên thiết bị nhận.",result,sources.size(),0,0);complete(target.isEmpty()?"Đã tạo mã "+result.getString("code"):"Đã gửi yêu cầu nhận file.");
      }catch(Exception e){publish(cancellation.isCancelled()?"cancelled":"error",cancellation.isCancelled()?"Đã hủy gửi file.":e.getMessage(),null,0,0,0);complete(cancellation.isCancelled()?"Đã hủy gửi file.":"Chưa gửi được file. Mở ứng dụng để thử lại.");}
      finally{for(File archive:archives)archive.delete();}
    });
    return START_NOT_STICKY;
  }
  private void publish(String status,String message,JSONObject result,int index,long sent,long total){try{JSONObject event=new JSONObject().put("status",status).put("origin",origin).put("target",target).put("message",message==null?"Kiểm tra Wi-Fi và thử lại.":message).put("index",index).put("sent",sent).put("total",total).put("elapsed",Math.max(1,SystemClock.elapsedRealtime()-began));if(result!=null)event.put("transfer",result);snapshot=event;main.post(()->{for(Listener listener:listeners)listener.onState(event);});}catch(JSONException ignored){}}
  private void complete(String text){main.post(()->{stopForeground(STOP_FOREGROUND_REMOVE);((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(140,notification(text,false,0));stopSelf();});}
  @Override public IBinder onBind(Intent intent){return null;}
  @Override public void onTimeout(int startId,int type){cancellation.cancel();publish("error","Android đã dừng phiên nền. Mở ứng dụng để gửi lại.",null,0,0,0);stopSelf();}
  @Override public void onDestroy(){cancellation.cancel();worker.shutdownNow();super.onDestroy();}
}
