package app.flowdrop.mobile;
import android.content.*;
import android.net.Uri;
import android.os.Parcelable;
import java.io.IOException;
import java.util.*;
/** Only user-granted content URIs enter the native file selection. No URL fetching or file:// access. */
public final class SharedFiles {
  public static boolean accepts(Intent intent){return intent!=null&&(Intent.ACTION_SEND.equals(intent.getAction())||Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction()));}
  public static ArrayList<Uri> collect(Intent intent)throws IOException{
    LinkedHashSet<Uri> files=new LinkedHashSet<>();if(!accepts(intent))return new ArrayList<>();
    if((intent.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)==0)throw new IOException("Ứng dụng chia sẻ chưa cấp quyền đọc file. Chọn Chia sẻ từ Thư viện hoặc trình quản lý file rồi thử lại.");
    try{
      if(Intent.ACTION_SEND.equals(intent.getAction())){Parcelable value=intent.getParcelableExtra(Intent.EXTRA_STREAM);if(value!=null){if(!(value instanceof Uri))throw new IOException("Dữ liệu chia sẻ không hợp lệ.");add(files,(Uri)value);}}
      else{ArrayList<?> values=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);if(values!=null)for(Object value:values){if(!(value instanceof Uri))throw new IOException("Dữ liệu chia sẻ không hợp lệ.");add(files,(Uri)value);}}
      if(intent.getData()!=null)add(files,intent.getData());
      ClipData clip=intent.getClipData();if(clip!=null)for(int i=0;i<clip.getItemCount();i++){Uri value=clip.getItemAt(i).getUri();if(value!=null)add(files,value);}
    }catch(RuntimeException error){throw new IOException("Không đọc được danh sách file chia sẻ. Hãy chọn lại file.");}
    if(files.isEmpty())throw new IOException("Chọn file để chia sẻ với FlowDrop. Nội dung chỉ có văn bản hoặc đường dẫn chưa được hỗ trợ.");
    int length=0;for(Uri uri:files){length+=uri.toString().length();if(length>8*1024*1024)throw new IOException("Danh sách đường dẫn chia sẻ quá dài.");}return new ArrayList<>(files);
  }
  private static void add(Set<Uri> files,Uri value)throws IOException{if(!"content".equals(value.getScheme())||value.getAuthority()==null||value.getAuthority().isEmpty()||value.toString().length()>65536||value.toString().matches("(?s).*[\\x00-\\x1f\\x7f].*"))throw new IOException("Chỉ nhận file qua quyền chia sẻ của Android. Không mở đường dẫn hệ thống hoặc URL từ ứng dụng khác.");files.add(value);}
  private SharedFiles(){}
}
