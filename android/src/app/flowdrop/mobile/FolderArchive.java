package app.flowdrop.mobile;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.*;
import java.util.*;
import java.util.zip.*;

/** Native SAF folder traversal and streaming ZIP64, including empty directories. */
public final class FolderArchive {
  public interface Progress {void update(long bytes,String current);}
  public static final class Result {public final File file;public final String name;Result(File file,String name){this.file=file;this.name=name;}}
  private final ContentResolver resolver;private final ZipOutputStream zip;private final TransferClient.Cancellation cancellation;private final Progress progress;
  private final Set<String> visiting=new HashSet<>();private long bytes,last;
  private FolderArchive(ContentResolver resolver,ZipOutputStream zip,TransferClient.Cancellation cancellation,Progress progress){this.resolver=resolver;this.zip=zip;this.cancellation=cancellation;this.progress=progress;}
  private static String part(String name)throws IOException{if(name==null||name.isEmpty()||name.equals(".")||name.equals("..")||name.matches(".*[\\\\/\\x00-\\x1f].*"))throw new IOException("Tên trong thư mục không hợp lệ.");return name;}
  public static String name(ContentResolver resolver,Uri tree)throws IOException{
    Uri root=DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree));
    try(Cursor cursor=resolver.query(root,new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)){
      if(cursor!=null&&cursor.moveToFirst())return part(cursor.getString(0));
    }catch(RuntimeException error){throw new IOException("Không đọc được thư mục đã chọn.",error);}
    throw new IOException("Không đọc được thư mục đã chọn.");
  }
  public static Result create(ContentResolver resolver,Uri tree,File target,TransferClient.Cancellation cancellation,Progress progress)throws Exception{
    String name=name(resolver,tree);if(!"content".equals(tree.getScheme()))throw new IOException("Chọn thư mục bằng trình chọn Android.");
    try(OutputStream file=new BufferedOutputStream(new FileOutputStream(target));ZipOutputStream zip=new ZipOutputStream(file)){
      zip.setLevel(1);new FolderArchive(resolver,zip,cancellation,progress).directory(tree,DocumentsContract.getTreeDocumentId(tree),name,0);zip.finish();return new Result(target,name+".zip");
    }catch(Exception error){target.delete();throw error;}
  }
  private void directory(Uri tree,String id,String path,int depth)throws Exception{
    cancellation.check();if(depth>128||!visiting.add(id))throw new IOException("Thư mục lặp hoặc quá sâu.");
    zip.putNextEntry(new ZipEntry(path+"/"));zip.closeEntry();
    Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,id);
    try(Cursor cursor=resolver.query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,DocumentsContract.Document.COLUMN_SIZE},null,null,null)){
      if(cursor==null)throw new IOException("Không đọc được nội dung thư mục "+path);
      while(cursor.moveToNext()){
        cancellation.check();String child=cursor.getString(0),name=part(cursor.getString(1)),mime=cursor.getString(2),entry=path+"/"+name;
        if(DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)){directory(tree,child,entry,depth+1);continue;}
        long expected=cursor.isNull(3)?-1:cursor.getLong(3),read=0;Uri uri=DocumentsContract.buildDocumentUriUsingTree(tree,child);
        zip.putNextEntry(new ZipEntry(entry));
        try(InputStream in=resolver.openInputStream(uri)){
          if(in==null)throw new IOException("Không mở được "+entry);byte[] buffer=new byte[65536];int count;
          while((count=in.read(buffer))!=-1){cancellation.check();read+=count;if(bytes>9007199254740991L-count)throw new IOException("Dung lượng vượt phạm vi giao thức.");bytes+=count;zip.write(buffer,0,count);long now=System.currentTimeMillis();if(now-last>200){last=now;progress.update(bytes,entry);}}
        }
        if(expected>=0&&read!=expected)throw new IOException("File đã thay đổi: "+entry);zip.closeEntry();progress.update(bytes,entry);
      }
    }finally{visiting.remove(id);}
  }
}
