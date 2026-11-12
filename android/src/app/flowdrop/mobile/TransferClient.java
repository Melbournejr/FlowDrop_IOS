package app.flowdrop.mobile;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Native HTTP transport. No renderer; file bodies always use bounded buffers. */
public final class TransferClient {
  public interface Connections{HttpURLConnection open(URL url)throws Exception;}
  private static volatile Connections connections;
  public static void setConnections(Connections provider){connections=provider;}
  private static HttpURLConnection open(URL url)throws IOException{try{Connections selected=connections;return selected==null?(HttpURLConnection)url.openConnection():selected.open(url);}catch(Exception e){throw new IOException("Chưa kết nối được thiết bị qua Wi-Fi.",e);}}
  private static volatile String localOrigin="",localUploadCapability="";
  public static void setLocalUploadCapability(String origin,String capability){localOrigin=origin==null?"":origin;localUploadCapability=capability==null?"":capability;}
  private static final int MAX_JSON=8*1024*1024;
  public static final long MAX_EXACT_SIZE=9007199254740991L;
  public interface Opener {InputStream open()throws IOException;}
  public interface Progress {void update(int index,long sent,long total);}
  public static final class Source {
    public final String name,type;public final long size;private final Opener opener;
    public Source(String name,String type,long size,Opener opener){this.name=name;this.type=type;this.size=size;this.opener=opener;}
    public InputStream open()throws IOException{return opener.open();}
  }
  public static final class Cancellation {
    private volatile boolean cancelled;private volatile HttpURLConnection active;
    public void cancel(){cancelled=true;HttpURLConnection c=active;if(c!=null)c.disconnect();}
    public void check()throws InterruptedIOException{if(cancelled||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Đã hủy gửi file.");}
    public boolean isCancelled(){return cancelled;}
    private synchronized void attach(HttpURLConnection connection)throws IOException{check();active=connection;if(cancelled){connection.disconnect();check();}}
    private synchronized void detach(HttpURLConnection connection){if(active==connection)active=null;}
  }
  public static String base(String value)throws IOException{
    try{URI uri=new URI(value);if(!Arrays.asList("http","https").contains(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getPort()>65535)throw new Exception();return new URI(uri.getScheme(),null,uri.getHost(),uri.getPort(),"/",null,null).toString();}catch(Exception e){throw new IOException("Địa chỉ thiết bị không hợp lệ.");}
  }
  private static HttpURLConnection connect(String origin,String route,String method,Cancellation cancellation)throws IOException{
    HttpURLConnection c=open(new URL(base(origin)+route));c.setRequestMethod(method);if(method.equals("POST")&&route.equals("api/transfers")&&base(origin).equals(localOrigin))c.setRequestProperty("X-Local-Token",localUploadCapability);c.setConnectTimeout(8000);c.setReadTimeout(90000);c.setInstanceFollowRedirects(false);c.setRequestProperty("User-Agent","FlowDropAndroidNative/1.9");if(cancellation!=null)cancellation.attach(c);return c;
  }
  private static JSONObject response(HttpURLConnection c)throws Exception{
    int status=c.getResponseCode();InputStream body=status>=400?c.getErrorStream():c.getInputStream();ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    if(body!=null)try(InputStream input=body){byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))!=-1){if(bytes.size()+n>MAX_JSON)throw new IOException("Danh sách file quá dài để xử lý.");bytes.write(buffer,0,n);}}
    JSONObject data;try{data=new JSONObject(bytes.toString("UTF-8"));}catch(Exception e){throw new IOException("Thiết bị trả dữ liệu không hợp lệ. Kiểm tra phiên FlowDrop.");}
    if(status<200||status>=300)throw new IOException(data.optString("error","Thiết bị chưa hoàn tất yêu cầu ("+status+")."));return data;
  }
  public static JSONObject json(String origin,String route,String method,JSONObject value,String token,Cancellation cancellation)throws Exception{
    HttpURLConnection c=connect(origin,route,method,cancellation);
    try{if(token!=null)c.setRequestProperty("X-Upload-Token",token);if(!"GET".equals(method)){byte[] bytes=value==null?new byte[0]:value.toString().getBytes(StandardCharsets.UTF_8);if(bytes.length>MAX_JSON)throw new IOException("Danh sách tên file quá dài. Hãy chia thành các lượt nhỏ hơn.");c.setRequestProperty("Content-Type","application/json");c.setDoOutput(true);c.setFixedLengthStreamingMode(bytes.length);try(OutputStream out=c.getOutputStream()){out.write(bytes);}}return response(c);}finally{if(cancellation!=null)cancellation.detach(c);c.disconnect();}
  }
  public static JSONObject metadata(String origin,String code)throws Exception{
    if(code==null||!code.matches("[A-Z2-9]{8}"))throw new IOException("Nhập đủ mã nhận 8 ký tự.");JSONObject data=json(origin,"api/transfers/"+code,"GET",null,null,null);CodeLookup.validate(data,code);
    return data;
  }
  public static JSONObject send(String origin,List<Source> sources,Progress progress,Cancellation cancellation)throws Exception{
    if(sources.isEmpty())throw new IOException("Chọn ít nhất một file.");JSONArray files=new JSONArray();long total=0;
    for(Source f:sources){if(f.size<0||f.size>MAX_EXACT_SIZE-total)throw new IOException("Không xác định được dung lượng file đã chọn.");total+=f.size;files.put(new JSONObject().put("name",f.name).put("size",f.size).put("type",f.type));}
    JSONObject session=json(origin,"api/transfers","POST",new JSONObject().put("files",files),null,cancellation);String code=session.getString("code"),token=session.getString("token");long sent=0;
    try{
      JSONArray remote=session.getJSONArray("files");if(remote.length()!=sources.size())throw new IOException("Danh sách file không khớp.");
      for(int i=0;i<sources.size();i++){
        cancellation.check();Source file=sources.get(i);HttpURLConnection c=connect(origin,"api/transfers/"+code+"/files/"+remote.getJSONObject(i).getString("id"),"PUT",cancellation);
        try{c.setRequestProperty("X-Upload-Token",token);c.setRequestProperty("Content-Type","application/octet-stream");c.setDoOutput(true);c.setFixedLengthStreamingMode(file.size);long written=0,last=0;
          try(InputStream input=file.open();OutputStream output=c.getOutputStream()){
            if(input==null)throw new IOException("Không mở được "+file.name);byte[] buffer=new byte[65536];int n;
            while((n=input.read(buffer))!=-1){cancellation.check();if(written+n>file.size)throw new IOException("File đã thay đổi. Chọn lại "+file.name);output.write(buffer,0,n);written+=n;long now=System.nanoTime();if(now-last>200000000L){progress.update(i,sent+written,total);last=now;}}
            if(written!=file.size)throw new IOException("File đã thay đổi hoặc chưa đọc đủ: "+file.name);
          }
          response(c);sent+=written;progress.update(i,sent,total);
        }finally{cancellation.detach(c);c.disconnect();}
      }
      cancellation.check();return json(origin,"api/transfers/"+code+"/complete","POST",null,token,cancellation).put("token",token);
    }catch(Exception e){try{json(origin,"api/transfers/"+code,"DELETE",null,token,null);}catch(Exception ignored){}if(cancellation.isCancelled())throw new InterruptedIOException("Đã hủy gửi file.");throw e;}
  }
  private TransferClient(){}
}
