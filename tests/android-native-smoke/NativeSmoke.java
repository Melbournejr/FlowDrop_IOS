package app.flowdrop.mobile.test;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import android.view.*;
import android.widget.*;
import app.flowdrop.mobile.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.json.*;

/** Instrumentation exercises real Activity, ContentResolver, services and MediaStore. */
public final class NativeSmoke extends Instrumentation {
 private volatile Activity activity;private final ArrayList<Uri> sourceUris=new ArrayList<>(),savedUris=new ArrayList<>();private final HashMap<String,byte[]> expected=new HashMap<>();
 interface Condition{boolean test()throws Exception;}
 private void check(boolean v,String m){if(!v)throw new AssertionError(m);}
 private void await(Condition test,String message,int seconds)throws Exception{long end=SystemClock.elapsedRealtime()+seconds*1000L;while(SystemClock.elapsedRealtime()<end){if(test.test())return;SystemClock.sleep(200);}throw new AssertionError(message+"; sender="+SendService.state());}
 private View find(View view,String value){if(view instanceof TextView&&value.contentEquals(((TextView)view).getText())&&view.getVisibility()==View.VISIBLE)return view;if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++){View found=find(group.getChildAt(i),value);if(found!=null)return found;}}return null;}
 private View root(){return activity.getWindow().getDecorView();}
 private View widget(String text){AtomicReference<View> found=new AtomicReference<>();runOnMainSync(()->found.set(find(root(),text)));return found.get();}
 private void click(String text)throws Exception{await(()->widget(text)!=null,"Missing native control "+text,90);runOnMainSync(()->{View v=find(root(),text);check(v!=null&&v.isEnabled(),"Native control disabled: "+text);v.performClick();});}
 private void noRenderer(View view){check(!view.getClass().getName().startsWith("android.webkit."),"Embedded renderer found");if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)noRenderer(((ViewGroup)view).getChildAt(i));}
 private void screenshot(String name)throws Exception{Bitmap bitmap=getUiAutomation().takeScreenshot();if(bitmap!=null){File file=new File(getTargetContext().getExternalFilesDir(null),name);try(FileOutputStream out=new FileOutputStream(file)){bitmap.compress(Bitmap.CompressFormat.PNG,100,out);}bitmap.recycle();}}
 private Uri create(String name,String mime,byte[] bytes)throws Exception{ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.DISPLAY_NAME,name);values.put(MediaStore.MediaColumns.MIME_TYPE,mime);values.put(MediaStore.MediaColumns.RELATIVE_PATH,"Download/FlowDropNativeTest");Uri uri=getTargetContext().getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);check(uri!=null,"Cannot create source");try(OutputStream output=getTargetContext().getContentResolver().openOutputStream(uri)){output.write(bytes);}sourceUris.add(uri);expected.put(name,bytes);return uri;}
 private void stage(String value){Bundle b=new Bundle();b.putString("stage",value);sendStatus(1,b);}
 @Override public void callActivityOnCreate(Activity value,Bundle state){super.callActivityOnCreate(value,state);if(value instanceof MainActivity){activity=value;stage("native_activity_created");}}
 @Override public void onCreate(Bundle arguments){super.onCreate(arguments);start();}
 @Override public void onStart(){Bundle result=new Bundle();try{
  Intent launch=new Intent(Intent.ACTION_MAIN).setComponent(new ComponentName("app.flowdrop.mobile","app.flowdrop.mobile.MainActivity")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);stage("launching_native_activity");getTargetContext().startActivity(launch);await(()->activity!=null,"Activity creation timed out",120);await(()->widget("Tạo phiên trên điện thoại này")!=null,"Native connect screen not ready",120);runOnMainSync(()->noRenderer(root()));screenshot("native-connect-1.6.png");stage("native_connect_screen");click("Tạo phiên trên điện thoại này");await(()->widget("Chọn file để gửi")!=null,"Phone host did not open native send screen",150);
  stage("native_phone_host_ready");byte[] text=new byte[1024*1024];for(int i=0;i<text.length;i++)text[i]=(byte)(i%251);create("Tài liệu native.txt","text/plain",text);create("Rỗng.bin","application/octet-stream",new byte[0]);create("Ảnh native.png","image/png",android.util.Base64.decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZQAAAABJRU5ErkJggg==",0));
  Intent chosen=new Intent();ClipData data=ClipData.newRawUri("native-files",sourceUris.get(0));for(int i=1;i<sourceUris.size();i++)data.addItem(new ClipData.Item(sourceUris.get(i)));chosen.setClipData(data);chosen.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
  IntentFilter filter=new IntentFilter(Intent.ACTION_OPEN_DOCUMENT);filter.addCategory(Intent.CATEGORY_OPENABLE);filter.addDataType("*/*");ActivityMonitor picker=addMonitor(filter,new ActivityResult(Activity.RESULT_OK,chosen),true);click("Chọn file để gửi");await(()->picker.getHits()>0,"Native picker contract not invoked",30);removeMonitor(picker);stage("native_picker_result");await(()->{View b=widget("Tạo mã gửi");return b!=null&&b.isEnabled();},"Picker results not loaded",90);click("Tạo mã gửi");await(()->"sent".equals(SendService.state().optString("status")),"Native SendService did not complete",180);stage("native_send_complete");JSONObject transfer=SendService.state().getJSONObject("transfer");String code=transfer.getString("code");check(transfer.getJSONArray("files").length()==3,"Native picker lost files");runOnMainSync(()->noRenderer(root()));screenshot("native-send-1.6.png");
  click("Nhận file");runOnMainSync(()->{View edit=findHint(root(),"ABCD EFGH");check(edit instanceof EditText,"Native code input missing");((EditText)edit).setText(code);});
  await(()->{JSONArray history=TransferHistory.read(getTargetContext());int n=0;for(int i=0;i<history.length();i++)if("receive".equals(history.getJSONObject(i).optString("direction"))&&code.equals(history.getJSONObject(i).optString("code")))n++;return n==3;},"Native automatic MediaStore receive did not finish",180);
  stage("native_receive_complete");JSONArray history=TransferHistory.read(getTargetContext());for(int i=0;i<history.length();i++){JSONObject entry=history.getJSONObject(i);if(!"receive".equals(entry.optString("direction"))||!code.equals(entry.optString("code")))continue;Uri uri=Uri.parse(entry.getString("uri"));savedUris.add(uri);byte[] original=expected.get(entry.getString("name"));ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream input=getTargetContext().getContentResolver().openInputStream(uri)){byte[] buffer=new byte[65536];int n;while((n=input.read(buffer))!=-1)bytes.write(buffer,0,n);}check(Arrays.equals(bytes.toByteArray(),original),"MediaStore saved bytes changed");try(Cursor c=getTargetContext().getContentResolver().query(uri,new String[]{MediaStore.MediaColumns.IS_PENDING,MediaStore.MediaColumns.RELATIVE_PATH},null,null,null)){check(c!=null&&c.moveToFirst()&&c.getInt(0)==0,"Partial file was published");check(c.getString(1).startsWith(entry.getString("name").endsWith(".png")?"DCIM/FlowDrop":"Download/FlowDrop"),"Wrong saved folder");}}
  runOnMainSync(()->noRenderer(root()));screenshot("native-receive-1.6.png");click("Lịch sử");await(()->widget("Lịch sử chuyển file")!=null,"Native history missing",30);screenshot("native-history-1.6.png");
  String origin=SendService.state().getString("origin");TransferClient.json(origin,"api/transfers/"+code,"DELETE",null,transfer.getString("token"),null);for(Uri uri:savedUris)try(InputStream input=getTargetContext().getContentResolver().openInputStream(uri)){check(input!=null,"Revoke removed saved file");}
  result.putString("result",new JSONObject().put("passed",true).put("sdk",Build.VERSION.SDK_INT).put("nativeWidgets",true).put("embeddedRenderer",false).put("nativePickerContract",true).put("files",3).put("nativeSendService",true).put("automaticReceiveService",true).put("mediaStoreExactBytes",true).put("albumAndDownloads",true).put("partialFilesHidden",true).put("revokeKeepsSavedFiles",true).put("history",true).toString());finish(Activity.RESULT_OK,result);
 }catch(Throwable e){result.putString("failure",android.util.Log.getStackTraceString(e));finish(Activity.RESULT_CANCELED,result);}finally{for(Uri uri:sourceUris)try{getTargetContext().getContentResolver().delete(uri,null,null);}catch(Exception ignored){}}}
 private View findHint(View view,String hint){if(view instanceof EditText&&hint.contentEquals(((EditText)view).getHint()))return view;if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){View found=findHint(((ViewGroup)view).getChildAt(i),hint);if(found!=null)return found;}return null;}
}
