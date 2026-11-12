package app.flowdrop.mobile;
import java.io.*;
import org.json.*;
/** Exercises the same in-process consent methods used by the Android Activity. */
public final class PeerHostHarness {
 public static void main(String[] args)throws Exception{
  TransferServer host=new TransferServer(new File(args[0]),null,args[1],0);
  System.out.println(new JSONObject().put("url",host.getLocalUrl()).put("localToken",host.getUploadCapability()));System.out.flush();
  BufferedReader input=new BufferedReader(new InputStreamReader(System.in,"UTF-8"));String line;
  while((line=input.readLine())!=null)try{
   JSONObject command=new JSONObject(line),result=new JSONObject();String action=command.getString("action");
   if("list".equals(action))result.put("offers",host.pendingOffers());
   if("answer".equals(action)){
    JSONObject accepted=host.answerOffer(command.getString("id"),command.optBoolean("accept"));result.put("accepted",accepted==null?JSONObject.NULL:accepted);
   }
   if("sessions".equals(action))result.put("sessions",host.sessions());
   if("finish".equals(action))host.receiveFinished(command.getString("id"),null);
   if("send".equals(action))result=host.offerTo(command.getString("target"),command.getString("code"));
   if("receive".equals(action)){
    JSONObject item=command.getJSONObject("offer");String origin=item.getString("origin"),code=item.getString("code"),sessionId=item.getString("id");long received=0;int done=0;JSONArray saved=new JSONArray();
    try{JSONObject meta=TransferClient.metadata(origin,code);JSONArray files=meta.getJSONArray("files");java.nio.file.Path folder=new File(args[0],"received").toPath();java.nio.file.Files.createDirectories(folder);
     for(int i=0;i<files.length();i++){JSONObject file=files.getJSONObject(i);String name=file.getString("name");java.nio.file.Path part=folder.resolve(file.getString("id")+".part"),target=folder.resolve(file.getString("id"));java.net.HttpURLConnection connection=(java.net.HttpURLConnection)new java.net.URL(origin+"api/transfers/"+code+"/files/"+file.getString("id")).openConnection();
      try{long count=0;try(InputStream in=connection.getInputStream();OutputStream out=java.nio.file.Files.newOutputStream(part)){byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1){out.write(bytes,0,n);count+=n;host.receiveProgress(sessionId,received+count,done,name);if(command.optLong("failAfter")>0&&received+count>=command.optLong("failAfter"))throw new IOException("Injected receive failure before commit");if(command.optInt("delay")>0)Thread.sleep(command.optInt("delay"));}}if(count!=file.getLong("size"))throw new IOException("Truncated file");java.nio.file.Files.move(part,target,java.nio.file.StandardCopyOption.REPLACE_EXISTING);received+=count;done++;host.receiveProgress(sessionId,received,done,name);saved.put(target.toString());}finally{connection.disconnect();java.nio.file.Files.deleteIfExists(part);}
     }host.receiveFinished(sessionId,null);result.put("files",saved);
    }catch(Exception e){host.receiveFinished(sessionId,e.getMessage());throw e;}
   }
   System.out.println(result);System.out.flush();
  }catch(Exception e){System.out.println(new JSONObject().put("error",e.toString()));System.out.flush();}
  host.close();
 }
}
