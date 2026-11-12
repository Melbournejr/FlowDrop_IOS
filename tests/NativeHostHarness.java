package app.flowdrop.mobile;
import java.io.File;
public final class NativeHostHarness {
 public static void main(String[] args)throws Exception{TransferServer server=new TransferServer(new File(args[0]),null,"Android Native test",0);System.out.println(new org.json.JSONObject().put("url",server.getLocalUrl()).put("localToken",server.getUploadCapability()));System.out.flush();Thread.sleep(Long.MAX_VALUE);}
}
