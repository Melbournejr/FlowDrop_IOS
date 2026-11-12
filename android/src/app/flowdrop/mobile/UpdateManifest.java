package app.flowdrop.mobile;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import org.json.*;

/** A signed UTF-8 payload avoids cross-platform JSON canonicalization differences. */
public final class UpdateManifest {
  public static final class Entry {
    public final String version,url,sha256;
    public final long versionCode,size;
    Entry(JSONObject value)throws Exception {
      version=value.getString("version");versionCode=value.getLong("versionCode");url=value.getString("url");sha256=value.getString("sha256");size=value.getLong("size");
      if(!(value.get("versionCode") instanceof Number)||!(value.get("size") instanceof Number)||value.getDouble("versionCode")!=versionCode||value.getDouble("size")!=size)throw new IOException("Dung lượng hoặc số phiên bản không hợp lệ.");
      URI target=new URI(url);
      if(!version.matches("[0-9]+\\.[0-9]+\\.[0-9]+")||versionCode<=0||versionCode>Integer.MAX_VALUE||size<=0||size>1024L*1024*1024||!sha256.matches("[a-f0-9]{64}")||!"https".equals(target.getScheme())||target.getHost()==null||target.getUserInfo()!=null)throw new IOException("Thông tin APK cập nhật không hợp lệ.");
    }
    public JSONObject json()throws JSONException{return new JSONObject().put("version",version).put("versionCode",versionCode).put("url",url).put("sha256",sha256).put("size",size);}
  }
  public static Entry verify(String text,String publicKey)throws Exception {
    if(text.getBytes(StandardCharsets.UTF_8).length>100000)throw new IOException("Thông tin cập nhật quá lớn.");
    JSONObject envelope=new JSONObject(text);String payload=envelope.getString("payload");
    byte[] bytes=payload.getBytes(StandardCharsets.UTF_8);if(bytes.length>65536)throw new IOException("Thông tin cập nhật quá lớn.");
    PublicKey key=KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(publicKey)));
    Signature signature=Signature.getInstance("SHA256withRSA");signature.initVerify(key);signature.update(bytes);
    if(!signature.verify(Base64.getDecoder().decode(envelope.getString("signature"))))throw new IOException("Chữ ký thông tin cập nhật không hợp lệ.");
    JSONObject value=new JSONObject(payload);if(!"FlowDrop".equals(value.optString("app"))||value.optInt("schema")!=1)throw new IOException("Không phải bản cập nhật FlowDrop.");
    return new Entry(value.getJSONObject("platforms").getJSONObject("android"));
  }
}
