#pragma once
#include <ws2bth.h>
#include <bluetoothapis.h>
#include <optional>
#include <regex>
#include <atomic>
#include <functional>
#include <mutex>
#include <iphlpapi.h>
#include <ws2tcpip.h>

// Setup only. RFCOMM is authenticated/encrypted by the OS bond; Wi-Fi file
// transport still requires the existing independent FlowDrop TLS pairing.
namespace fdlink {
struct Winsock { Winsock(){WSADATA d;if(WSAStartup(MAKEWORD(2,2),&d))throw std::runtime_error("Không mở được Bluetooth socket.");} ~Winsock(){WSACleanup();} };
struct Socket { SOCKET s=INVALID_SOCKET;~Socket(){if(s!=INVALID_SOCKET)closesocket(s);} };
struct SystemDll { HMODULE h;explicit SystemDll(const wchar_t* name):h(LoadLibraryExW(name,nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32)){if(!h)throw std::runtime_error("Hệ điều hành chưa hỗ trợ Bluetooth/Wi-Fi API cần thiết.");}~SystemDll(){FreeLibrary(h);} };
struct Wlan {
  SystemDll library{L"wlanapi.dll"};HANDLE h=nullptr;
  decltype(&WlanOpenHandle) open=(decltype(open))GetProcAddress(library.h,"WlanOpenHandle");
  decltype(&WlanCloseHandle) close=(decltype(close))GetProcAddress(library.h,"WlanCloseHandle");
  decltype(&WlanEnumInterfaces) enumerate=(decltype(enumerate))GetProcAddress(library.h,"WlanEnumInterfaces");
  decltype(&WlanFreeMemory) freeMemory=(decltype(freeMemory))GetProcAddress(library.h,"WlanFreeMemory");
  decltype(&WlanConnect) connect=(decltype(connect))GetProcAddress(library.h,"WlanConnect");
  decltype(&WlanQueryInterface) query=(decltype(query))GetProcAddress(library.h,"WlanQueryInterface");
  Wlan(){if(!open||!close||!enumerate||!freeMemory||!connect||!query)throw std::runtime_error("Wi-Fi API không đầy đủ.");}
  ~Wlan(){if(h)close(h,nullptr);}
};
struct WlanMemory { void* p=nullptr;decltype(&WlanFreeMemory) freeMemory;explicit WlanMemory(decltype(freeMemory) f):freeMemory(f){}~WlanMemory(){if(p)freeMemory(p);} };
#ifndef FLOWDROP_PREVIEW_BUILD
#define FLOWDROP_PREVIEW_BUILD "source"
#endif
inline std::atomic<unsigned> sessionGeneration{0};
inline std::atomic<bool> monitoring{false};
inline std::atomic<int> monitorPhase{0};
inline std::mutex joinedMutex;
inline GUID joinedInterface{};
inline bool joinedKnown=false;
inline std::string joinedSsid;
// DHCP gateway is a location hint for the Android group owner, never TLS trust.
inline std::string directGateway(){
  if(!monitoring.load())return {};GUID wanted;std::string expected;{std::lock_guard<std::mutex> lock(joinedMutex);if(!joinedKnown)return {};wanted=joinedInterface;expected=joinedSsid;}
  wchar_t wideGuid[40]{};if(!StringFromGUID2(wanted,wideGuid,40))return {};std::string guid;for(wchar_t c:wideGuid){if(!c)break;guid+=(char)c;}
  try{Wlan wlan;DWORD version,size=0;WLAN_OPCODE_VALUE_TYPE type;if(wlan.open(2,nullptr,&version,&wlan.h)!=ERROR_SUCCESS)return {};WlanMemory current(wlan.freeMemory);if(wlan.query(wlan.h,&wanted,wlan_intf_opcode_current_connection,nullptr,&size,&current.p,&type)!=ERROR_SUCCESS||!current.p)return {};auto association=(PWLAN_CONNECTION_ATTRIBUTES)current.p;if(association->isState!=wlan_interface_state_connected||association->wlanAssociationAttributes.dot11Ssid.uSSIDLength!=expected.size()||memcmp(association->wlanAssociationAttributes.dot11Ssid.ucSSID,expected.data(),expected.size()))return {};
    SystemDll dll(L"iphlpapi.dll");auto adapters=(decltype(&GetAdaptersAddresses))GetProcAddress(dll.h,"GetAdaptersAddresses");if(!adapters)return {};ULONG bytes=16384;std::vector<unsigned char> buffer;
    for(int attempt=0;attempt<3&&bytes<=1024*1024;attempt++){buffer.resize(bytes);auto list=(PIP_ADAPTER_ADDRESSES)buffer.data();ULONG result=adapters(AF_INET,GAA_FLAG_INCLUDE_GATEWAYS|GAA_FLAG_SKIP_ANYCAST|GAA_FLAG_SKIP_MULTICAST|GAA_FLAG_SKIP_DNS_SERVER,nullptr,list,&bytes);if(result==ERROR_BUFFER_OVERFLOW)continue;if(result!=NO_ERROR)return {};
      for(auto p=list;p;p=p->Next)if(p->AdapterName&&!_stricmp(p->AdapterName,guid.c_str())&&p->OperStatus==IfOperStatusUp){for(auto g=p->FirstGatewayAddress;g;g=g->Next)if(g->Address.lpSockaddr&&g->Address.lpSockaddr->sa_family==AF_INET){char ip[INET_ADDRSTRLEN]{};auto address=&((sockaddr_in*)g->Address.lpSockaddr)->sin_addr;if(InetNtopA(AF_INET,address,ip,sizeof(ip))&&strcmp(ip,"0.0.0.0")&&strncmp(ip,"127.",4))return ip;}}break;
    }
  }catch(...){}return {};
}
inline int directPeerIndex(const json& peers,const std::string& gateway){
  if(gateway.empty()||!peers.is_array())return -1;int found=-1;std::regex url("^https?://([0-9.]+):([0-9]{1,5})/?$");
  for(size_t i=0;i<peers.size();i++){if(!peers[i].is_object()||!peers[i].contains("url")||!peers[i]["url"].is_string())continue;std::smatch match;auto value=peers[i]["url"].get<std::string>();if(std::regex_match(value,match,url)&&match[1].str()==gateway){auto port=std::stoul(match[2].str());if(port==0||port>65535)continue;if(found>=0)return -2;found=(int)i;}}return found;
}
inline void stopRecovery(){sessionGeneration++;monitoring=false;monitorPhase=4;}
// A connected different SSID is respected, never forcibly replaced by recovery.
inline int recoveryAction(bool connected,bool expected,unsigned misses,unsigned attempts,bool due=true){if(connected)return expected?0:3;if(attempts>=2)return 2;return misses>=3&&due?1:0;}
inline json diagnostics(){
  json out={{"appVersion","1.14.0"},{"build",FLOWDROP_PREVIEW_BUILD},{"wifi",json::array()},{"recoveryPhase",monitorPhase.load()},{"recoveryActive",monitoring.load()}};
  try{Wlan wlan;DWORD version;if(wlan.open(2,nullptr,&version,&wlan.h)!=ERROR_SUCCESS)return out;WlanMemory memory(wlan.freeMemory);if(wlan.enumerate(wlan.h,nullptr,(PWLAN_INTERFACE_INFO_LIST*)&memory.p)!=ERROR_SUCCESS||!memory.p)return out;
    auto list=(PWLAN_INTERFACE_INFO_LIST)memory.p;out["interfaceCount"]=list->dwNumberOfItems;for(DWORD i=0;i<list->dwNumberOfItems&&i<8;i++){DWORD size=0;WLAN_OPCODE_VALUE_TYPE type;WlanMemory current(wlan.freeMemory);DWORD result=wlan.query(wlan.h,&list->InterfaceInfo[i].InterfaceGuid,wlan_intf_opcode_current_connection,nullptr,&size,&current.p,&type);json row={{"state",(int)list->InterfaceInfo[i].isState},{"queryResult",result}};
      if(result==ERROR_SUCCESS&&current.p){auto c=(PWLAN_CONNECTION_ATTRIBUTES)current.p;row["receiveKbps"]=c->wlanAssociationAttributes.ulRxRate;row["transmitKbps"]=c->wlanAssociationAttributes.ulTxRate;row["signalPercent"]=c->wlanAssociationAttributes.wlanSignalQuality;row["phyType"]=(int)c->wlanAssociationAttributes.dot11PhyType;}out["wifi"].push_back(row);}
  }catch(...){out["wifiApiAvailable"]=false;}return out;
}
inline void copyDiagnostics(HWND owner){
  auto data=wide(diagnostics().dump(2));if(!OpenClipboard(owner))return;HGLOBAL buffer=GlobalAlloc(GMEM_MOVEABLE,(data.size()+1)*sizeof(wchar_t));if(!buffer){CloseClipboard();return;}
  void* target=GlobalLock(buffer);if(!target){GlobalFree(buffer);CloseClipboard();return;}memcpy(target,data.c_str(),(data.size()+1)*sizeof(wchar_t));GlobalUnlock(buffer);EmptyClipboard();if(!SetClipboardData(CF_UNICODETEXT,buffer))GlobalFree(buffer);CloseClipboard();
  MessageBoxW(owner,L"Đã sao chép chẩn đoán Wi-Fi. Không có tên mạng, địa chỉ IP/MAC, mật khẩu hoặc mã ghép nối.",L"FlowDrop",MB_OK|MB_ICONINFORMATION);
}
inline std::optional<BTH_ADDR> choose(HWND owner){
  std::vector<BTH_ADDR> addresses;std::vector<std::wstring> names;addresses.reserve(32);names.reserve(32);
  try{SystemDll library(L"bthprops.cpl");auto first=(decltype(&BluetoothFindFirstDevice))GetProcAddress(library.h,"BluetoothFindFirstDevice");auto next=(decltype(&BluetoothFindNextDevice))GetProcAddress(library.h,"BluetoothFindNextDevice");auto finish=(decltype(&BluetoothFindDeviceClose))GetProcAddress(library.h,"BluetoothFindDeviceClose");
    if(first&&next&&finish){BLUETOOTH_DEVICE_SEARCH_PARAMS p{};p.dwSize=sizeof(p);p.fReturnAuthenticated=TRUE;p.fReturnRemembered=TRUE;p.fIssueInquiry=FALSE;BLUETOOTH_DEVICE_INFO d{};d.dwSize=sizeof(d);auto find=first(&p,&d);
      if(find){do{if(!d.fAuthenticated)continue;std::wstring name(d.szName,wcsnlen(d.szName,BLUETOOTH_MAX_NAME_SIZE));for(auto& c:name)if(c<32||c==127)c=L' ';if(name.size()>80)name.resize(80);addresses.push_back(d.Address.ullLong);names.push_back(name+L"\nKết nối trực tiếp với điện thoại này");}while(names.size()<32&&next(find,&d));finish(find);}
    }
  }catch(...){ }
  std::vector<TASKDIALOG_BUTTON> buttons;for(size_t i=0;i<names.size();i++)buttons.push_back({5000+(int)i,names[i].c_str()});
  buttons.push_back({6001,L"Ghép đôi Bluetooth lần đầu\nMở Cài đặt Bluetooth của Windows"});buttons.push_back({6002,L"Mobile Hotspot thủ công"});buttons.push_back({6003,L"Sao chép chẩn đoán Wi-Fi"});buttons.push_back({6004,L"Auto / LAN\nGiữ mạng hiện tại"});if(monitoring.load())buttons.push_back({6005,L"Dừng tự nối lại\nGiữ nguyên Wi-Fi hiện tại"});
  TASKDIALOGCONFIG config{};config.cbSize=sizeof(config);config.hwndParent=owner;config.dwFlags=TDF_USE_COMMAND_LINKS|TDF_ALLOW_DIALOG_CANCELLATION;config.dwCommonButtons=TDCBF_CANCEL_BUTTON;
  config.pszWindowTitle=L"FlowDrop · Kết nối trực tiếp";config.pszMainInstruction=names.empty()?L"Ghép đôi Bluetooth để kết nối":L"Chọn điện thoại để kết nối";
  config.pszContent=L"Trên điện thoại, mở FlowDrop và bấm Kết nối trực tiếp với máy tính. Chọn điện thoại bên dưới, rồi cho phép trên điện thoại. Windows sẽ chuyển sang mạng Wi-Fi riêng và thử nối lại tối đa 2 lần nếu mạng bị rớt. Dừng tự nối lại trong cửa sổ này; file vẫn cần ghép nối bảo mật FlowDrop.";
  config.cButtons=(UINT)buttons.size();config.pButtons=buttons.data();config.nDefaultButton=IDCANCEL;int selected=IDCANCEL;
  if(FAILED(TaskDialogIndirect(&config,&selected,nullptr,nullptr)))throw std::runtime_error("Chưa mở được cửa sổ kết nối.");
  if(selected>=5000&&selected<5000+(int)addresses.size())return addresses[selected-5000];
  if(selected==6001)ShellExecuteW(owner,L"open",L"ms-settings:bluetooth",nullptr,nullptr,SW_SHOWNORMAL);
  if(selected==6002)ShellExecuteW(owner,L"open",L"ms-settings:network-mobilehotspot",nullptr,nullptr,SW_SHOWNORMAL);
  if(selected==6003)copyDiagnostics(owner);if(selected==6005)stopRecovery();return {};
}
inline void validate(const json& value){
  if(!value.is_object()||value.size()!=3||!value.contains("protocol")||!value["protocol"].is_string()||value["protocol"]!="FlowDropLink1"||!value.contains("ssid")||!value["ssid"].is_string()||!value.contains("passphrase")||!value["passphrase"].is_string())throw std::runtime_error("Thông tin mạng Bluetooth không hợp lệ.");
  if(!std::regex_match(value["ssid"].get<std::string>(),std::regex("DIRECT-fd-FlowDrop-[a-f0-9]{8}"))||!std::regex_match(value["passphrase"].get<std::string>(),std::regex("[a-f0-9]{20}")))throw std::runtime_error("Từ chối thông tin mạng không phải Turbo FlowDrop.");
}
inline json receive(BTH_ADDR address){
  Winsock w;Socket sock;sock.s=socket(AF_BTH,SOCK_STREAM,BTHPROTO_RFCOMM);if(sock.s==INVALID_SOCKET)throw std::runtime_error("Không mở được Bluetooth. Kiểm tra adapter và quyền hệ điều hành.");
  BOOL enabled=TRUE;if(setsockopt(sock.s,SOL_RFCOMM,SO_BTH_AUTHENTICATE,(char*)&enabled,sizeof(enabled))||setsockopt(sock.s,SOL_RFCOMM,SO_BTH_ENCRYPT,(char*)&enabled,sizeof(enabled)))throw std::runtime_error("Không bật được kênh Bluetooth mã hóa; đã hủy.");
  SOCKADDR_BTH target{};target.addressFamily=AF_BTH;target.btAddr=address;target.serviceClassId={0xf568a2ec,0x7d09,0x4bf7,{0x93,0xb4,0x23,0x49,0x12,0xf5,0xc2,0x6a}};target.port=0;
  u_long nonblock=1;if(ioctlsocket(sock.s,FIONBIO,&nonblock))throw std::runtime_error("Không cấu hình được Bluetooth.");
  if(connect(sock.s,(sockaddr*)&target,sizeof(target))==SOCKET_ERROR){int error=WSAGetLastError();if(error!=WSAEWOULDBLOCK&&error!=WSAEINPROGRESS)throw std::runtime_error("Chưa kết nối được. Bật chờ Bluetooth trong FlowDrop trên điện thoại.");fd_set writes,errors;FD_ZERO(&writes);FD_ZERO(&errors);FD_SET(sock.s,&writes);FD_SET(sock.s,&errors);timeval wait{20,0};if(select(0,nullptr,&writes,&errors,&wait)<=0||FD_ISSET(sock.s,&errors))throw std::runtime_error("Hết thời gian kết nối Bluetooth.");int result=0,size=sizeof(result);if(getsockopt(sock.s,SOL_SOCKET,SO_ERROR,(char*)&result,&size)||result)throw std::runtime_error("Bluetooth từ chối kết nối.");}
  nonblock=0;if(ioctlsocket(sock.s,FIONBIO,&nonblock))throw std::runtime_error("Không cấu hình được Bluetooth.");DWORD timeout=35000;if(setsockopt(sock.s,SOL_SOCKET,SO_RCVTIMEO,(char*)&timeout,sizeof(timeout))||setsockopt(sock.s,SOL_SOCKET,SO_SNDTIMEO,(char*)&timeout,sizeof(timeout)))throw std::runtime_error("Không thiết lập được timeout Bluetooth.");
  const std::string hello="FlowDropLink1\n";for(size_t n=0;n<hello.size();){int sent=send(sock.s,hello.data()+n,(int)(hello.size()-n),0);if(sent<=0)throw std::runtime_error("Mất kết nối Bluetooth.");n+=sent;}
  std::string body;const ULONGLONG deadline=GetTickCount64()+35000;
  for(;;){if(GetTickCount64()>deadline)throw std::runtime_error("Hết thời gian nhận thông tin mạng.");char c;int n=recv(sock.s,&c,1,0);if(n!=1)throw std::runtime_error("Chưa được cho phép trên điện thoại hoặc Bluetooth đã ngắt.");if(c=='\n')break;if(body.size()>=2048)throw std::runtime_error("Phản hồi Bluetooth quá dài.");body.push_back(c);}
  auto value=json::parse(body,nullptr,false);validate(value);return value;
}
inline void join(const json& value,unsigned lease=0,bool allowSwitch=true){
  validate(value);std::string ssid=value["ssid"],pass=value["passphrase"];std::wstring hex;const wchar_t* digits=L"0123456789ABCDEF";for(unsigned char c:ssid){hex+=digits[c>>4];hex+=digits[c&15];}
  // Inputs are restricted ASCII; no credentials enter shell argv, logs, files,
  // saved WLAN profiles, or the FlowDrop trust store.
  std::wstring xml=L"<?xml version=\"1.0\"?><WLANProfile xmlns=\"http://www.microsoft.com/networking/WLAN/profile/v1\"><name>FlowDrop temporary</name><SSIDConfig><SSID><hex>"+hex+L"</hex></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>manual</connectionMode><MSM><security><authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption><sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>"+wide(pass)+L"</keyMaterial></sharedKey></security></MSM></WLANProfile>";
  Wlan wlan;DWORD version;if(wlan.open(2,nullptr,&version,&wlan.h)!=ERROR_SUCCESS)throw std::runtime_error("Không mở được Wi-Fi API.");WlanMemory memory(wlan.freeMemory);if(wlan.enumerate(wlan.h,nullptr,(PWLAN_INTERFACE_INFO_LIST*)&memory.p)!=ERROR_SUCCESS||!memory.p)throw std::runtime_error("Không tìm thấy Wi-Fi adapter.");auto list=(PWLAN_INTERFACE_INFO_LIST)memory.p;if(list->dwNumberOfItems!=1)throw std::runtime_error("Cần một Wi-Fi adapter hoạt động; nhiều adapter cần chọn mạng thủ công.");auto guid=list->InterfaceInfo[0].InterfaceGuid;
  WLAN_CONNECTION_PARAMETERS p{};p.wlanConnectionMode=wlan_connection_mode_temporary_profile;p.strProfile=xml.c_str();p.dot11BssType=dot11_BSS_type_infrastructure;
  if(lease&&sessionGeneration.load()!=lease)throw std::runtime_error("Đã hủy kết nối trực tiếp.");
  if(!allowSwitch){DWORD size=0;WLAN_OPCODE_VALUE_TYPE type;WlanMemory observed(wlan.freeMemory);if(wlan.query(wlan.h,&guid,wlan_intf_opcode_current_connection,nullptr,&size,&observed.p,&type)==ERROR_SUCCESS&&observed.p){auto a=(PWLAN_CONNECTION_ATTRIBUTES)observed.p;if(a->isState==wlan_interface_state_connected&&(a->wlanAssociationAttributes.dot11Ssid.uSSIDLength!=ssid.size()||memcmp(a->wlanAssociationAttributes.dot11Ssid.ucSSID,ssid.data(),ssid.size())!=0))throw std::runtime_error("Windows đã chuyển mạng.");}}
  DWORD result=wlan.connect(wlan.h,&guid,&p,nullptr);SecureZeroMemory(xml.data(),xml.size()*sizeof(wchar_t));SecureZeroMemory(pass.data(),pass.size());if(result!=ERROR_SUCCESS)throw std::runtime_error("Windows chưa cho phép kết nối Wi-Fi. Kiểm tra quyền vị trí/Wi-Fi trong Cài đặt.");
  for(int n=0;n<60;n++){if(lease&&sessionGeneration.load()!=lease)throw std::runtime_error("Đã hủy kết nối trực tiếp.");DWORD size=0;WLAN_OPCODE_VALUE_TYPE type;WlanMemory current(wlan.freeMemory);if(wlan.query(wlan.h,&guid,wlan_intf_opcode_current_connection,nullptr,&size,&current.p,&type)==ERROR_SUCCESS&&current.p){auto a=(PWLAN_CONNECTION_ATTRIBUTES)current.p;if(a->isState==wlan_interface_state_connected&&a->wlanAssociationAttributes.dot11Ssid.uSSIDLength==ssid.size()&&memcmp(a->wlanAssociationAttributes.dot11Ssid.ucSSID,ssid.data(),ssid.size())==0){std::lock_guard<std::mutex> lock(joinedMutex);joinedInterface=guid;joinedSsid=ssid;joinedKnown=true;return;}}Sleep(500);}
  throw std::runtime_error("Chưa xác nhận được Windows vào mạng Turbo. Kiểm tra danh sách Wi-Fi; không cần Internet.");
}
inline void monitor(const json& value,unsigned lease,const std::function<void(int)>& notify){
  if(sessionGeneration.load()!=lease)return;const std::string ssid=value.at("ssid");unsigned misses=0,attempts=0;ULONGLONG nextAttempt=0;monitoring=true;monitorPhase=0;
  try{Wlan wlan;DWORD version;if(wlan.open(2,nullptr,&version,&wlan.h)!=ERROR_SUCCESS)throw std::runtime_error("WLAN unavailable");WlanMemory interfaces(wlan.freeMemory);if(wlan.enumerate(wlan.h,nullptr,(PWLAN_INTERFACE_INFO_LIST*)&interfaces.p)!=ERROR_SUCCESS||!interfaces.p)throw std::runtime_error("WLAN unavailable");auto list=(PWLAN_INTERFACE_INFO_LIST)interfaces.p;if(list->dwNumberOfItems!=1)throw std::runtime_error("WLAN changed");auto guid=list->InterfaceInfo[0].InterfaceGuid;
    while(sessionGeneration.load()==lease){Sleep(1000);if(sessionGeneration.load()!=lease)break;DWORD size=0;WLAN_OPCODE_VALUE_TYPE type;WlanMemory observed(wlan.freeMemory);bool connected=false,expected=false;
      if(wlan.query(wlan.h,&guid,wlan_intf_opcode_current_connection,nullptr,&size,&observed.p,&type)==ERROR_SUCCESS&&observed.p){auto a=(PWLAN_CONNECTION_ATTRIBUTES)observed.p;connected=a->isState==wlan_interface_state_connected;expected=a->wlanAssociationAttributes.dot11Ssid.uSSIDLength==ssid.size()&&memcmp(a->wlanAssociationAttributes.dot11Ssid.ucSSID,ssid.data(),ssid.size())==0;}
      misses=connected?0:misses+1;int action=recoveryAction(connected,expected,misses,attempts,GetTickCount64()>=nextAttempt);
      if(action==3){monitorPhase=3;notify(3);break;}if(action==2){monitorPhase=2;notify(2);break;}
      if(action==1){attempts++;nextAttempt=GetTickCount64()+10000;monitorPhase=1;notify(1);try{join(value,lease,false);misses=0;monitorPhase=0;notify(0);}catch(...){nextAttempt=GetTickCount64()+10000;if(sessionGeneration.load()!=lease)break;}}
    }
  }catch(...){if(sessionGeneration.load()==lease){monitorPhase=2;notify(2);}}
  if(sessionGeneration.load()==lease)monitoring=false;
}

}
