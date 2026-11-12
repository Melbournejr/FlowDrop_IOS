package app.flowdrop.mobile.test;
import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import java.io.*;
/** Separate-UID source application used only by instrumentation; not shipped in FlowDrop. */
public final class ShareSourceProvider extends ContentProvider {
  public static final String AUTHORITY="app.flowdrop.sharetests.files";
  public static final String PHOTO="Ảnh chia sẻ.png",DOCUMENT="Chia sẻ từ Quản lý file.txt";
  public static final String TEXT="Dữ liệu chia sẻ qua Android — giữ nguyên tên và nội dung.\n";
  public static final String PNG="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZQAAAABJRU5ErkJggg==";
  public boolean onCreate(){return true;}
  private File file(Uri uri)throws FileNotFoundException{String name=uri.getLastPathSegment();if(!PHOTO.equals(name)&&!DOCUMENT.equals(name))throw new FileNotFoundException();return new File(new File(getContext().getCacheDir(),"share-source"),name);}
  public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){try{File file=file(uri);String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor out=new MatrixCursor(columns);Object[] values=new Object[columns.length];for(int i=0;i<columns.length;i++)values[i]=OpenableColumns.DISPLAY_NAME.equals(columns[i])?file.getName():OpenableColumns.SIZE.equals(columns[i])?file.length():"owner_uid".equals(columns[i])?android.os.Process.myUid():null;out.addRow(values);return out;}catch(Exception error){return null;}}
  public String getType(Uri uri){return PHOTO.equals(uri.getLastPathSegment())?"image/png":"text/plain";}
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{if(!"r".equals(mode))throw new FileNotFoundException();return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
  public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
  public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
  public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
}
