package app.flowdrop.mobile;

import android.app.*;
import android.app.job.*;
import android.content.*;
import android.content.pm.*;
import android.net.*;
import android.os.*;
import android.provider.Settings;
import android.widget.Toast;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** Public release feed, authenticated APK download and system-managed self updates. */
public final class AppUpdates {
  private static final int JOB=170,NOTICE=171;
  private static final String CHANNEL="flowdrop-updates",PREFS="app-updates";
  private static final AtomicBoolean checking=new AtomicBoolean();
  private static final Handler main=new Handler(Looper.getMainLooper());
  private static final ExecutorService worker=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"flowdrop-updater");t.setDaemon(true);return t;});
  private static volatile String phase="idle",message="";
  private static volatile long downloaded,total,pauseUntil;
  private static boolean dialog;
  private static SharedPreferences prefs(Context context){return context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);}
  public static boolean automatic(Context context){return prefs(context).getBoolean("automatic",true);}
  public static boolean installing(){return "installing".equals(phase);}
  public static synchronized boolean reserveTransfer(){if(installing())return false;pauseUntil=SystemClock.elapsedRealtime()+30000;return true;}
  private static boolean busy(){
    if(SystemClock.elapsedRealtime()<pauseUntil||SendService.busy()||ReceiveService.busy())return true;
    HostService host=HostService.current;
    if(host!=null)try{JSONArray sessions=host.sessions();for(int i=0;i<sessions.length();i++)if(Arrays.asList("pending","accepted","transferring").contains(sessions.getJSONObject(i).optString("state")))return true;}catch(Exception ignored){}
    return false;
  }
  private static File apk(Context context){return new File(new File(context.getFilesDir(),"updates"),"package.apk");}
  private static long current(Context context)throws Exception{return context.getPackageManager().getPackageInfo(context.getPackageName(),0).getLongVersionCode();}
  private static UpdateManifest.Entry cached(Context context){try{String raw=prefs(context).getString("entry",null);if(raw==null)return null;UpdateManifest.Entry entry=new UpdateManifest.Entry(new JSONObject(raw));if(entry.versionCode<=current(context)){clear(context);return null;}return entry;}catch(Exception ignored){return null;}}
  private static void clear(Context context){prefs(context).edit().remove("entry").remove("session").remove("confirmation").apply();apk(context).delete();}
  public static String status(Context context){UpdateManifest.Entry entry=cached(context);if(installing())return "Hệ thống đang cài bản cập nhật…";if("downloading".equals(phase))return "Đang tải "+downloaded+" / "+total+" byte";if("checking".equals(phase))return "Đang kiểm tra bản mới…";if(entry!=null)return "Đã tải bản "+entry.version+" · Sẵn sàng cài";return message.isEmpty()?"FlowDrop "+ReleaseConfig.VERSION:message;}
  public static void configure(Context context,boolean enabled){prefs(context).edit().putBoolean("automatic",enabled).apply();schedule(context);}
  public static void schedule(Context context){
    JobScheduler scheduler=(JobScheduler)context.getSystemService(Context.JOB_SCHEDULER_SERVICE);if(scheduler==null)return;
    if(!automatic(context)){scheduler.cancel(JOB);return;}
    scheduler.schedule(new JobInfo.Builder(JOB,new ComponentName(context,UpdateJobService.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED).setPeriodic(6*3600000L).setPersisted(true).build());
  }
  private static boolean unmetered(Context context){ConnectivityManager manager=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);return manager!=null&&!manager.isActiveNetworkMetered();}
  public static void resume(Activity activity){
    Context context=activity.getApplicationContext();schedule(context);cached(context);
    if(prefs(context).getBoolean("resumeInstall",false)){prefs(context).edit().remove("resumeInstall").apply();if(activity.getPackageManager().canRequestPackageInstalls())install(activity,true);}
    if(automatic(context)&&unmetered(context)&&System.currentTimeMillis()-prefs(context).getLong("checked",0)>6*3600000L)async(context,false);
    offer(activity,false);
  }
  public static void manual(Activity activity){
    if(cached(activity)!=null){offer(activity,true);return;}
    Toast.makeText(activity,"Đang kiểm tra cập nhật…",Toast.LENGTH_SHORT).show();async(activity.getApplicationContext(),true);
  }
  private static void async(Context context,boolean manual){worker.execute(()->{check(context);main.post(()->{MainActivity active=MainActivity.foregroundActivity;if(active==null||active.isFinishing())return;if(manual&&cached(active)==null)Toast.makeText(active,status(active),Toast.LENGTH_LONG).show();else offer(active,manual);});});}
  private static HttpURLConnection connect(String value)throws Exception{
    URL target=new URL(value);
    for(int i=0;i<6;i++){
      if(!"https".equals(target.getProtocol())||target.getUserInfo()!=null)throw new IOException("Cập nhật yêu cầu HTTPS.");
      HttpURLConnection connection=(HttpURLConnection)target.openConnection();connection.setConnectTimeout(10000);connection.setReadTimeout(30000);connection.setInstanceFollowRedirects(false);connection.setRequestProperty("Accept-Encoding","identity");connection.setRequestProperty("User-Agent","FlowDrop/"+ReleaseConfig.VERSION);
      int status=connection.getResponseCode();if(Arrays.asList(301,302,303,307,308).contains(status)){String next=connection.getHeaderField("Location");connection.disconnect();if(next==null)throw new IOException("Đường dẫn cập nhật không hợp lệ.");target=new URL(target,next);continue;}
      if(status!=200){connection.disconnect();throw new IOException("Chưa truy cập được kênh cập nhật ("+status+").");}return connection;
    }
    throw new IOException("Đường dẫn cập nhật chuyển tiếp quá nhiều lần.");
  }
  private static String feed()throws Exception{HttpURLConnection connection=connect(ReleaseConfig.FEED);try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buffer=new byte[8192];int count;while((count=in.read(buffer))!=-1){if(out.size()+count>100000)throw new IOException("Thông tin cập nhật quá lớn.");out.write(buffer,0,count);}return new String(out.toByteArray(),StandardCharsets.UTF_8);}finally{connection.disconnect();}}
  private static String hex(byte[] bytes){StringBuilder value=new StringBuilder();for(byte item:bytes)value.append(String.format(Locale.ROOT,"%02x",item&255));return value.toString();}
  private static String hash(File file)throws Exception{MessageDigest digest=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] buffer=new byte[65536];int count;while((count=in.read(buffer))!=-1)digest.update(buffer,0,count);}return hex(digest.digest());}
  private static Set<String> signers(PackageInfo info)throws Exception{if(info==null||info.signingInfo==null)throw new IOException("APK không có thông tin khóa ký.");Set<String> found=new HashSet<>();for(android.content.pm.Signature signer:info.signingInfo.getApkContentsSigners())found.add(hex(MessageDigest.getInstance("SHA-256").digest(signer.toByteArray())));return found;}
  private static void validateApk(Context context,File file,UpdateManifest.Entry entry)throws Exception{
    if(file.length()!=entry.size||!hash(file).equals(entry.sha256))throw new IOException("Bộ cài chưa đủ dữ liệu hoặc sai SHA256.");
    PackageManager manager=context.getPackageManager();PackageInfo incoming=manager.getPackageArchiveInfo(file.getAbsolutePath(),PackageManager.GET_SIGNING_CERTIFICATES),installed=manager.getPackageInfo(context.getPackageName(),PackageManager.GET_SIGNING_CERTIFICATES);
    if(incoming==null||!context.getPackageName().equals(incoming.packageName)||incoming.getLongVersionCode()!=entry.versionCode||!entry.version.equals(incoming.versionName)||!signers(incoming).equals(signers(installed)))throw new IOException("APK không đúng ứng dụng, phiên bản hoặc khóa ký FlowDrop đang cài.");
  }
  public static boolean check(Context context){
    if(!checking.compareAndSet(false,true))return true;
    File temporary=null;
    try{
      if(busy()){phase="deferred";return false;}phase="checking";message="";prefs(context).edit().putLong("checked",System.currentTimeMillis()).apply();
      UpdateManifest.Entry entry=UpdateManifest.verify(feed(),ReleaseConfig.PUBLIC_KEY);
      if(entry.versionCode<=current(context)){phase="current";message="Bạn đang dùng bản mới nhất.";return true;}
      File target=apk(context);target.getParentFile().mkdirs();
      UpdateManifest.Entry old=cached(context);
      if(old==null||!old.sha256.equals(entry.sha256)||!target.exists()||target.length()!=entry.size){
        phase="downloading";downloaded=0;total=entry.size;temporary=File.createTempFile("download-",".part",target.getParentFile());HttpURLConnection connection=connect(entry.url);
        try{
          long declared=connection.getContentLengthLong();if(declared>=0&&declared!=entry.size)throw new IOException("Dung lượng APK tải về không khớp.");
          MessageDigest digest=MessageDigest.getInstance("SHA-256");
          try(InputStream in=connection.getInputStream();OutputStream out=new FileOutputStream(temporary)){
            byte[] buffer=new byte[65536];int count;while((count=in.read(buffer))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Đã dừng tải cập nhật.");downloaded+=count;if(downloaded>entry.size)throw new IOException("Bộ cài vượt dung lượng đã ký.");digest.update(buffer,0,count);out.write(buffer,0,count);}
          }
          if(downloaded!=entry.size||!hex(digest.digest()).equals(entry.sha256))throw new IOException("Bộ cài tải chưa đủ hoặc sai SHA256.");
          validateApk(context,temporary,entry);Files.move(temporary.toPath(),target.toPath(),StandardCopyOption.REPLACE_EXISTING);temporary=null;
        }finally{connection.disconnect();}
      }else validateApk(context,target,entry);
      prefs(context).edit().putString("entry",entry.json().toString()).apply();phase="ready";
      notifyReady(context,entry.version);
      if(automatic(context)&&Build.VERSION.SDK_INT>=31&&context.getPackageManager().canRequestPackageInstalls()&&!busy())install(context,false);
      return true;
    }catch(Exception error){phase="error";message=error.getMessage()==null?"Chưa kiểm tra được cập nhật.":error.getMessage();return false;}
    finally{if(temporary!=null)temporary.delete();checking.set(false);}
  }
  public static void offer(Activity activity,boolean manual){
    if(activity.isFinishing()||activity.isDestroyed()||dialog)return;UpdateManifest.Entry entry=cached(activity);if(entry==null||busy())return;
    if(installing())return;
    if(automatic(activity)&&Build.VERSION.SDK_INT>=31&&activity.getPackageManager().canRequestPackageInstalls()&&System.currentTimeMillis()-prefs(activity).getLong("attempt",0)>3600000L){install(activity,false);return;}
    if(!manual&&prefs(activity).getLong("offered",0)==entry.versionCode)return;
    prefs(activity).edit().putLong("offered",entry.versionCode).apply();dialog=true;
    new AlertDialog.Builder(activity).setTitle("FlowDrop "+entry.version).setMessage("Đã tải và kiểm tra bản mới. Cài đặt khi không có phiên truyền đang chạy.").setNegativeButton("Để sau",null).setPositiveButton("Cài cập nhật",(d,w)->install(activity,true)).setOnDismissListener(d->dialog=false).show();
  }
  public static synchronized void install(Context context,boolean manual){
    if(busy()||installing())return;UpdateManifest.Entry entry=cached(context);if(entry==null)return;
    try{
      String confirmation=prefs(context).getString("confirmation",null);
      if(confirmation!=null){Intent intent=Intent.parseUri(confirmation,Intent.URI_INTENT_SCHEME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);if(context instanceof Activity)((Activity)context).startActivity(intent);return;}
      int pending=prefs(context).getInt("session",-1);if(pending>=0&&context.getPackageManager().getPackageInstaller().getSessionInfo(pending)!=null)return;
      if(!context.getPackageManager().canRequestPackageInstalls()){
        if(context instanceof Activity){prefs(context).edit().putBoolean("resumeInstall",true).apply();((Activity)context).startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+context.getPackageName())));}else notifyReady(context,entry.version);return;
      }
      validateApk(context,apk(context),entry);PackageInstaller installer=context.getPackageManager().getPackageInstaller();PackageInstaller.SessionParams params=new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);params.setAppPackageName(context.getPackageName());
      if(Build.VERSION.SDK_INT>=31)params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
      int id=installer.createSession(params);phase="installing";prefs(context).edit().putInt("session",id).putLong("attempt",System.currentTimeMillis()).apply();
      try(PackageInstaller.Session session=installer.openSession(id)){
        try(InputStream in=new FileInputStream(apk(context));OutputStream out=session.openWrite("base.apk",0,entry.size)){byte[] buffer=new byte[65536];int count;while((count=in.read(buffer))!=-1)out.write(buffer,0,count);session.fsync(out);}
        Intent result=new Intent(context,UpdateInstallReceiver.class);int flags=PendingIntent.FLAG_UPDATE_CURRENT|(Build.VERSION.SDK_INT>=31?PendingIntent.FLAG_MUTABLE:0);PendingIntent response=PendingIntent.getBroadcast(context,id,result,flags);session.commit(response.getIntentSender());
      }catch(Exception error){installer.abandonSession(id);throw error;}
    }catch(Exception error){phase="ready";message=error.getMessage();prefs(context).edit().remove("session").remove("confirmation").apply();if(context instanceof Activity)Toast.makeText(context,"Chưa cài được: "+message,Toast.LENGTH_LONG).show();}
  }
  private static Notification.Builder notice(Context context){NotificationManager manager=(NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE);manager.createNotificationChannel(new NotificationChannel(CHANNEL,"Cập nhật FlowDrop",NotificationManager.IMPORTANCE_DEFAULT));return new Notification.Builder(context,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle("Cập nhật FlowDrop").setAutoCancel(true);}
  private static void notifyReady(Context context,String version){Intent open=new Intent(context,MainActivity.class).putExtra("installUpdate",true).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);PendingIntent pending=PendingIntent.getActivity(context,NOTICE,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);((NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE)).notify(NOTICE,notice(context).setContentText("Đã tải bản "+version+". Chạm để cài.").setContentIntent(pending).build());}
  public static void installResult(Context context,int status,Intent confirmation,String error){
    if(status==PackageInstaller.STATUS_PENDING_USER_ACTION&&confirmation!=null){
      phase="waiting";confirmation.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);prefs(context).edit().putString("confirmation",confirmation.toUri(Intent.URI_INTENT_SCHEME)).apply();
      PendingIntent pending=PendingIntent.getActivity(context,NOTICE,confirmation,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);((NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE)).notify(NOTICE,notice(context).setContentText("Chạm để xác nhận cài bản mới.").setContentIntent(pending).build());
      MainActivity active=MainActivity.foregroundActivity;if(active!=null&&!busy())active.startActivity(confirmation);return;
    }
    prefs(context).edit().remove("session").remove("confirmation").apply();
    if(status==PackageInstaller.STATUS_SUCCESS){clear(context);phase="current";message="Đã cập nhật FlowDrop.";((NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(NOTICE);}
    else{phase="ready";message=error==null?"Chưa hoàn tất cài cập nhật.":error;}
  }
}
