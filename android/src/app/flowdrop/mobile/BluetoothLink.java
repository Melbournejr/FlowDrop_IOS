package app.flowdrop.mobile;

import android.bluetooth.*;
import android.content.Context;
import android.os.*;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** One explicitly opened, encrypted RFCOMM rendezvous with an OS-bonded peer.
 * Bluetooth exchanges only network setup, never files or FlowDrop trust secrets. */
public final class BluetoothLink implements AutoCloseable {
  public interface Consent { void ask(String bondedName,Runnable accept,Runnable reject); }
  public interface Status { void update(String message); }
  private static final UUID SERVICE=UUID.fromString("f568a2ec-7d09-4bf7-93b4-234912f5c26a");
  private final Handler main=new Handler(Looper.getMainLooper());
  private volatile BluetoothServerSocket listener;
  private volatile BluetoothSocket connection;
  private volatile boolean closed;
  private Runnable deadline;
  public void start(Context context,TurboLink turbo,Consent consent,Status status)throws Exception {
    BluetoothManager manager=(BluetoothManager)context.getSystemService(Context.BLUETOOTH_SERVICE);
    BluetoothAdapter adapter=manager==null?null:manager.getAdapter();
    if(adapter==null||!adapter.isEnabled())throw new IOException("Bật Bluetooth và ghép đôi điện thoại với Windows trong Cài đặt trước.");
    JSONObject state=turbo.snapshot();if(!state.optBoolean("owned")||state.optString("ssid").isEmpty())throw new IOException("Tạo mạng Turbo trước khi kết nối Bluetooth.");
    listener=adapter.listenUsingRfcommWithServiceRecord("FlowDrop Direct Link",SERVICE);
    deadline=()->{close();status.update("Hết thời gian chờ Bluetooth. Bấm kết nối để thử lại.");};
    main.postDelayed(deadline,60000);
    new Thread(()->{
      try{
        connection=listener.accept(60000);listener.close();listener=null;
        BluetoothDevice peer=connection.getRemoteDevice();
        if(peer.getBondState()!=BluetoothDevice.BOND_BONDED)throw new IOException("Chỉ nhận thiết bị đã ghép đôi Bluetooth trong hệ điều hành.");
        String name=peer.getName();name=name==null?"Thiết bị Bluetooth đã ghép đôi":name.replaceAll("[\\p{Cntrl}]"," ");
        final String bondedName=name.length()>80?name.substring(0,80):name;
        InputStream input=connection.getInputStream();ByteArrayOutputStream bytes=new ByteArrayOutputStream();int c;
        while((c=input.read())!=-1&&c!='\n'){if(bytes.size()>=256)throw new IOException("Yêu cầu Bluetooth quá dài.");bytes.write(c);}
        if(c!='\n'||!"FlowDropLink1".equals(bytes.toString("UTF-8")))throw new IOException("Yêu cầu Bluetooth không hợp lệ.");
        CountDownLatch answered=new CountDownLatch(1);boolean[] allowed={false};
        main.post(()->{if(closed){answered.countDown();return;}consent.ask(bondedName,()->{allowed[0]=true;answered.countDown();},answered::countDown);});
        if(!answered.await(30,TimeUnit.SECONDS)||!allowed[0]||closed)throw new IOException("Chưa được chấp nhận kết nối Bluetooth.");
        JSONObject current=turbo.snapshot();
        if(!current.optBoolean("owned")||!state.getString("ssid").equals(current.optString("ssid"))||!state.getString("passphrase").equals(current.optString("passphrase")))throw new IOException("Mạng Turbo đã đổi; hãy thử lại.");
        JSONObject reply=new JSONObject().put("protocol","FlowDropLink1").put("ssid",current.getString("ssid")).put("passphrase",current.getString("passphrase"));
        byte[] payload=(reply.toString()+"\n").getBytes(StandardCharsets.UTF_8);
        connection.getOutputStream().write(payload);connection.getOutputStream().flush();
        main.post(()->status.update("Đã chuyển thông tin mạng qua Bluetooth. Chờ Windows kết nối Wi-Fi; vẫn cần ghép nối TLS trong FlowDrop."));
      }catch(Exception error){if(!closed)main.post(()->status.update("Chưa nối được Bluetooth. Kiểm tra ghép đôi Bluetooth của Windows rồi thử lại."));}
      finally{close();}
    },"flowdrop-bluetooth-link").start();
  }
  public void close(){closed=true;if(deadline!=null)main.removeCallbacks(deadline);try{if(listener!=null)listener.close();}catch(IOException ignored){}try{if(connection!=null)connection.close();}catch(IOException ignored){}}
}
