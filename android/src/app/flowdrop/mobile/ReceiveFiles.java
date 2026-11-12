package app.flowdrop.mobile;
import java.util.Locale;

/** Pure filename/MIME routing shared with JVM tests. */
public final class ReceiveFiles {
  public static final class Route {
    public final String kind,mime,path;
    Route(String kind,String mime,String path){this.kind=kind;this.mime=mime;this.path=path;}
  }
  public static String safeName(String value){
    String name=value.replaceAll("[\\x00-\\x1f\\x7f/\\\\]","_").trim();while(name.endsWith("."))name=name.substring(0,name.length()-1);
    if(name.isEmpty())name="file";int dot=name.lastIndexOf('.');String extension=dot>0?name.substring(dot):"";if(extension.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>40)extension="";String stem=extension.isEmpty()?name:name.substring(0,name.length()-extension.length());StringBuilder result=new StringBuilder();for(int i=0;i<stem.length();){int p=stem.codePointAt(i);String next=new String(Character.toChars(p));if((result.toString()+next+extension).getBytes(java.nio.charset.StandardCharsets.UTF_8).length>190)break;result.append(next);i+=Character.charCount(p);}return (result.length()==0?"file":result.toString())+extension;
  }
  public static Route route(String name,String supplied){
    String lower=name.toLowerCase(Locale.ROOT),mime=supplied==null?"":supplied.toLowerCase(Locale.ROOT).split(";",2)[0].trim();
    int dot=lower.lastIndexOf('.');String extension=dot<0?"":lower.substring(dot+1);
    switch(extension){
      case "jpg":case "jpeg":mime="image/jpeg";break;case "png":mime="image/png";break;case "gif":mime="image/gif";break;case "webp":mime="image/webp";break;case "bmp":mime="image/bmp";break;case "heic":mime="image/heic";break;case "heif":mime="image/heif";break;case "avif":mime="image/avif";break;
      case "mp4":case "m4v":mime="video/mp4";break;case "3gp":mime="video/3gpp";break;case "webm":mime="video/webm";break;case "mkv":mime="video/x-matroska";break;case "mov":mime="video/quicktime";break;
      case "pdf":mime="application/pdf";break;case "txt":mime="text/plain";break;case "zip":mime="application/zip";break;case "mp3":mime="audio/mpeg";break;case "svg":mime="image/svg+xml";break;
      default:break;
    }
    if(mime.startsWith("image/")&&!mime.equals("image/svg+xml"))return new Route("image",mime,"DCIM/FlowDrop");
    if(mime.startsWith("video/"))return new Route("video",mime,"DCIM/FlowDrop");
    if(!mime.matches("[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+"))mime="application/octet-stream";
    return new Route("download",mime,"Download/FlowDrop");
  }
}
