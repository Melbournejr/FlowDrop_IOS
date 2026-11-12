package app.flowdrop.mobile.test;
import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.util.*;
public final class ShareSenderActivity extends Activity {
  protected void onCreate(Bundle state){super.onCreate(state);try{
    File directory=new File(getCacheDir(),"share-source");directory.mkdirs();
    try(FileOutputStream out=new FileOutputStream(new File(directory,ShareSourceProvider.PHOTO))){out.write(android.util.Base64.decode(ShareSourceProvider.PNG,0));}
    try(FileOutputStream out=new FileOutputStream(new File(directory,ShareSourceProvider.DOCUMENT))){out.write(ShareSourceProvider.TEXT.getBytes("UTF-8"));}
    Uri photo=new Uri.Builder().scheme("content").authority(ShareSourceProvider.AUTHORITY).appendPath(ShareSourceProvider.PHOTO).build(),document=new Uri.Builder().scheme("content").authority(ShareSourceProvider.AUTHORITY).appendPath(ShareSourceProvider.DOCUMENT).build();
    boolean multiple="multiple".equals(getIntent().getStringExtra("scenario"));Intent send=new Intent(multiple?Intent.ACTION_SEND_MULTIPLE:Intent.ACTION_SEND).setType(multiple?"*/*":"image/png").setComponent(new ComponentName("app.flowdrop.mobile","app.flowdrop.mobile.MainActivity")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_ACTIVITY_NEW_TASK);
    ClipData data=ClipData.newRawUri("shared files",photo);if(multiple){ArrayList<Uri> uris=new ArrayList<>();uris.add(photo);uris.add(document);send.putParcelableArrayListExtra(Intent.EXTRA_STREAM,uris);data.addItem(new ClipData.Item(document));}else send.putExtra(Intent.EXTRA_STREAM,photo);send.setClipData(data);startActivity(send);
  }catch(Exception error){throw new RuntimeException(error);}finally{finish();}}
}
