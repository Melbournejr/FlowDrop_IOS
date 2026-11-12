package app.flowdrop.mobile;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import java.io.*;
import java.util.*;
import org.json.*;

/** Scoped-storage folder import. All folder contents stay together under Download/FlowDrop. */
public final class FolderReceive implements FolderPackage.Sink {
  private final Context context;private final ContentResolver resolver;private final ArrayList<Uri> created=new ArrayList<>();private final Set<Uri> markers=new HashSet<>();
  private final JSONArray inventory=new JSONArray();private final HashSet<String> directoryMarkers=new HashSet<>();
  private String root,path;private File inventoryFile;private boolean committed;
  public FolderReceive(Context context){this.context=context;resolver=context.getContentResolver();}
  private File physical(String relative){return new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),relative.substring("Download/".length()));}
  private boolean exists(String candidate)throws Exception {
    String prefix="Download/FlowDrop/"+candidate+"/";
    if(physical(prefix).exists())return true;
    try(Cursor cursor=resolver.query(MediaStore.Downloads.EXTERNAL_CONTENT_URI,new String[]{MediaStore.MediaColumns.RELATIVE_PATH,MediaStore.MediaColumns.DISPLAY_NAME},MediaStore.MediaColumns.RELATIVE_PATH+" LIKE ?",new String[]{"Download/FlowDrop/%"},null)){
      if(cursor!=null)while(cursor.moveToNext()){String relative=cursor.getString(0);if(relative!=null&&relative.startsWith(prefix)||"Download/FlowDrop/".equals(relative)&&candidate.equals(cursor.getString(1)))return true;}
    }return false;
  }
  @Override public long availableBytes(){return Environment.getExternalStorageDirectory().getUsableSpace();}
  @Override public void begin(String original)throws Exception {
    for(int i=0;i<10000;i++){String candidate=i==0?original:original+" ("+i+")";if(!exists(candidate)){root=candidate;path="Download/FlowDrop/"+candidate;return;}}
    throw new IOException("Có quá nhiều thư mục trùng tên.");
  }
  private Uri insert(String relative,String name,String mime,boolean exactName)throws Exception {
    ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.DISPLAY_NAME,name);values.put(MediaStore.MediaColumns.MIME_TYPE,mime);values.put(MediaStore.MediaColumns.RELATIVE_PATH,relative);values.put(MediaStore.MediaColumns.IS_PENDING,1);
    Uri uri=resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);if(uri==null)throw new IOException("Không tạo được file trong thư mục nhận.");created.add(uri);
    try(Cursor cursor=resolver.query(uri,new String[]{MediaStore.MediaColumns.DISPLAY_NAME,MediaStore.MediaColumns.RELATIVE_PATH},null,null,null)){
      if(cursor==null||!cursor.moveToFirst()||exactName&&!name.equals(cursor.getString(0))||!(relative.endsWith("/")?relative:relative+"/").equals(cursor.getString(1)))throw new IOException("Android không giữ được tên/đường dẫn: "+name+" → "+(cursor!=null&&!cursor.isBeforeFirst()?cursor.getString(0)+" · "+cursor.getString(1):"không đọc được thông tin"));
    }return uri;
  }
  @Override public void directory(String relative)throws Exception {
    if(!directoryMarkers.add(relative))return;Uri marker=insert(path+(relative.isEmpty()?"":"/"+relative),".flowdrop-pending-"+UUID.randomUUID(),"application/octet-stream",false);markers.add(marker);
    try(OutputStream out=resolver.openOutputStream(marker,"w")){if(out==null)throw new IOException("Không tạo được thư mục nhận.");}
  }
  @Override public OutputStream file(String relative,long size)throws Exception {
    int slash=relative.lastIndexOf('/');String folder=slash<0?"":relative.substring(0,slash),name=relative.substring(slash+1);
    String mime=ReceiveFiles.route(name,"").mime;Uri uri=insert(path+(folder.isEmpty()?"":"/"+folder),name,mime,true);
    inventory.put(new JSONObject().put("uri",uri.toString()).put("size",size));OutputStream out=resolver.openOutputStream(uri,"w");if(out==null)throw new IOException("Không ghi được "+relative);return out;
  }
  public JSONObject commit(long archiveSize,FolderPackage.Result result)throws Exception {
    File folder=new File(context.getFilesDir(),"folder-receipts");if(!folder.isDirectory()&&!folder.mkdirs())throw new IOException("Không lưu được thông tin thư mục nhận.");inventoryFile=new File(folder,UUID.randomUUID()+".json");
    JSONObject receipt=new JSONObject().put("kind","folder").put("name",root).put("path",path).put("uri","").put("size",archiveSize).put("filesCount",result.files).put("unpackedSize",result.size).put("inventory",inventoryFile.getAbsolutePath());
    try(OutputStream out=new FileOutputStream(inventoryFile)){out.write(new JSONObject().put("files",inventory).put("directories",new JSONArray(directoryMarkers)).toString().getBytes("UTF-8"));}
    ContentValues ready=new ContentValues();ready.put(MediaStore.MediaColumns.IS_PENDING,0);
    for(Uri uri:created)if(!markers.contains(uri)&&resolver.update(uri,ready,null,null)<1)throw new IOException("Chưa hoàn tất tạo thư mục nhận.");
    for(Uri marker:markers)resolver.delete(marker,null,null);
    committed=true;return receipt;
  }
  public void rollback(){if(committed)return;for(Uri uri:created)try{resolver.delete(uri,null,null);}catch(Exception ignored){}if(inventoryFile!=null)inventoryFile.delete();if(path!=null){ArrayList<String> dirs=new ArrayList<>(directoryMarkers);Collections.sort(dirs,(a,b)->Integer.compare(b.length(),a.length()));for(String dir:dirs)new File(physical(path),dir).delete();physical(path).delete();}}
  public static boolean stillSaved(Context context,JSONObject receipt){
    try{
      String path=receipt.getString("path");File root=new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),path.substring("Download/".length()));if(!root.isDirectory())return false;
      ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=new FileInputStream(receipt.getString("inventory"))){byte[] buffer=new byte[8192];int count;while((count=in.read(buffer))!=-1)bytes.write(buffer,0,count);}
      JSONObject contents=new JSONObject(bytes.toString("UTF-8"));JSONArray directories=contents.getJSONArray("directories");for(int d=0;d<directories.length();d++)if(!new File(root,directories.getString(d)).isDirectory())return false;JSONArray items=contents.getJSONArray("files");for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);try(android.content.res.AssetFileDescriptor file=context.getContentResolver().openAssetFileDescriptor(Uri.parse(item.getString("uri")),"r")){if(file==null||file.getLength()!=item.getLong("size"))return false;}}return true;
    }catch(Exception ignored){return false;}
  }
}
