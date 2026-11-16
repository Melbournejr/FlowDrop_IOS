package app.flowdrop.mobile;
import android.content.Context;
import android.security.keystore.*;
import org.json.JSONObject;
import javax.net.ssl.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.security.cert.X509Certificate;
import java.math.BigInteger;
import java.util.*;
import javax.security.auth.x500.X500Principal;

/** Non-exportable per-install transport key and AES-GCM protected trusted-device store. */
public final class AndroidDeviceVault implements DeviceSecurity.Vault {
  private static final String TLS_ALIAS="flowdrop.transport.identity.v1",STORE_ALIAS="flowdrop.transport.trust.v1";
  private final KeyStore keys;
  private final Path file;
  private final JSONObject trusted;
  private volatile String keyTypes="";
  public String diagnostic(){return "TLS key types="+keyTypes;}
  private void observeKeyType(String type){if(type!=null&&type.matches("[A-Za-z0-9_-]{1,40}")&&keyTypes.length()<200&&!keyTypes.contains(type))keyTypes+=type+",";}
  public AndroidDeviceVault(Context context,String id)throws Exception{
    keys=KeyStore.getInstance("AndroidKeyStore");keys.load(null);file=new File(context.getFilesDir(),"device-transport-trust.gcm").toPath();
    if(!keys.containsAlias(TLS_ALIAS)){Calendar end=Calendar.getInstance();end.add(Calendar.YEAR,5);KeyPairGenerator generator=KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_RSA,"AndroidKeyStore");generator.initialize(new KeyGenParameterSpec.Builder(TLS_ALIAS,KeyProperties.PURPOSE_SIGN|KeyProperties.PURPOSE_VERIFY).setKeySize(2048).setDigests(KeyProperties.DIGEST_NONE,KeyProperties.DIGEST_SHA256,KeyProperties.DIGEST_SHA512).setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1,KeyProperties.SIGNATURE_PADDING_RSA_PSS).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setCertificateSubject(new X500Principal("CN="+DeviceSecurity.identityName(id))).setCertificateSerialNumber(new BigInteger(128,new SecureRandom())).setCertificateNotBefore(new Date(System.currentTimeMillis()-86400000)).setCertificateNotAfter(end.getTime()).build());generator.generateKeyPair();}
    if(!keys.containsAlias(STORE_ALIAS)){if(Files.exists(file))throw new IOException("Không mở được kho tin cậy. Cần ghép nối lại có xác nhận.");KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");generator.init(new KeyGenParameterSpec.Builder(STORE_ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();}
    if(Files.exists(file)){byte[] bytes=Files.readAllBytes(file);if(bytes.length<28||bytes.length>1024*1024)throw new IOException("Kho tin cậy không hợp lệ.");Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,keys.getKey(STORE_ALIAS,null),new GCMParameterSpec(128,Arrays.copyOfRange(bytes,0,12)));cipher.updateAAD("FlowDropTrust1".getBytes(StandardCharsets.UTF_8));trusted=new JSONObject(new String(cipher.doFinal(Arrays.copyOfRange(bytes,12,bytes.length)),StandardCharsets.UTF_8));}else trusted=new JSONObject();
  }
  public JSONObject trusted(){return trusted;}
  public synchronized void save()throws Exception{Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,keys.getKey(STORE_ALIAS,null));cipher.updateAAD("FlowDropTrust1".getBytes(StandardCharsets.UTF_8));byte[] encrypted=cipher.doFinal(trusted.toString().getBytes(StandardCharsets.UTF_8));ByteArrayOutputStream bytes=new ByteArrayOutputStream();bytes.write(cipher.getIV());bytes.write(encrypted);Path tmp=file.resolveSibling(file.getFileName()+".tmp");Files.write(tmp,bytes.toByteArray());Files.move(tmp,file,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}
  public X509Certificate certificate()throws Exception{return (X509Certificate)keys.getCertificate(TLS_ALIAS);}
  public SSLContext context()throws Exception{
    final PrivateKey privateKey=(PrivateKey)keys.getKey(TLS_ALIAS,null);final X509Certificate cert=certificate();
    X509ExtendedKeyManager manager=new X509ExtendedKeyManager(){public String[] getClientAliases(String type,Principal[] issuers){return null;}public String chooseClientAlias(String[] types,Principal[] issuers,java.net.Socket socket){return null;}public String[] getServerAliases(String type,Principal[] issuers){return type.equals("RSA")?new String[]{TLS_ALIAS}:null;}public String chooseServerAlias(String type,Principal[] issuers,java.net.Socket socket){observeKeyType(type);return type.equals("RSA")?TLS_ALIAS:null;}public String chooseEngineServerAlias(String type,Principal[] issuers,SSLEngine engine){observeKeyType(type);return type.equals("RSA")?TLS_ALIAS:null;}public X509Certificate[] getCertificateChain(String alias){return TLS_ALIAS.equals(alias)?new X509Certificate[]{cert}:null;}public PrivateKey getPrivateKey(String alias){return TLS_ALIAS.equals(alias)?privateKey:null;}};
    SSLContext context=SSLContext.getInstance("TLS");context.init(new KeyManager[]{manager},null,new SecureRandom());return context;
  }
}
