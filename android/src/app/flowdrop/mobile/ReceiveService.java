package app.flowdrop.mobile;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Downloads into MediaStore; only publishes Gallery/Downloads entries after a complete write. */
public final class ReceiveService extends Service {
  private static volatile boolean running;
  public static boolean busy(){return running;}
  public interface Listener {void onResult(String origin,JSONObject event);}
  private static final CopyOnWriteArrayList<Listener> listeners=new CopyOnWriteArrayList<>();
  public static void addListener(Listener listener){listeners.add(listener);}
  public static void removeListener(Listener listener){listeners.remove(listener);}
  private final Handler main=new Handler(Looper.getMainLooper());
  private final ExecutorService worker=Executors.newSingleThreadExecutor();
  private final Set<String> pending=new HashSet<>();
  private static final String CHANNEL="flowdrop-receive";
  private int lastStart=0,savedCount=0;
  private final Set<Batch> batches=Collections.newSetFromMap(new ConcurrentHashMap<Batch,Boolean>());
  private static final class Batch {
    final TransferServer tracker;final String id;long bytes,current;int done;String error;boolean finished;
    Batch(String id){HostService host=HostService.current;tracker=host==null?null:host.transfers();this.id=id;}
    void progress(long count,String name)throws Exception{current=count;if(tracker!=null&&id!=null)tracker.receiveProgress(id,bytes+count,done,name);}
    void saved(long count,String name)throws Exception{bytes+=count;current=0;done++;if(tracker!=null&&id!=null)tracker.receiveProgress(id,bytes,done,name);}
    synchronized void finish(String reason){if(finished)return;finished=true;try{if(tracker!=null&&id!=null)tracker.receiveFinished(id,reason);}catch(Exception e){try{if(tracker!=null&&id!=null)tracker.receiveFinished(id,e.getMessage());}catch(Exception ignored){}}}
  }
  private volatile boolean closed=false;
  private volatile HttpURLConnection activeConnection;
  @Override public void onCreate(){super.onCreate();running=true;NotificationManager manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);manager.createNotificationChannel(new NotificationChannel(CHANNEL,"File đã nhận",NotificationManager.IMPORTANCE_LOW));startForeground(130,notification("Đang lưu file từ FlowDrop…",true));}
  private Notification notification(String text,boolean ongoing){PendingIntent open=PendingIntent.getActivity(this,2,new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);return new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle("FlowDrop").setContentText(text).setContentIntent(open).setOngoing(ongoing).build();}
  private void update(String text){((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(130,notification(text,true));}
  @Override public int onStartCommand(Intent intent,int flags,int startId){
    lastStart=startId;
    String origin=intent==null?null:intent.getStringExtra("origin"),code=intent==null?null:intent.getStringExtra("code"),id=intent==null?null:intent.getStringExtra("fileId"),cookie=intent==null?null:intent.getStringExtra("cookie");
    try{URI uri=new URI(origin);if(!Arrays.asList("http","https").contains(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||code==null||!code.matches("[A-Z2-9]{8}")||id!=null&&!id.matches("[a-f0-9-]{36}"))throw new Exception();}catch(Exception e){if(pending.isEmpty())finish();return START_NOT_STICKY;}
    final String base=origin.endsWith("/")?origin:origin+"/",share=code,fileId=id,cookies=cookie,key=base+code+"/"+id;
    if(!pending.add(key))return START_NOT_STICKY;
    if(pending.size()>20){pending.remove(key);if(pending.isEmpty())finish();return START_NOT_STICKY;}
    Batch batch=new Batch(intent.getStringExtra("sessionId"));batches.add(batch);
    worker.submit(()->{
      try{receive(base,share,fileId,cookies,batch);batch.finish(batch.error);}catch(Exception error){batch.finish(error.getMessage());event(base,share,fileId,"error",null,error.getMessage());}
      finally{batches.remove(batch);main.post(()->{pending.remove(key);if(pending.isEmpty())finish();});}
    });return START_NOT_STICKY;
  }
  private HttpURLConnection connect(String url,String cookie)throws Exception{HttpURLConnection connection=WifiNetwork.open(this,new URL(url));connection.setConnectTimeout(10000);connection.setReadTimeout(60000);connection.setInstanceFollowRedirects(false);if(cookie!=null&&!cookie.isEmpty())connection.setRequestProperty("Cookie",cookie);activeConnection=connection;return connection;}
  private void receive(String base,String code,String selected,String cookie,Batch batch)throws Exception{
    HttpURLConnection meta=connect(base+"api/transfers/"+code,cookie);JSONObject transfer;
    try{if(meta.getResponseCode()!=200)throw new IOException("Mã không còn khả dụng. Hãy kiểm tra hoặc gửi lại file.");ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream input=meta.getInputStream()){byte[] buffer=new byte[2048];int n;while((n=input.read(buffer))!=-1){if(bytes.size()+n>8*1024*1024)throw new IOException("Dữ liệu file không hợp lệ.");bytes.write(buffer,0,n);}}transfer=new JSONObject(bytes.toString("UTF-8"));}finally{meta.disconnect();activeConnection=null;}
    JSONArray files=transfer.getJSONArray("files");if(files.length()<1)throw new IOException("Danh sách file không hợp lệ.");
    long total=0;boolean found=selected==null;
    for(int i=0;i<files.length();i++){JSONObject file=files.getJSONObject(i);long size=file.getLong("size");if(size<0||size>9007199254740991L||!file.getString("id").matches("[a-f0-9-]{36}"))throw new IOException("Dung lượng file không hợp lệ.");if(size>9007199254740991L-total)throw new IOException("Dung lượng vượt phạm vi giao thức.");total+=size;}
    for(int i=0;i<files.length();i++){
      if(closed||Thread.currentThread().isInterrupted())throw new IOException("Đã dừng lưu file.");JSONObject file=files.getJSONObject(i);String id=file.getString("id");if(selected!=null&&!selected.equals(id))continue;found=true;
      try{batch.current=0;save(base,code,file,cookie,batch);batch.saved(file.getLong("size"),file.getString("name"));}catch(Exception error){batch.bytes+=batch.current;batch.current=0;if(batch.error==null)batch.error=error.getMessage();event(base,code,id,"error",null,error.getMessage());}
    }
    if(!found)throw new IOException("Không tìm thấy file.");
  }
  private void save(String base,String code,JSONObject file,String cookie,Batch batch)throws Exception{
    String id=file.getString("id"),name=ReceiveFiles.safeName(file.getString("name"));long expected=file.getLong("size");batch.progress(0,name);
    SharedPreferences receipts=getSharedPreferences("received-files",MODE_PRIVATE);String key=base+code+"/"+id;String old=receipts.getString(key,null);
    if(old!=null)try{JSONObject saved=new JSONObject(old);if("folder".equals(saved.optString("kind"))){if(FolderReceive.stillSaved(this,saved)){event(base,code,id,"saved",saved.getString("path"),null);return;}}else{Uri uri=Uri.parse(saved.getString("uri"));try(android.content.res.AssetFileDescriptor descriptor=getContentResolver().openAssetFileDescriptor(uri,"r")){if(descriptor!=null&&(descriptor.getLength()==expected||descriptor.getLength()<0)){event(base,code,id,"saved",saved.getString("path"),null);return;}}}}catch(Exception ignored){}
    if(FolderPackage.MIME.equals(file.optString("type"))){saveFolder(base,code,file,cookie,batch,receipts,key);return;}
    ReceiveFiles.Route route=ReceiveFiles.route(name,file.optString("type",""));ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.DISPLAY_NAME,name);values.put(MediaStore.MediaColumns.MIME_TYPE,route.mime);values.put(MediaStore.MediaColumns.RELATIVE_PATH,route.path);values.put(MediaStore.MediaColumns.IS_PENDING,1);
    Uri collection="image".equals(route.kind)?MediaStore.Images.Media.EXTERNAL_CONTENT_URI:"video".equals(route.kind)?MediaStore.Video.Media.EXTERNAL_CONTENT_URI:MediaStore.Downloads.EXTERNAL_CONTENT_URI;
    HttpURLConnection connection=connect(base+"api/transfers/"+code+"/files/"+id,cookie);Uri destination=null;boolean published=false;
    try{
      if(connection.getResponseCode()!=200)throw new IOException("Không tải được "+name+". Mã có thể đã hết hạn.");long declared=connection.getContentLengthLong();if(declared>=0&&declared!=expected)throw new IOException("Dung lượng tải về không khớp.");
      destination=getContentResolver().insert(collection,values);if(destination==null)throw new IOException("Không tạo được file trong bộ nhớ máy.");
      update("Đang lưu "+name+" → "+route.path);long count=0,lastProgress=0;
      try(InputStream input=connection.getInputStream();OutputStream output=getContentResolver().openOutputStream(destination,"w")){
        if(output==null)throw new IOException("Không mở được file để ghi.");byte[] buffer=new byte[65536];int n;
        while((n=input.read(buffer))!=-1){if(closed||Thread.currentThread().isInterrupted())throw new IOException("Đã dừng lưu file.");count+=n;if(count>expected)throw new IOException("Dung lượng tải về không khớp.");output.write(buffer,0,n);long now=SystemClock.elapsedRealtime();if(now-lastProgress>500){progress(base,code,id,count,expected);batch.progress(count,name);lastProgress=now;}}if(count!=expected)throw new IOException("File chưa tải đủ. Hãy thử lại.");
      }
      batch.progress(expected,name);ContentValues ready=new ContentValues();ready.put(MediaStore.MediaColumns.IS_PENDING,0);if(getContentResolver().update(destination,ready,null,null)<1)throw new IOException("Chưa hoàn tất lưu file.");published=true;
      String savedName=name;try(Cursor cursor=getContentResolver().query(destination,new String[]{MediaStore.MediaColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())savedName=cursor.getString(0);}catch(RuntimeException ignored){}
      String displayPath=route.path+"/"+savedName;JSONObject receipt=new JSONObject().put("uri",destination.toString()).put("path",displayPath);receipts.edit().putString(key,receipt.toString()).apply();TransferHistory.received(this,base,code,id,savedName,displayPath,destination.toString(),expected);savedCount++;event(base,code,id,"saved",displayPath,null);
    }finally{connection.disconnect();activeConnection=null;if(destination!=null&&!published)try{getContentResolver().delete(destination,null,null);}catch(Exception ignored){}}
  }
  private void saveFolder(String base,String code,JSONObject file,String cookie,Batch batch,SharedPreferences receipts,String key)throws Exception {
    String id=file.getString("id"),name=file.getString("name");long expected=file.getLong("size");File archive=File.createTempFile("flowdrop-receive-folder-",".zip",getCacheDir());FolderReceive sink=new FolderReceive(this);HttpURLConnection connection=connect(base+"api/transfers/"+code+"/files/"+id,cookie);
    try{
      if(connection.getResponseCode()!=200)throw new IOException("Không tải được thư mục.");long declared=connection.getContentLengthLong();if(declared>=0&&declared!=expected)throw new IOException("Dung lượng thư mục không khớp.");
      long bytes=0,last=0;try(InputStream in=connection.getInputStream();OutputStream out=new FileOutputStream(archive)){byte[] buffer=new byte[65536];int count;while((count=in.read(buffer))!=-1){if(closed||Thread.currentThread().isInterrupted())throw new IOException("Đã dừng nhận thư mục.");bytes+=count;if(bytes>expected)throw new IOException("Dung lượng thư mục không khớp.");out.write(buffer,0,count);long now=SystemClock.elapsedRealtime();if(now-last>500){progress(base,code,id,bytes,expected);batch.progress(bytes,name);last=now;}}}if(bytes!=expected)throw new IOException("Thư mục chưa tải đủ.");batch.progress(expected,name);
      final long[] notification={0};FolderPackage.Result result=FolderPackage.extract(archive,sink,new TransferClient.Cancellation(),(count,current)->{if(closed)throw new IOException("Đã dừng nhận thư mục.");long now=SystemClock.elapsedRealtime();if(now-notification[0]>500){update("Đang tạo thư mục · "+current);batch.progress(expected,"Đang tạo thư mục · "+current);notification[0]=now;}});
      JSONObject receipt=sink.commit(expected,result);receipts.edit().putString(key,receipt.toString()).apply();TransferHistory.received(this,base,code,id,receipt.getString("name"),receipt.getString("path"),"",expected);savedCount++;event(base,code,id,"saved",receipt.getString("path"),null);
    }finally{connection.disconnect();activeConnection=null;archive.delete();sink.rollback();}
  }
  private void event(String base,String code,String id,String status,String path,String message){try{JSONObject value=new JSONObject().put("code",code).put("status",status);if(id!=null)value.put("id",id);if(path!=null)value.put("path",path);if(message!=null)value.put("error",message);main.post(()->{for(Listener listener:listeners)listener.onResult(base,value);});}catch(JSONException ignored){}}
  private void progress(String base,String code,String id,long bytes,long total){try{JSONObject value=new JSONObject().put("code",code).put("id",id).put("status","progress").put("bytes",bytes).put("total",total);main.post(()->{for(Listener listener:listeners)listener.onResult(base,value);});}catch(JSONException ignored){}}
  private void finish(){if(stopSelfResult(lastStart)){((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(130,notification(savedCount>0?"Đã lưu "+savedCount+" file vào FlowDrop.":"Đã xử lý lưu file. Mở ứng dụng để xem kết quả.",false));stopForeground(STOP_FOREGROUND_DETACH);}}
  @Override public IBinder onBind(Intent intent){return null;}
  @Override public void onTimeout(int startId,int type){stopSelf();}
  @Override public void onDestroy(){running=false;closed=true;for(Batch batch:batches)batch.finish("Phiên nhận bị dừng trước khi lưu đủ file.");if(activeConnection!=null)activeConnection.disconnect();worker.shutdownNow();super.onDestroy();}
}
