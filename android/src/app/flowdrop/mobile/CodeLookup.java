package app.flowdrop.mobile;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Supplier;
import org.json.*;

/** Resolve an eight-character share code across LAN hosts instead of one selected host. */
public final class CodeLookup {
  public interface Connections {HttpURLConnection open(URL url)throws Exception;}
  public static final class Found {public final String origin;public final JSONObject metadata;Found(String origin,JSONObject metadata){this.origin=origin;this.metadata=metadata;}}
  public static String normalize(String code){return code==null?"":code.replaceAll("[\\p{javaWhitespace}\\p{Z}\\x{0085}\\x{FEFF}-]","").toUpperCase(Locale.ROOT);}
  private static final class LookupFailure extends IOException{final int status;LookupFailure(int status){super("Mã không khả dụng.");this.status=status;}}
  private static JSONObject json(String origin,String route,Connections connections)throws Exception{
    HttpURLConnection connection=connections.open(new URL(origin+route));connection.setConnectTimeout(2000);connection.setReadTimeout(2500);connection.setInstanceFollowRedirects(false);
    try{
      int status=connection.getResponseCode();if(status!=200)throw new LookupFailure(status);
      try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
        byte[] buffer=new byte[8192];int count;while((count=in.read(buffer))!=-1){if(out.size()+count>8*1024*1024)throw new IOException("Phản hồi quá lớn.");out.write(buffer,0,count);}
        return new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
      }
    }finally{connection.disconnect();}
  }
  public static Found find(String input,Collection<String> candidates,String preferred,Connections connections)throws Exception{
    return find(input,()->candidates,preferred,connections);
  }
  public static Found find(String input,Supplier<? extends Collection<String>> candidates,String preferred,Connections connections)throws Exception{
    String code=normalize(input);if(!code.matches("[A-Z2-9]{8}"))throw new IOException("Nhập đủ mã nhận 8 ký tự.");
    LinkedHashSet<String> origins=new LinkedHashSet<>();final java.util.concurrent.atomic.AtomicInteger verified=new java.util.concurrent.atomic.AtomicInteger();final java.util.concurrent.atomic.AtomicBoolean expired=new java.util.concurrent.atomic.AtomicBoolean(),unpaired=new java.util.concurrent.atomic.AtomicBoolean();
    ExecutorService pool=Executors.newFixedThreadPool(4,r->{Thread thread=new Thread(r,"flowdrop-code-lookup");thread.setDaemon(true);return thread;});
    CompletionService<Found> completion=new ExecutorCompletionService<>(pool);ArrayList<Found> found=new ArrayList<>();
    try{
      long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(7);
      int pending=0;
      while(System.nanoTime()<deadline){
        for(String candidate:candidates.get())try{URI uri=new URI(candidate);if(!Arrays.asList("http","https").contains(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getPort()>65535)continue;String origin=uri.getScheme()+"://"+uri.getRawAuthority();if(origins.size()>=64||!origins.add(origin))continue;
          completion.submit(()->{JSONObject config=json(origin,"/api/config",connections);if(!"FlowDrop".equals(config.optString("name")))throw new IOException("Không phải FlowDrop.");verified.incrementAndGet();try{JSONObject metadata=json(origin,"/api/transfers/"+code,connections);validate(metadata,code);return new Found(origin+"/",metadata);}catch(LookupFailure e){if(e.status==410)expired.set(true);throw e;}});pending++;
        }catch(Exception ignored){}
        if(pending==0&&!found.isEmpty())break;
        Future<Found> next=completion.poll(Math.min(TimeUnit.MILLISECONDS.toNanos(200),Math.max(0,deadline-System.nanoTime())),TimeUnit.NANOSECONDS);
        if(next!=null){pending--;try{found.add(next.get());}catch(ExecutionException error){if(error.getCause()!=null&&String.valueOf(error.getCause().getMessage()).toLowerCase(Locale.ROOT).contains("ghép nối"))unpaired.set(true);}}
      }
    }finally{pool.shutdownNow();}
    if(found.size()>1){for(Found match:found)if(preferred!=null&&match.origin.equals(preferred.endsWith("/")?preferred:preferred+"/"))return match;throw new IOException("Nhiều thiết bị dùng cùng mã. Chọn đúng thiết bị gửi rồi nhận lại.");}
    if(found.isEmpty())throw new IOException(unpaired.get()?"Ghép nối thiết bị gửi trong mục Bảo mật trước khi nhận mã.":expired.get()?"Mã chia sẻ đã hết hạn. Tạo mã mới trên thiết bị gửi.":verified.get()>0?"Mã không tồn tại hoặc đã được thu hồi. Kiểm tra lại mã và máy gửi.":"Chưa tìm thấy thiết bị giữ mã trong Wi-Fi. Mở FlowDrop trên máy gửi rồi thử lại.");
    return found.get(0);
  }
  public static void validate(JSONObject metadata,String code)throws Exception{
    if(!code.equals(metadata.optString("code")))throw new IOException("Mã trả về không khớp.");
    JSONArray files=metadata.getJSONArray("files");if(files.length()==0)throw new IOException("Không có file trong mã này.");long total=0;Set<String> ids=new HashSet<>();
    for(int i=0;i<files.length();i++){
      JSONObject file=files.getJSONObject(i);Object raw=file.get("size");if(!(raw instanceof Number))throw new IOException("Dung lượng không hợp lệ.");double exact=((Number)raw).doubleValue();long size=((Number)raw).longValue();
      if(!Double.isFinite(exact)||size!=exact||size<0||size>9007199254740991L-total||!file.getString("id").matches("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")||!ids.add(file.getString("id"))||file.getString("name").trim().isEmpty()||file.getString("name").length()>255||java.util.regex.Pattern.compile("[\\x00-\\x1f\\x7f]").matcher(file.getString("name")).find()||file.optString("type","").length()>150||java.util.regex.Pattern.compile("[\\x00-\\x1f\\x7f]").matcher(file.optString("type","")).find())throw new IOException("Thông tin file không hợp lệ.");if(file.has("sha256")&&!file.getString("sha256").matches("[a-f0-9]{64}"))throw new IOException("SHA-256 của file không hợp lệ.");total+=size;
    }
  }
}
