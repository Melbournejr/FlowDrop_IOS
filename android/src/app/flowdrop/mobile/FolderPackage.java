package app.flowdrop.mobile;

import java.io.*;
import java.util.*;
import java.util.zip.*;

/** Platform-independent folder package reader; it never interprets entries as links. */
public final class FolderPackage {
  public static final String MIME="application/vnd.flowdrop.folder+zip";
  public interface Sink {
    long availableBytes()throws Exception;
    void begin(String root)throws Exception;
    void directory(String relative)throws Exception;
    OutputStream file(String relative,long size)throws Exception;
  }
  public interface Progress {void update(long bytes,String name)throws Exception;}
  public static final class Result {public final String name;public final int files;public final long size;Result(String name,int files,long size){this.name=name;this.files=files;this.size=size;}}
  private static String[] components(String value)throws IOException {
    if(value.isEmpty()||value.startsWith("/")||value.indexOf('\\')>=0||java.util.regex.Pattern.compile("[\\x00-\\x1f\\x7f]").matcher(value).find()||value.matches("^[A-Za-z]:.*"))throw new IOException("Đường dẫn trong thư mục không hợp lệ.");
    String[] parts=value.split("/",-1);for(String part:parts)if(part.isEmpty()||part.equals(".")||part.equals(".."))throw new IOException("Đường dẫn trong thư mục không hợp lệ.");return parts;
  }
  public static Result extract(File archive,Sink sink,TransferClient.Cancellation cancellation,Progress progress)throws Exception {
    String root=null;int count=0;long total=0;Set<String> names=new HashSet<>();
    try(ZipFile zip=new ZipFile(archive)){
      Enumeration<? extends ZipEntry> entries=zip.entries();
      while(entries.hasMoreElements()){
        cancellation.check();ZipEntry entry=entries.nextElement();boolean directory=entry.isDirectory();String full=entry.getName();if(directory)full=full.substring(0,full.length()-1);String[] parts=components(full);
        if(root==null){if(!directory||parts.length!=1)throw new IOException("Gói thiếu thư mục gốc.");root=parts[0];sink.begin(root);}
        if(!root.equals(parts[0])||!names.add(full))throw new IOException("Gói có nhiều thư mục gốc hoặc tên bị trùng.");
        String relative=parts.length==1?"":full.substring(root.length()+1);long size=entry.getSize();
        if(size<0||size>9007199254740991L-total||directory&&size!=0)throw new IOException("Dung lượng trong thư mục không hợp lệ.");
        if(size+64L*1024*1024>sink.availableBytes())throw new IOException("Không đủ dung lượng trống để khôi phục thư mục an toàn.");
        if(directory){sink.directory(relative);continue;}
        if(relative.isEmpty())throw new IOException("Thư mục gốc không hợp lệ.");long bytes=0;CRC32 crc=new CRC32();
        try(InputStream in=zip.getInputStream(entry);OutputStream out=sink.file(relative,size)){
          byte[] buffer=new byte[65536];int read;while((read=in.read(buffer))!=-1){cancellation.check();bytes+=read;if(bytes>size)throw new IOException("File trong thư mục sai dung lượng.");crc.update(buffer,0,read);out.write(buffer,0,read);progress.update(total+bytes,full);}
        }
        if(bytes!=size||crc.getValue()!=entry.getCrc())throw new IOException("File trong thư mục chưa đủ hoặc sai CRC: "+full);total+=bytes;count++;
      }
    }
    if(root==null)throw new IOException("Gói thư mục rỗng không hợp lệ.");return new Result(root,count,total);
  }
}
