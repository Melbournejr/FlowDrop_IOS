#pragma once
#include <ws2bth.h>
#include <bluetoothapis.h>
#include <optional>
#include <regex>

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
inline std::optional<BTH_ADDR> choose(HWND owner){
  SystemDll library(L"bthprops.cpl");
  auto first=(decltype(&BluetoothFindFirstDevice))GetProcAddress(library.h,"BluetoothFindFirstDevice");
  auto next=(decltype(&BluetoothFindNextDevice))GetProcAddress(library.h,"BluetoothFindNextDevice");
  auto finish=(decltype(&BluetoothFindDeviceClose))GetProcAddress(library.h,"BluetoothFindDeviceClose");
  if(!first||!next||!finish)throw std::runtime_error("Bluetooth API không đầy đủ.");
  BLUETOOTH_DEVICE_SEARCH_PARAMS p{};p.dwSize=sizeof(p);p.fReturnAuthenticated=TRUE;p.fReturnRemembered=TRUE;p.fIssueInquiry=FALSE;
  BLUETOOTH_DEVICE_INFO d{};d.dwSize=sizeof(d);auto find=first(&p,&d);
  if(!find){MessageBoxW(owner,L"Bật Bluetooth, ghép đôi điện thoại với Windows trong Cài đặt, rồi tạo Turbo và bật chờ Bluetooth trong FlowDrop trên điện thoại.",L"FlowDrop · Bluetooth",MB_OK|MB_ICONINFORMATION);return {};}
  std::optional<BTH_ADDR> selected;unsigned count=0;
  do{if(!d.fAuthenticated)continue;std::wstring name=d.szName;for(auto& c:name)if(c<32||c==127)c=L' ';if(name.size()>80)name.resize(80);
    auto message=L"Kết nối với thiết bị Bluetooth đã ghép đôi: "+name+L"?\n\nTrên điện thoại: Tạo Turbo → Kết nối Windows qua Bluetooth, rồi cho phép yêu cầu. Windows sẽ chuyển từ mạng Wi-Fi hiện tại sang mạng riêng của điện thoại.\n\nCó: kết nối. Không: thiết bị tiếp theo. Hủy: đóng.";
    int answer=MessageBoxW(owner,message.c_str(),L"FlowDrop · Kết nối trực tiếp",MB_YESNOCANCEL|MB_ICONQUESTION|MB_DEFBUTTON3);
    if(answer==IDYES){selected=d.Address.ullLong;break;}if(answer==IDCANCEL)break;
  }while(++count<32&&next(find,&d));finish(find);return selected;
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
inline void join(const json& value){
  validate(value);std::string ssid=value["ssid"],pass=value["passphrase"];std::wstring hex;const wchar_t* digits=L"0123456789ABCDEF";for(unsigned char c:ssid){hex+=digits[c>>4];hex+=digits[c&15];}
  // Inputs are restricted ASCII; no credentials enter shell argv, logs, files,
  // saved WLAN profiles, or the FlowDrop trust store.
  std::wstring xml=L"<?xml version=\"1.0\"?><WLANProfile xmlns=\"http://www.microsoft.com/networking/WLAN/profile/v1\"><name>FlowDrop temporary</name><SSIDConfig><SSID><hex>"+hex+L"</hex></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>manual</connectionMode><MSM><security><authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption><sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>"+wide(pass)+L"</keyMaterial></sharedKey></security></MSM></WLANProfile>";
  Wlan wlan;DWORD version;if(wlan.open(2,nullptr,&version,&wlan.h)!=ERROR_SUCCESS)throw std::runtime_error("Không mở được Wi-Fi API.");WlanMemory memory(wlan.freeMemory);if(wlan.enumerate(wlan.h,nullptr,(PWLAN_INTERFACE_INFO_LIST*)&memory.p)!=ERROR_SUCCESS||!memory.p)throw std::runtime_error("Không tìm thấy Wi-Fi adapter.");auto list=(PWLAN_INTERFACE_INFO_LIST)memory.p;if(list->dwNumberOfItems!=1)throw std::runtime_error("Cần một Wi-Fi adapter hoạt động; nhiều adapter cần chọn mạng thủ công.");auto guid=list->InterfaceInfo[0].InterfaceGuid;
  WLAN_CONNECTION_PARAMETERS p{};p.wlanConnectionMode=wlan_connection_mode_temporary_profile;p.strProfile=xml.c_str();p.dot11BssType=dot11_BSS_type_infrastructure;
  DWORD result=wlan.connect(wlan.h,&guid,&p,nullptr);SecureZeroMemory(xml.data(),xml.size()*sizeof(wchar_t));SecureZeroMemory(pass.data(),pass.size());if(result!=ERROR_SUCCESS)throw std::runtime_error("Windows chưa cho phép kết nối Wi-Fi. Kiểm tra quyền vị trí/Wi-Fi trong Cài đặt.");
  for(int n=0;n<60;n++){DWORD size=0;WLAN_OPCODE_VALUE_TYPE type;WlanMemory current(wlan.freeMemory);if(wlan.query(wlan.h,&guid,wlan_intf_opcode_current_connection,nullptr,&size,&current.p,&type)==ERROR_SUCCESS&&current.p){auto a=(PWLAN_CONNECTION_ATTRIBUTES)current.p;if(a->isState==wlan_interface_state_connected&&a->wlanAssociationAttributes.dot11Ssid.uSSIDLength==ssid.size()&&memcmp(a->wlanAssociationAttributes.dot11Ssid.ucSSID,ssid.data(),ssid.size())==0)return;}Sleep(500);}
  throw std::runtime_error("Chưa xác nhận được Windows vào mạng Turbo. Kiểm tra danh sách Wi-Fi; không cần Internet.");
}
}
