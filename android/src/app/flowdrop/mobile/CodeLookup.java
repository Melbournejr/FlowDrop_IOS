package app.flowdrop.mobile;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Resolve an eight-character share code across LAN hosts instead of one selected host. */
public final class CodeLookup {
  public interface Connections {HttpURLConnection open(URL url)throws Exception;}
  public static final class Found {public final String origin;public final JSONObject metadata;Found(String origin,JSONObject metadata){this.origin=origin;this.metadata=metadata;}}
  public static String normalize(String code){return code==null?"":code.replaceAll("[\\s-]","").toUpperCase(Locale.ROOT);}
  private static JSONObject json(String origin,String route,Connections connections)throws Exception{
    HttpURLConnection connection=connections.open(new URL(origin+route));connection.setConnectTimeout(2000);connection.setReadTimeout(2500);connection.setInstanceFollowRedirects(false);
    try{
      if(connection.getResponseCode()!=200)throw new IOException("Không có mã trên thiết bị này.");
      try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
        byte[] buffer=new byte[8192];int count;while((count=in.read(buffer))!=-1){if(out.size()+count>8*1024*1024)throw new IOException("Phản hồi quá lớn.");out.write(buffer,0,count);}
        return new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
      }
    }finally{connection.disconnect();}
  }
  public static Found find(String input,Collection<String> candidates,String preferred,Connections connections)throws Exception{
    String code=normalize(input);if(!code.matches("[A-Z2-9]{8}"))throw new IOException("Nhập đủ mã nhận 8 ký tự.");
    LinkedHashSet<String> origins=new LinkedHashSet<>();
    for(String candidate:candidates)try{URI uri=new URI(candidate);if(("http".equals(uri.getScheme())||"https".equals(uri.getScheme()))&&uri.getHost()!=null&&uri.getUserInfo()==null&&uri.getPort()<=65535)origins.add(uri.getScheme()+"://"+uri.getRawAuthority());if(origins.size()>=64)break;}catch(Exception ignored){}
    ExecutorService pool=Executors.newFixedThreadPool(4,r->{Thread thread=new Thread(r,"flowdrop-code-lookup");thread.setDaemon(true);return thread;});
    CompletionService<Found> completion=new ExecutorCompletionService<>(pool);ArrayList<Found> found=new ArrayList<>();
    try{
      for(String origin:origins)completion.submit(()->{
        JSONObject config=json(origin,"/api/config",connections);if(!"FlowDrop".equals(config.optString("name")))throw new IOException("Không phải FlowDrop.");
        JSONObject metadata=json(origin,"/api/transfers/"+code,connections);validate(metadata,code);return new Found(origin+"/",metadata);
      });
      long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(7);
      for(int i=0;i<origins.size();i++){
        long remaining=deadline-System.nanoTime();if(remaining<=0)break;Future<Found> next=completion.poll(remaining,TimeUnit.NANOSECONDS);if(next==null)break;
        try{found.add(next.get());}catch(ExecutionException ignored){}
      }
    }finally{pool.shutdownNow();}
    if(found.size()>1){for(Found match:found)if(preferred!=null&&match.origin.equals(preferred.endsWith("/")?preferred:preferred+"/"))return match;throw new IOException("Nhiều thiết bị dùng cùng mã. Chọn đúng thiết bị gửi rồi nhận lại.");}
    if(found.isEmpty())throw new IOException("Chưa tìm thấy mã trong Wi-Fi. Mở FlowDrop trên máy gửi, giữ mã còn hiệu lực rồi thử lại.");
    return found.get(0);
  }
  public static void validate(JSONObject metadata,String code)throws Exception{
    if(!code.equals(metadata.optString("code")))throw new IOException("Mã trả về không khớp.");
    JSONArray files=metadata.getJSONArray("files");if(files.length()==0)throw new IOException("Không có file trong mã này.");long total=0;Set<String> ids=new HashSet<>();
    for(int i=0;i<files.length();i++){
      JSONObject file=files.getJSONObject(i);Object raw=file.get("size");if(!(raw instanceof Number))throw new IOException("Dung lượng không hợp lệ.");double exact=((Number)raw).doubleValue();long size=((Number)raw).longValue();
      if(!Double.isFinite(exact)||size!=exact||size<0||size>9007199254740991L-total||!file.getString("id").matches("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")||!ids.add(file.getString("id"))||file.getString("name").trim().isEmpty()||file.getString("name").length()>255||java.util.regex.Pattern.compile("[\\x00-\\x1f\\x7f]").matcher(file.getString("name")).find()||file.optString("type","").length()>150||java.util.regex.Pattern.compile("[\\x00-\\x1f\\x7f]").matcher(file.optString("type","")).find())throw new IOException("Thông tin file không hợp lệ.");total+=size;
    }
  }
}
