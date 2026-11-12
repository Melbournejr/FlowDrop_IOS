package app.flowdrop.mobile;

import android.content.Context;
import org.json.*;

/** Compact device-local history, shared by native sending and receiving services. */
public final class TransferHistory {
  public static synchronized JSONArray read(Context context){try{return new JSONArray(context.getSharedPreferences("native-history",0).getString("items","[]"));}catch(Exception e){return new JSONArray();}}
  public static synchronized void sent(Context context,String origin,JSONObject metadata){try{JSONArray files=metadata.getJSONArray("files");long total=0;for(int i=0;i<files.length();i++)total+=files.getJSONObject(i).getLong("size");JSONObject entry=new JSONObject().put("key",origin+metadata.getString("code")+"send").put("origin",origin).put("code",metadata.getString("code")).put("token",metadata.getString("token")).put("direction","send").put("name",files.getJSONObject(0).getString("name")).put("count",files.length()).put("size",total).put("time",System.currentTimeMillis()).put("expiresAt",metadata.getLong("expiresAt"));put(context,entry);}catch(JSONException ignored){}}
  public static synchronized void received(Context context,String origin,String code,String id,String name,String path,String uri,long size){try{put(context,new JSONObject().put("key",origin+code+id).put("origin",origin).put("code",code).put("direction","receive").put("name",name).put("path",path).put("uri",uri).put("count",1).put("size",size).put("time",System.currentTimeMillis()));}catch(JSONException ignored){}}
  private static void put(Context context,JSONObject item)throws JSONException{JSONArray old=read(context),next=new JSONArray();next.put(item);for(int i=0;i<old.length()&&next.length()<50;i++)if(!item.getString("key").equals(old.getJSONObject(i).optString("key")))next.put(old.getJSONObject(i));context.getSharedPreferences("native-history",0).edit().putString("items",next.toString()).apply();}
  public static synchronized void revoked(Context context,String origin,String code){JSONArray items=read(context);for(int i=0;i<items.length();i++){JSONObject item=items.optJSONObject(i);if(item!=null&&origin.equals(item.optString("origin"))&&code.equals(item.optString("code")))try{item.put("revoked",true);}catch(JSONException ignored){}}context.getSharedPreferences("native-history",0).edit().putString("items",items.toString()).apply();}
  private TransferHistory(){}
}
