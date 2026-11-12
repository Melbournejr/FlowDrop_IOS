package app.flowdrop.mobile;
public final class ReceiveRoutingHarness {
  private static void route(String name,String mime,String expected){ReceiveFiles.Route actual=ReceiveFiles.route(name,mime);if(!expected.equals(actual.kind))throw new AssertionError(name+": "+actual.kind);if(!("download".equals(expected)?"Download/FlowDrop":"DCIM/FlowDrop").equals(actual.path))throw new AssertionError(actual.path);}
  public static void main(String[] args){
    route("ảnh.JPG","application/octet-stream","image");route("photo.heic","","image");route("movie.MP4","","video");route("camera","image/png","image");route("clip.webm","","video");route("vector.svg","image/svg+xml","download");route("hóa đơn.pdf","","download");route("music.mp3","audio/mpeg","download");route("backup.zip","","download");route("unknown.bin","invalid value","download");
    String name=ReceiveFiles.safeName("../ảnh\\test.jpg");if(name.contains("/")||name.contains("\\"))throw new AssertionError(name);
    StringBuilder longName=new StringBuilder();for(int i=0;i<100;i++)longName.append("Ảnh");longName.append(".jpeg");String shortened=ReceiveFiles.safeName(longName.toString());if(!shortened.endsWith(".jpeg")||shortened.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>190)throw new AssertionError(shortened);
    System.out.println("Android routing passed: photos/videos to DCIM/FlowDrop, other files to Download/FlowDrop, Unicode names and safe paths.");
  }
}
