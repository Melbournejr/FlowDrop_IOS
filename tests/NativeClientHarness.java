package app.flowdrop.mobile;
import java.io.*;
import java.net.*;
import java.security.*;
import java.util.*;
import org.json.*;

/** Executes the exact transport shipped in the APK, with a small JVM heap. */
public final class NativeClientHarness {
  static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
  static String hex(byte[] bytes){StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format("%02x",b&255));return out.toString();}
  static final class Generated extends InputStream {
    long remaining;final MessageDigest hash;
    Generated(long size,MessageDigest hash){remaining=size;this.hash=hash;}
    @Override public int read()throws IOException{byte[] b=new byte[1];return read(b,0,1)==-1?-1:b[0]&255;}
    @Override public int read(byte[] b,int offset,int length){if(remaining==0)return -1;int count=(int)Math.min(remaining,length);Arrays.fill(b,offset,offset+count,(byte)90);hash.update(b,offset,count);remaining-=count;return count;}
  }
  public static void main(String[] args)throws Exception{
    String origin=args[0];TransferClient.setLocalUploadCapability(origin,System.getenv("FLOWDROP_TEST_LOCAL_CAPABILITY"));long large=Long.parseLong(args[1]);List<TransferClient.Source> sources=new ArrayList<>();List<String> digests=new ArrayList<>();
    for(int i=0;i<100;i++){byte[] bytes=i==0?new byte[0]:("Tệp tiếng Việt · "+i).getBytes("UTF-8");sources.add(new TransferClient.Source("Tài liệu "+i+".txt","text/plain",bytes.length,()->new ByteArrayInputStream(bytes)));digests.add(hex(MessageDigest.getInstance("SHA-256").digest(bytes)));}
    MessageDigest expected=MessageDigest.getInstance("SHA-256");sources.add(new TransferClient.Source("Video lớn.bin","application/octet-stream",large,()->new Generated(large,expected)));
    final long[] last={0,0};TransferClient.Cancellation cancellation=new TransferClient.Cancellation();JSONObject sent=TransferClient.send(origin,sources,(i,bytes,total)->{check(bytes>=last[0],"Progress moved backward");last[0]=bytes;last[1]=total;},cancellation);digests.add(hex(expected.digest()));check(last[0]==last[1]&&last[1]>=large,"64-bit progress incorrect");
    JSONObject metadata=TransferClient.metadata(origin,sent.getString("code"));check(metadata.getJSONArray("files").length()==101,"File count truncated");JSONArray files=metadata.getJSONArray("files");
    for(int i=0;i<files.length();i++){JSONObject file=files.getJSONObject(i);HttpURLConnection c=(HttpURLConnection)new URL(origin+"api/transfers/"+sent.getString("code")+"/files/"+file.getString("id")).openConnection();c.setReadTimeout(90000);MessageDigest actual=MessageDigest.getInstance("SHA-256");long count=0;try(InputStream input=c.getInputStream()){byte[] buffer=new byte[65536];int n;while((n=input.read(buffer))!=-1){count+=n;actual.update(buffer,0,n);}}finally{c.disconnect();}check(count==file.getLong("size"),"Downloaded file truncated");check(hex(actual.digest()).equals(digests.get(i)),"Downloaded bytes changed");}
    TransferClient.json(origin,"api/transfers/"+sent.getString("code"),"DELETE",null,sent.getString("token"),null);
    boolean missing=false;try{TransferClient.metadata(origin,sent.getString("code"));}catch(IOException expectedMissing){missing=true;}check(missing,"Revocation did not remove transfer");
    MessageDigest cancelledDigest=MessageDigest.getInstance("SHA-256");
    TransferClient.Cancellation cancel=new TransferClient.Cancellation();boolean interrupted=false;try{TransferClient.send(origin,Collections.singletonList(new TransferClient.Source("cancel.bin","application/octet-stream",16*1024*1024,()->new Generated(16*1024*1024,cancelledDigest))),(i,bytes,total)->cancel.cancel(),cancel);}catch(InterruptedIOException expectedCancel){interrupted=true;}check(interrupted,"Cancel did not stop upload");
    boolean changed=false;try{TransferClient.send(origin,Collections.singletonList(new TransferClient.Source("changed.bin","application/octet-stream",20,()->new ByteArrayInputStream(new byte[1]))),(i,b,t)->{},new TransferClient.Cancellation());}catch(IOException expectedChanged){changed=true;}check(changed,"Truncated source was accepted");
    System.out.println(new JSONObject().put("files",101).put("largeFileBytes",large).put("sha256",digests.get(100)).put("streaming",true).put("cancel",true).put("sourceChanged",true).put("revoke",true).put("passed",true).toString());
  }
}
