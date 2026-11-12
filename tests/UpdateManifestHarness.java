package app.flowdrop.mobile;
import java.nio.file.*;
public final class UpdateManifestHarness {
 public static void main(String[] args)throws Exception {
  if(args[0].equals("manifest")){UpdateManifest.Entry entry=UpdateManifest.verify(new String(Files.readAllBytes(Paths.get(args[1])),"UTF-8"),args[2]);System.out.println(entry.json());return;}
  CodeLookup.Found found=CodeLookup.find(args[1],java.util.Arrays.asList(args).subList(3,args.length),args[2],url->(java.net.HttpURLConnection)url.openConnection());
  System.out.println(new org.json.JSONObject().put("origin",found.origin).put("metadata",found.metadata));
 }
}
