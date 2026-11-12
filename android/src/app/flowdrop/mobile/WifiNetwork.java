package app.flowdrop.mobile;

import android.content.Context;
import android.net.*;
import java.net.*;
import java.util.*;

/** Keep discovery and its confirmation requests on Wi-Fi, including when cellular/VPN is default. */
public final class WifiNetwork {
  private WifiNetwork(){}
  public static Network find(Context context){
    ConnectivityManager manager=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);if(manager==null)return null;
    for(Network network:manager.getAllNetworks()){NetworkCapabilities caps=manager.getNetworkCapabilities(network);if(caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)&&!caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN))return network;}return null;
  }
  public static HttpURLConnection open(Context context,URL url)throws Exception{
    String host=url.getHost();if("127.0.0.1".equals(host)||"localhost".equalsIgnoreCase(host)||"::1".equals(host))return (HttpURLConnection)url.openConnection();
    Network network=find(context);return (HttpURLConnection)(network==null?url.openConnection():network.openConnection(url));
  }
  public static List<NetworkInterface> interfaces(Context context,Network network)throws Exception{
    ConnectivityManager manager=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);LinkProperties links=manager==null?null:manager.getLinkProperties(network);
    if(links==null||links.getInterfaceName()==null)return Collections.emptyList();NetworkInterface iface=NetworkInterface.getByName(links.getInterfaceName());return iface==null?Collections.emptyList():Collections.singletonList(iface);
  }
}
