package app.flowdrop.mobile.test;
import android.app.*;
import android.content.*;
import android.content.pm.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.widget.*;
import app.flowdrop.mobile.*;
import java.io.*;
import java.net.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.json.*;
public final class NativeShareSmoke extends Instrumentation {
  private volatile Activity activity;private volatile int creations;
  private interface Check{boolean ready()throws Exception;}
  private void check(boolean value,String text){if(!value)throw new AssertionError(text);}
  private void await(Check value,String text,int seconds)throws Exception{long deadline=SystemClock.elapsedRealtime()+seconds*1000L;while(SystemClock.elapsedRealtime()<deadline){if(value.ready())return;Thread.sleep(150);}throw new AssertionError(text);}
  public void callActivityOnCreate(Activity value,Bundle state){super.callActivityOnCreate(value,state);if(value instanceof MainActivity){activity=value;creations++;}}
  private View find(View view,String prefix){if(view instanceof TextView&&((TextView)view).getText().toString().startsWith(prefix))return view;if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){View value=find(((ViewGroup)view).getChildAt(i),prefix);if(value!=null)return value;}return null;}
  private View root(){return activity.getWindow().getDecorView();}
  private View widget(String text){AtomicReference<View> found=new AtomicReference<>();runOnMainSync(()->found.set(find(root(),text)));return found.get();}
  private void click(String text)throws Exception{await(()->widget(text)!=null&&widget(text).isEnabled(),"Control unavailable: "+text,40);runOnMainSync(()->find(root(),text).performClick());}
  private JSONArray selection(){AtomicReference<JSONArray> value=new AtomicReference<>();runOnMainSync(()->{try{Field field=MainActivity.class.getDeclaredField("selected");field.setAccessible(true);value.set(new JSONArray(field.get(activity).toString()));}catch(Exception error){throw new RuntimeException(error);}});return value.get();}
  private void sender(String scenario){getTargetContext().startActivity(new Intent().setComponent(new ComponentName("app.flowdrop.mobile.test","app.flowdrop.mobile.test.ShareSenderActivity")).putExtra("scenario",scenario).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
  private void stage(String value){Bundle out=new Bundle();out.putString("stage",value);sendStatus(1,out);}
  public void onCreate(Bundle args){super.onCreate(args);start();}
  public void onStart(){Bundle result=new Bundle();TransferServer receiver=null;try{
    for(String action:new String[]{Intent.ACTION_SEND,Intent.ACTION_SEND_MULTIPLE})for(String type:new String[]{"image/png","video/mp4","application/pdf"}){List<ResolveInfo> targets=getTargetContext().getPackageManager().queryIntentActivities(new Intent(action).setType(type),PackageManager.MATCH_DEFAULT_ONLY);check(targets.stream().anyMatch(r->"app.flowdrop.mobile".equals(r.activityInfo.packageName)),"FlowDrop missing from sharesheet for "+action+" "+type);}
    sender("single");await(()->activity!=null&&selection().length()==1,"Cold single share was not imported",100);Activity original=activity;stage("single_share_imported");
    Uri photo=Uri.parse(selection().getJSONObject(0).getString("uri"));try(Cursor owner=getTargetContext().getContentResolver().query(photo,new String[]{"owner_uid"},null,null,null)){check(owner!=null&&owner.moveToFirst()&&owner.getInt(0)!=android.os.Process.myUid(),"Source must have a separate application UID");}
    check(!SendService.busy()&&!"sent".equals(SendService.state().optString("status")),"Sharing sent a file before confirmation");
    sender("multiple");await(()->activity==original&&selection().length()==2,"Warm multiple share lost files or created a second activity",80);check(creations==1,"Warm share recreated the app");
    Set<String> names=new HashSet<>();for(int i=0;i<selection().length();i++)names.add(selection().getJSONObject(i).getString("name"));check(names.contains(ShareSourceProvider.PHOTO)&&names.contains(ShareSourceProvider.DOCUMENT),"Original names were not preserved");stage("multiple_share_imported_and_deduplicated");
    for(String unsafe:new String[]{"file:///data/data/app.flowdrop.mobile/shared_prefs/private.xml","https://evil.test/file"}){boolean rejected=false;try{SharedFiles.collect(new Intent(Intent.ACTION_SEND).setType("*/*").putExtra(Intent.EXTRA_STREAM,Uri.parse(unsafe)).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));}catch(IOException expected){rejected=true;}check(rejected,"Unsafe shared URI accepted");}
    boolean missingGrant=false;try{SharedFiles.collect(new Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM,photo));}catch(IOException expected){missingGrant=true;}check(missingGrant,"Missing URI grant accepted");
    await(()->HostService.current!=null&&HostService.current.isReady(),"Host not ready",90);TransferServer source=HostService.current.transfers();
    HttpURLConnection denied=(HttpURLConnection)new URL(source.getLocalUrl()+"api/transfers").openConnection();denied.setRequestMethod("POST");denied.setDoOutput(true);try(OutputStream out=denied.getOutputStream()){out.write("{\"files\":[{\"name\":\"blocked.txt\",\"size\":0}]}".getBytes("UTF-8"));}check(denied.getResponseCode()==403,"Android unauthorized local upload was accepted");denied.disconnect();
    receiver=new TransferServer(new File(getTargetContext().getCacheDir(),"share-peer-"+UUID.randomUUID()),null,"Máy nhận kiểm thử",0);
    JSONObject config=TransferClient.json(source.getLocalUrl(),"api/config","GET",null,null,null);String address=null;JSONArray addresses=config.getJSONArray("addresses");for(int i=0;i<addresses.length();i++){String host=new URL(addresses.getString(i)).getHost();if(!host.startsWith("127.")&&!host.startsWith("169.254.")){address=host;break;}}final String target="http://"+(address==null?"localhost":address)+":"+receiver.getPort();
    click("Không thấy thiết bị? Kết nối dự phòng");runOnMainSync(()->{ViewGroup tree=(ViewGroup)root();setAddress(tree,target);});click("Kết nối với thiết bị");await(()->widget("Gửi đến")!=null,"No send preview after shared files",60);check(selection().length()==2,"Connecting discarded shared files");click("Gửi đến");
    await(()->"sent".equals(SendService.state().optString("status")),"Native SendService did not complete",100);JSONArray pending=receiver.pendingOffers();check(pending.length()==1,"Missing recipient consent request");JSONObject offer=receiver.answerOffer(pending.getJSONObject(0).getString("id"),true);String origin=offer.getString("origin"),code=offer.getString("code");JSONArray files=TransferClient.metadata(origin,code).getJSONArray("files");check(files.length()==2,"Shared file count changed");long total=0;
    for(int i=0;i<files.length();i++){JSONObject file=files.getJSONObject(i);ByteArrayOutputStream bytes=new ByteArrayOutputStream();HttpURLConnection connection=(HttpURLConnection)new URL(origin+"api/transfers/"+code+"/files/"+file.getString("id")).openConnection();try(InputStream in=connection.getInputStream()){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)bytes.write(buffer,0,n);}finally{connection.disconnect();}byte[] expected=ShareSourceProvider.PHOTO.equals(file.getString("name"))?android.util.Base64.decode(ShareSourceProvider.PNG,0):ShareSourceProvider.TEXT.getBytes("UTF-8");check(Arrays.equals(expected,bytes.toByteArray()),"Shared bytes changed: "+file.getString("name"));total+=bytes.size();receiver.receiveProgress(offer.getString("id"),total,i+1,file.getString("name"));}
    receiver.receiveFinished(offer.getString("id"),null);stage("native_send_preserved_exact_bytes");
    result.putString("result",new JSONObject().put("passed",true).put("sdk",Build.VERSION.SDK_INT).put("sharesheetSendAndMultiple",true).put("photoVideoPdfMimeResolution",true).put("separateSenderUid",true).put("coldActivityShare",true).put("warmActivityReuse",true).put("deduplicate",true).put("originalNames",true).put("noAutomaticSend",true).put("unsafeUrisRejected",true).put("missingGrantRejected",true).put("localUploadCapabilityRequired",true).put("nativeSendService",true).put("recipientConsent",true).put("exactBytes",true).toString());finish(Activity.RESULT_OK,result);
  }catch(Throwable error){result.putString("failure",android.util.Log.getStackTraceString(error));finish(Activity.RESULT_CANCELED,result);}finally{if(receiver!=null)receiver.close();}}
  private void setAddress(View view,String address){if(view instanceof EditText&&((EditText)view).getHint()!=null&&((EditText)view).getHint().toString().startsWith("http://192.168.")){((EditText)view).setText(address);return;}if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)setAddress(((ViewGroup)view).getChildAt(i),address);}
}
