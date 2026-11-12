package app.flowdrop.mobile;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.zip.*;import org.json.*;
public final class FolderPackageHarness {
 public static void main(String[] args)throws Exception {
  if(args[0].equals("create")){try(ZipOutputStream z=new ZipOutputStream(new FileOutputStream(args[1]))){for(String name:new String[]{"Ảnh dự án/","Ảnh dự án/rỗng/","Ảnh dự án/hình/","Ảnh dự án/hình/Tên gốc.txt","Ảnh dự án/rỗng.bin"}){z.putNextEntry(new ZipEntry(name));if(name.endsWith("Tên gốc.txt"))z.write("Nội dung nguyên bản".getBytes("UTF-8"));z.closeEntry();}}return;}
  Path target=Paths.get(args[2]);Files.createDirectories(target);
  FolderPackage.Result result=FolderPackage.extract(new File(args[1]),new FolderPackage.Sink(){Path root;
   public long availableBytes(){return target.toFile().getUsableSpace();}
   public void begin(String name)throws Exception{root=target.resolve(name);Files.createDirectory(root);}
   public void directory(String relative)throws Exception{Files.createDirectories(root.resolve(relative));}
   public OutputStream file(String relative,long size)throws Exception{Path file=root.resolve(relative);Files.createDirectories(file.getParent());return Files.newOutputStream(file,StandardOpenOption.CREATE_NEW);}
  },new TransferClient.Cancellation(),(bytes,name)->{});
  System.out.println(new JSONObject().put("name",result.name).put("files",result.files).put("size",result.size));
 }
}
