package app.flowdrop.mobile;
import org.json.*;
import java.util.*;
import java.util.function.Consumer;

/** Typed, bounded events only; no network identifiers, credentials or errors. */
public final class LinkDiagnostics {
  public enum Event {HOST_START,HOST_STOP,CREATE_REQUEST,CREATE_ACCEPTED,CREATE_FAILED,GROUP_READY,
    GROUP_QUERY_EMPTY,GROUP_LOST,QUERY_TIMEOUT,API_FAILURE,CHANNEL_LOST,CHANNEL_REOPEN,
    RECOVERY_REQUEST,RECOVERY_EXHAUSTED,FOREIGN_GROUP,STOP_REQUEST,REMOVE_REQUEST,REMOVE_FAILED,REMOVED,LATE_CLEANUP}
  private final ArrayDeque<JSONObject> rows=new ArrayDeque<>();
  private Consumer<String> sink;
  public LinkDiagnostics(){this("");}
  public LinkDiagnostics(String previous){
    if(previous==null||previous.length()>16384)return;
    try{JSONArray old=new JSONArray(previous);for(int i=Math.max(0,old.length()-64);i<old.length();i++){
      JSONObject row=old.getJSONObject(i);Event type=Event.valueOf(row.getString("event"));
      rows.add(new JSONObject().put("timeMs",row.getLong("timeMs")).put("event",type.name()).put("detail",row.optInt("detail")));
    }}catch(Exception ignored){rows.clear();}
  }
  public synchronized void sink(Consumer<String> output){sink=output;}
  public synchronized void event(Event event,int detail){try{
    rows.add(new JSONObject().put("timeMs",System.currentTimeMillis()).put("event",event.name()).put("detail",detail));
    while(rows.size()>64)rows.removeFirst();if(sink!=null)sink.accept(report().toString());
  }catch(Exception ignored){}}
  public synchronized JSONArray report(){try{JSONArray out=new JSONArray();for(JSONObject row:rows)out.put(new JSONObject(row.toString()));return out;}catch(Exception ignored){return new JSONArray();}}
}
