package app.flowdrop.mobile.test;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import android.service.notification.StatusBarNotification;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.*;
import app.flowdrop.mobile.*;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.json.*;

/** Additional real-device tests; all four original instrumentation classes are also retained. */
public final class NativeRuntimeSmoke extends Instrumentation {
 private volatile Activity activity;
 private Bundle arguments;
 private final JSONArray checks = new JSONArray();
 private final ArrayList<JSONObject> saved = new ArrayList<>();
 interface Condition { boolean ready() throws Exception; }
 void check(boolean value,String text){if(!value)throw new AssertionError(text);}
 void await(Condition condition,String text,int seconds)throws Exception{long end=SystemClock.elapsedRealtime()+seconds*1000L;while(SystemClock.elapsedRealtime()<end){if(condition.ready())return;SystemClock.sleep(150);}throw new AssertionError(text);}
 void passed(String id,JSONObject details)throws Exception{checks.put(details.put("id",id).put("passed",true));Bundle out=new Bundle();out.putString("stage",id);sendStatus(1,out);}
 public void callActivityOnCreate(Activity value,Bundle state){super.callActivityOnCreate(value,state);if(value instanceof MainActivity)activity=value;}
 public void onCreate(Bundle args){super.onCreate(args);arguments=args==null?new Bundle():args;start();}
 String hash(byte[] bytes)throws Exception{StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
 byte[] read(InputStream source)throws Exception{try(InputStream in=source;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){check(out.size()+n<=8*1024*1024,"Smoke read exceeded bound");out.write(b,0,n);}return out.toByteArray();}}
 void launch()throws Exception{getTargetContext().startActivity(new Intent(Intent.ACTION_MAIN).setComponent(new ComponentName("app.flowdrop.mobile","app.flowdrop.mobile.MainActivity")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));await(()->activity!=null,"No actual MainActivity",120);await(()->activePackage().equals("app.flowdrop.mobile"),"MainActivity window did not become active",45);}
 View find(View v,String prefix){if(v instanceof TextView&&((TextView)v).getText().toString().startsWith(prefix)&&v.getVisibility()==View.VISIBLE)return v;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){View out=find(((ViewGroup)v).getChildAt(i),prefix);if(out!=null)return out;}return null;}
 View widget(String text){AtomicReference<View> found=new AtomicReference<>();runOnMainSync(()->found.set(find(activity.getWindow().getDecorView(),text)));return found.get();}
 void click(String text)throws Exception{await(()->widget(text)!=null&&widget(text).isEnabled(),"Actual native control missing: "+text,90);View control=widget(text);check(control!=null&&control.isEnabled(),"Actual native control became unavailable: "+text);runOnMainSync(()->control.performClick());}
 String activePackage(){AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();return root==null?"":String.valueOf(root.getPackageName());}
 void pressKey(int key)throws Exception{long down=SystemClock.uptimeMillis();KeyEvent pressed=new KeyEvent(down,down,KeyEvent.ACTION_DOWN,key,0,0,KeyCharacterMap.VIRTUAL_KEYBOARD,0,KeyEvent.FLAG_FROM_SYSTEM,InputDevice.SOURCE_KEYBOARD);check(getUiAutomation().injectInputEvent(pressed,true),"Android rejected actual key down: "+key);KeyEvent released=new KeyEvent(down,SystemClock.uptimeMillis(),KeyEvent.ACTION_UP,key,0,0,KeyCharacterMap.VIRTUAL_KEYBOARD,0,KeyEvent.FLAG_FROM_SYSTEM,InputDevice.SOURCE_KEYBOARD);check(getUiAutomation().injectInputEvent(released,true),"Android rejected actual key up: "+key);}
 boolean clickPermission(String id){AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();if(root==null)return false;for(AccessibilityNodeInfo node:root.findAccessibilityNodeInfosByViewId("com.android.permissioncontroller:id/"+id))if(node.isEnabled()&&node.isClickable())return node.performAction(AccessibilityNodeInfo.ACTION_CLICK);return false;}
 void permissions(Bundle result)throws Exception{
  launch();
  if(Build.VERSION.SDK_INT<33){passed("notification-api-policy",new JSONObject().put("sdk",Build.VERSION.SDK_INT).put("runtimePermissionRequired",false));return;}
  AccessibilityServiceInfo info=getUiAutomation().getServiceInfo();info.flags|=AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;getUiAutomation().setServiceInfo(info);
  final boolean allow="grant".equals(arguments.getString("decision","deny"));
  check(getTargetContext().checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED,"Permission probe requires initially denied permission");
  // Invoke the application's own request method. No production implementation is modified.
  runOnMainSync(()->{try{java.lang.reflect.Method ask=MainActivity.class.getDeclaredMethod("askNotifications");ask.setAccessible(true);ask.invoke(activity);}catch(Exception e){throw new RuntimeException(e);}});
  await(()->activePackage().contains("permissioncontroller"),"Actual Android notification permission dialog did not appear",45);
  await(()->clickPermission(allow?"permission_allow_button":"permission_deny_button"),"Permission decision control unavailable",45);
  await(()->!activePackage().contains("permissioncontroller"),"Permission dialog did not close",45);
  boolean granted=getTargetContext().checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;
  check(granted==allow,"Actual permission state differs from UI decision");
  passed("notification-permission-"+(allow?"grant":"deny"),new JSONObject().put("sdk",Build.VERSION.SDK_INT).put("dialogObserved",true).put("granted",granted).put("method","native request method + Android permissioncontroller accessibility action"));
 }
 int status(String origin,String route,String method,byte[] body,String upload,String local)throws Exception{
  HttpURLConnection c=(HttpURLConnection)new URL(origin+route).openConnection();c.setRequestMethod(method);c.setConnectTimeout(8000);c.setReadTimeout(30000);
  if(upload!=null)c.setRequestProperty("X-Upload-Token",upload);if(local!=null)c.setRequestProperty("X-Local-Token",local);
  try{if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(body.length);try(OutputStream out=c.getOutputStream()){out.write(body);}}int value=c.getResponseCode();InputStream stream=value>=400?c.getErrorStream():c.getInputStream();if(stream!=null)read(stream);return value;}finally{c.disconnect();}
 }
 void core()throws Exception{
  Context context=getTargetContext();launch();await(()->HostService.current!=null&&HostService.current.isReady(),"App foreground backend never became ready",150);
  HostService host=HostService.current;TransferServer server=host.transfers();String origin=server.getLocalUrl();String identity=server.getDeviceId();
  JSONObject config=TransferClient.json(origin,"api/config","GET",null,null,null);check("FlowDrop".equals(config.getString("name"))&&"1.13.0".equals(config.getString("version")),"Unexpected actual backend config");
  passed("live-native-backend",new JSONObject().put("sdk",Build.VERSION.SDK_INT).put("version",config.getString("version")));
  boolean notification=false;for(StatusBarNotification item:((NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE)).getActiveNotifications())if(item.getId()==120)notification=true;
  check(notification,"Foreground HostService notification missing");passed("foreground-notification",new JSONObject().put("hostReady",true).put("notificationId",120));
  click("● Điện thoại đang hiển thị trong Wi-Fi");click("Chọn file để gửi");
  await(()->activePackage().contains("documentsui"),"Actual Android document picker did not open",45);
  pressKey(KeyEvent.KEYCODE_BACK);
  await(()->activePackage().equals("app.flowdrop.mobile"),"Picker cancel did not return to app",45);
  check(widget("Chọn file hoặc thư mục.")!=null,"Picker cancellation changed empty selection");passed("system-picker-cancel",new JSONObject().put("systemPickerObserved",true).put("selectionPreserved",true));
  String suffix=Long.toString(System.currentTimeMillis());String[] names={"Rỗng "+suffix+".bin","Tệp Unicode có khoảng trắng "+suffix+".txt","small "+suffix+".bin"};
  byte[] pattern=new byte[131089];for(int i=0;i<pattern.length;i++)pattern[i]=(byte)(i%251);byte[][] bytes={new byte[0],"FlowDrop native SHA-256 — dữ liệu tổng hợp".getBytes("UTF-8"),pattern};
  JSONArray hashes=new JSONArray();ArrayList<Uri> received=new ArrayList<>();JSONObject last=null;
  for(int round=0;round<2;round++){
   ArrayList<TransferClient.Source> sources=new ArrayList<>();for(int i=0;i<names.length;i++){final byte[] data=bytes[i];sources.add(new TransferClient.Source(names[i],"application/octet-stream",data.length,()->new ByteArrayInputStream(data)));}
   JSONObject transfer=TransferClient.send(origin,sources,(i,n,t)->{},new TransferClient.Cancellation());last=transfer;String code=transfer.getString("code");
   JSONArray remote=transfer.getJSONArray("files");for(int i=0;i<remote.length();i++){JSONObject file=remote.getJSONObject(i);HttpURLConnection c=(HttpURLConnection)new URL(origin+"api/transfers/"+code+"/files/"+file.getString("id")).openConnection();byte[] actual;try{check(c.getResponseCode()==200,"Real HTTP file not available");actual=read(c.getInputStream());}finally{c.disconnect();}check(hash(actual).equals(hash(bytes[i])),"Live HTTP SHA-256 mismatch");}
   String session=server.beginCodeReceive(origin,transfer,null);context.startForegroundService(new Intent(context,ReceiveService.class).putExtra("origin",origin).putExtra("code",code).putExtra("sessionId",session));
   await(()->{JSONArray history=TransferHistory.read(context);int count=0;for(int i=0;i<history.length();i++)if("receive".equals(history.getJSONObject(i).optString("direction"))&&code.equals(history.getJSONObject(i).optString("code")))count++;return count==3;},"ReceiveService did not save all files",180);
   JSONArray history=TransferHistory.read(context);for(int i=0;i<history.length();i++){JSONObject entry=history.getJSONObject(i);if(!"receive".equals(entry.optString("direction"))||!code.equals(entry.optString("code")))continue;int index=-1;for(int j=0;j<remote.length();j++)if(entry.getString("key").endsWith(remote.getJSONObject(j).getString("id")))index=j;check(index>=0,"Saved history lost transfer file identity");String originalName=names[index],savedName=entry.getString("name");if(round==0)check(originalName.equals(savedName),"Original received filename lost");else{int dot=originalName.lastIndexOf('.');check(!savedName.equals(originalName)&&savedName.startsWith(originalName.substring(0,dot))&&savedName.endsWith(originalName.substring(dot)),"Collision changed original filename stem or extension");}Uri uri=Uri.parse(entry.getString("uri"));try(Cursor cursor=context.getContentResolver().query(uri,new String[]{MediaStore.MediaColumns.DISPLAY_NAME,MediaStore.MediaColumns.IS_PENDING},null,null,null)){check(cursor!=null&&cursor.moveToFirst()&&savedName.equals(cursor.getString(0))&&cursor.getInt(1)==0,"History differs from published MediaStore filename");}check(!received.contains(uri),"Duplicate name overwrote an existing URI");received.add(uri);byte[] data=read(context.getContentResolver().openInputStream(uri));check(hash(data).equals(hash(bytes[index])),"Saved MediaStore SHA-256 mismatch");saved.add(new JSONObject().put("uri",uri.toString()).put("sha256",hash(data)));hashes.put(new JSONObject().put("round",round).put("name",entry.getString("name")).put("originalName",originalName).put("size",data.length).put("expectedSha256",hash(bytes[index])).put("actualSha256",hash(data)));}
  }
  check(received.size()==6,"Independent duplicate transfers lost files");passed("native-transfer-and-collision-sha256",new JSONObject().put("files",hashes));
  TransferClient.Cancellation cancellation=new TransferClient.Cancellation();byte[] cancelledBytes=new byte[4*1024*1024];boolean cancelled=false;
  try{TransferClient.send(origin,Arrays.asList(new TransferClient.Source("cancelled.bin","application/octet-stream",cancelledBytes.length,()->new ByteArrayInputStream(cancelledBytes))),(i,n,t)->{if(n>0)cancellation.cancel();},cancellation);}catch(InterruptedIOException expected){cancelled=true;}
  check(cancelled&&cancellation.isCancelled(),"Actual active transfer cancellation was not observed");passed("cancel-active-http",new JSONObject().put("cancelled",true));
  JSONObject incomplete=TransferClient.json(origin,"api/transfers","POST",new JSONObject().put("files",new JSONArray().put(new JSONObject().put("name","interrupted.bin").put("size",65536))),null,null);
  String code=incomplete.getString("code"),upload=incomplete.getString("token"),file=incomplete.getJSONArray("files").getJSONObject(0).getString("id");
  URL address=new URL(origin);try(Socket socket=new Socket("127.0.0.1",address.getPort())){OutputStream stream=socket.getOutputStream();String headers="PUT /api/transfers/"+code+"/files/"+file+" HTTP/1.1\r\nHost: 127.0.0.1:"+address.getPort()+"\r\nX-Upload-Token: "+upload+"\r\nContent-Length: 65536\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n";stream.write(headers.getBytes("UTF-8"));stream.write(new byte[]{1,2,3});stream.flush();}
  SystemClock.sleep(500);check(status(origin,"api/transfers/"+code+"/complete","POST",new byte[0],upload,null)==409,"Disconnected upload was completed");check(status(origin,"api/transfers/"+code+"/files/"+file,"GET",null,null,null)==409,"Partial file became public");TransferClient.json(origin,"api/transfers/"+code,"DELETE",null,upload,null);passed("tcp-disconnect-no-partial-publication",new JSONObject().put("declaredBytes",65536).put("sentBytes",3));
  byte[] invalid="{\"files\":[{\"name\":\"bad.bin\",\"size\":-1}]}".getBytes("UTF-8");
  check(status(origin,"api/transfers","POST",invalid,null,null)==403,"Missing local capability accepted");check(status(origin,"api/transfers","POST",invalid,null,"incorrect-fixture-capability")==403,"Incorrect local capability accepted");check(status(origin,"api/transfers","POST",invalid,null,server.getUploadCapability())==400,"Invalid metadata accepted");passed("auth-and-invalid-request",new JSONObject().put("missingCapability",403).put("incorrectCapability",403).put("invalidMetadata",400));
  TransferServer peer=new TransferServer(new File(context.getCacheDir(),"runtime-peer-"+UUID.randomUUID()),null,"Runtime consent fixture",0);
  try{server.offerTo(peer.getLocalUrl(),last.getString("code"));await(()->peer.pendingOffers().length()==1,"Real peer consent request missing",30);JSONObject offer=peer.pendingOffers().getJSONObject(0);peer.answerOffer(offer.getString("id"),false);check(peer.pendingOffers().length()==0,"Rejected request remained pending");check("rejected".equals(peer.sessions().getJSONObject(0).getString("state")),"Recipient reject state missing");passed("recipient-rejection",new JSONObject().put("state","rejected").put("scope","same-emulator loopback; not physical LAN"));}finally{peer.close();}
  pressKey(KeyEvent.KEYCODE_HOME);await(()->!activePackage().isEmpty()&&!activePackage().equals("app.flowdrop.mobile"),"HOME did not move app to background",45);String backgroundPackage=activePackage();
  check("FlowDrop".equals(TransferClient.json(origin,"api/config","GET",null,null,null).getString("name")),"Foreground backend stopped when app went to background");launch();passed("background-and-reopen",new JSONObject().put("httpAliveInBackground",true).put("foregroundPackageDuringBackground",backgroundPackage).put("appWindowActiveAfterReopen",true));
  runOnMainSync(()->host.stopSharing());await(()->!HostService.running,"Host did not stop",30);boolean offline=false;try{TransferClient.json(origin,"api/config","GET",null,null,null);}catch(Exception expected){offline=true;}check(offline,"Stopped backend remained available");
  runOnMainSync(()->activity.recreate());await(()->HostService.current!=null&&HostService.current.isReady(),"Host restart failed",150);check(identity.equals(HostService.current.transfers().getDeviceId()),"Restart changed persistent device identity");
  for(JSONObject receipt:saved)check(receipt.getString("sha256").equals(hash(read(context.getContentResolver().openInputStream(Uri.parse(receipt.getString("uri")))))),"Restart or collision changed received data");
  passed("stop-restart-data-preserved",new JSONObject().put("filesVerified",saved.size()).put("deviceIdentityPreserved",true));
 }
 public void onStart(){Bundle result=new Bundle();try{if("prepare".equals(arguments.getString("mode"))){AppUpdates.configure(getTargetContext(),false);check(!AppUpdates.automatic(getTargetContext()),"Could not disable automatic updates in isolated test profile");passed("isolated-update-settings",new JSONObject().put("automatic",false));}else if("permissions".equals(arguments.getString("mode")))permissions(result);else core();result.putString("result",new JSONObject().put("passed",true).put("sdk",Build.VERSION.SDK_INT).put("checks",checks).toString());finish(Activity.RESULT_OK,result);}catch(Throwable failure){result.putString("failure",android.util.Log.getStackTraceString(failure));result.putString("completedChecks",checks.toString());finish(Activity.RESULT_CANCELED,result);}}
}
