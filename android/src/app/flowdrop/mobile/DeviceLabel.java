package app.flowdrop.mobile;
/** Friendly display names do not replace the persistent device ID. */
public final class DeviceLabel {
  public static String validate(String value){
    if(value==null)throw new IllegalArgumentException("Tên thiết bị cần từ 1 đến 50 ký tự.");
    for(int i=0;i<value.length();i++){char c=value.charAt(i);if(c<32||c==127||c==0x2028||c==0x2029)throw new IllegalArgumentException("Tên thiết bị không được chứa ký tự điều khiển.");}
    String name=value.trim();if(name.isEmpty()||name.codePointCount(0,name.length())>50)throw new IllegalArgumentException("Tên thiết bị cần từ 1 đến 50 ký tự.");return name;
  }
  public static String serviceName(String value){StringBuilder out=new StringBuilder();for(int i=0;i<value.length();){int cp=value.codePointAt(i);String next=new String(Character.toChars(cp));if((out.toString()+next).getBytes(java.nio.charset.StandardCharsets.UTF_8).length>45)break;out.append(next);i+=Character.charCount(cp);}return "FlowDrop - "+out.toString().replace('.',' ');}
}
