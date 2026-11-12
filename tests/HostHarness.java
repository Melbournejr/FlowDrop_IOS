package app.flowdrop.mobile;
import java.io.File;
import java.nio.file.*;
import java.util.concurrent.CountDownLatch;
public final class HostHarness {
  public static void main(String[] args)throws Exception {
    Path web=Paths.get(args[1]);
    TransferServer server=new TransferServer(new File(args[0]),name->Files.newInputStream(web.resolve(name)),"Android test",0);
    Runtime.getRuntime().addShutdownHook(new Thread(()->server.close()));
    System.out.println(new org.json.JSONObject().put("url",server.getLocalUrl()).put("localToken",server.getUploadCapability()));System.out.flush();new CountDownLatch(1).await();
  }
}
