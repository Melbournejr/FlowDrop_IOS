#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define NOMINMAX
#include <windows.h>
#include <commctrl.h>
#include <shobjidl.h>
#include <shlobj.h>
#include <shellapi.h>
#include <winhttp.h>
#include <uxtheme.h>
#include <filesystem>
#include <string>
#include <vector>
#include <thread>
#include <memory>
#include <functional>
#include <stdexcept>
#include <atomic>
#include "json.hpp"

using json = nlohmann::json;
namespace fs = std::filesystem;
constexpr UINT UI_EVENT = WM_APP + 1;
constexpr UINT UI_CLOSE = WM_APP + 2;
constexpr wchar_t CLASS_NAME[] = L"FlowDrop.NativeDesktop";
enum { PICK=101, SEND, COPY_CODE, RECEIVE, CHOOSE_FOLDER, OPEN_FOLDER, AUTO_SAVE, CLEAR_FILES, REVOKE };
HWND window, heading, subtitle, sendTitle, fileList, pickButton, clearButton, sendButton;
HWND folderPickButton,updateButton,updateAutoCheck,lanButton,renameButton;
constexpr int UPDATE_CHECK=2030,UPDATE_AUTO=2031,ALLOW_LAN=2032,RENAME_DEVICE=2033;
json updateState=json::object();bool applyingUpdate=false,checkingUpdate=false,promptingUpdate=false,renamingDevice=false;
uint64_t handledUpdateCheck=0,handledUpdateError=0;std::string currentDeviceName;
constexpr ULONG_PTR SHELL_FILES=0x46443132;
std::vector<fs::path> pendingShellPaths;
HWND progressBar, sendCode, copyButton, revokeButton, receiveTitle, receiveHelp, receiveCode, receiveButton, receiveList;
HWND folderLabel, folderText, folderButton, openButton, autoCheck, statusLabel;
HFONT bodyFont, titleFont, codeFont, sectionFont;
constexpr COLORREF BG=RGB(11,16,32), SURFACE=RGB(19,28,46), FIELD=RGB(12,21,37), TEXT=RGB(237,243,255), MUTED=RGB(158,172,194), ACCENT=RGB(88,230,163), BORDER=RGB(42,55,80);
HWND queueLabel,peerTitle,peerHelp,peerList,rescanButton,codeOnlyButton;
constexpr int PEER_LIST=2010,RESCAN=2011,CODE_ONLY=2012,PICK_FOLDER=2013;
json peers=json::array();std::string selectedPeerId;
std::atomic<bool> polling{false};bool promptingOffer=false;
RECT peerPanel{},sessionsPanel{};
HWND sessionsButton,transferButton,sessionsTitle,sessionsHelp,sessionList;
constexpr int SESSION_VIEW=2020,TRANSFER_VIEW=2021,SESSION_LIST=2022;
bool sessionMode=false;
json sessions=json::array(),preparingSession;
RECT sendPanel{},receivePanel{},savePanel{};
HBRUSH surfaceBrush;
HBRUSH background, whiteBrush;
HANDLE serverJob=nullptr, serverProcess=nullptr;
std::atomic<unsigned> serverPort{0};
std::vector<fs::path> selectedFiles;
std::vector<fs::path> selectedFolders;
std::string desktopToken, uploadToken, sentCode, saveDirectory, lastAutoCode;
bool ready=false, sending=false, receiving=false, updatingSettings=false, closing=false, automatic=true;

std::wstring wide(const std::string& value) {
  if(value.empty()) return {};
  int n=MultiByteToWideChar(CP_UTF8,0,value.data(),(int)value.size(),nullptr,0);
  std::wstring result(n,L'\0'); MultiByteToWideChar(CP_UTF8,0,value.data(),(int)value.size(),result.data(),n); return result;
}
std::string utf8(const std::wstring& value) {
  if(value.empty()) return {};
  int n=WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),nullptr,0,nullptr,nullptr);
  std::string result(n,'\0'); WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),result.data(),n,nullptr,nullptr); return result;
}
std::wstring text(HWND control) {
  int length=GetWindowTextLengthW(control); std::wstring result(length+1,L'\0');
  GetWindowTextW(control,result.data(),length+1); result.resize(length); return result;
}
void post(json event) {
  auto* data=new json(std::move(event));
  if(!IsWindow(window)||!PostMessageW(window,UI_EVENT,0,reinterpret_cast<LPARAM>(data))) delete data;
}
void backgroundTask(const std::string& operation,std::function<void()> action) {
  std::thread([operation,action=std::move(action)] {try {action();} catch(const std::exception& e) {post({{"kind","error"},{"operation",operation},{"message",e.what()}});}}).detach();
}
struct HttpHandle {
  HINTERNET value;
  explicit HttpHandle(HINTERNET handle):value(handle) {if(!value) throw std::runtime_error("Không kết nối được máy chủ FlowDrop.");}
  ~HttpHandle(){WinHttpCloseHandle(value);}
  HttpHandle(const HttpHandle&)=delete;
};
struct FileHandle {
  HANDLE value;
  explicit FileHandle(HANDLE h):value(h) {if(value==INVALID_HANDLE_VALUE) throw std::runtime_error("Không mở được file đã chọn.");}
  ~FileHandle(){CloseHandle(value);}
};
json responseJson(HINTERNET request) {
  if(!WinHttpReceiveResponse(request,nullptr)) throw std::runtime_error("Mất kết nối. Hãy thử lại.");
  DWORD status=0,length=sizeof(status); WinHttpQueryHeaders(request,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,nullptr,&status,&length,nullptr);
  std::string body; char buffer[16384]; DWORD count=0;
  while(WinHttpReadData(request,buffer,sizeof(buffer),&count)&&count) {
    if(body.size()+count>16*1024*1024) throw std::runtime_error("Phản hồi quá lớn."); body.append(buffer,count);
  }
  json result=json::parse(body,nullptr,false);
  if(result.is_discarded()) throw std::runtime_error("Máy chủ trả dữ liệu không hợp lệ.");
  if(status<200||status>=300) throw std::runtime_error(result.value("error",std::string("Không hoàn tất được yêu cầu.")));
  return result;
}
json requestJson(const wchar_t* method,const std::string& route,const json* payload=nullptr,const std::string& token="",bool transferToken=false,DWORD timeout=600000) {
  HttpHandle session(WinHttpOpen(L"FlowDrop/1.9",WINHTTP_ACCESS_TYPE_NO_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0));
  WinHttpSetTimeouts(session.value,5000,5000,timeout,timeout);
  HttpHandle connection(WinHttpConnect(session.value,L"127.0.0.1",(INTERNET_PORT)serverPort.load(),0));
  HttpHandle request(WinHttpOpenRequest(connection.value,method,wide(route).c_str(),nullptr,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,0));
  std::wstring headers=L"Content-Type: application/json\r\n";
  if(!token.empty()) headers+=(transferToken?L"X-Upload-Token: ":L"X-Desktop-Token: ")+wide(token)+L"\r\n";
  std::string body=payload?payload->dump():"";
  if(!WinHttpSendRequest(request.value,headers.c_str(),(DWORD)-1,body.empty()?WINHTTP_NO_REQUEST_DATA:body.data(),(DWORD)body.size(),(DWORD)body.size(),0)) throw std::runtime_error("Chưa gửi được yêu cầu. Hãy thử lại.");
  return responseJson(request.value);
}
void uploadFile(const fs::path& path,const json& file,const std::string& code,const std::string& token,uint64_t& completed,uint64_t total) {
  FileHandle input(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_SEQUENTIAL_SCAN,nullptr));
  LARGE_INTEGER length{}; if(!GetFileSizeEx(input.value,&length)||length.QuadPart!=file.at("size").get<int64_t>()) throw std::runtime_error("File đã thay đổi. Chọn lại và gửi lại.");
  HttpHandle session(WinHttpOpen(L"FlowDrop/1.9",WINHTTP_ACCESS_TYPE_NO_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0));
  WinHttpSetTimeouts(session.value,5000,5000,600000,600000);
  HttpHandle connection(WinHttpConnect(session.value,L"127.0.0.1",(INTERNET_PORT)serverPort.load(),0));
  auto route=wide("/api/transfers/"+code+"/files/"+file.at("id").get<std::string>());
  HttpHandle request(WinHttpOpenRequest(connection.value,L"PUT",route.c_str(),nullptr,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,0));
  std::wstring headers=L"Content-Type: application/octet-stream\r\nX-Upload-Token: "+wide(token)+L"\r\nContent-Length: "+std::to_wstring(length.QuadPart)+L"\r\n";
  if(!WinHttpSendRequest(request.value,headers.c_str(),(DWORD)-1,WINHTTP_NO_REQUEST_DATA,0,WINHTTP_IGNORE_REQUEST_TOTAL_LENGTH,0)) throw std::runtime_error("Chưa gửi được file.");
  char buffer[65536]; DWORD count=0; unsigned last=101;
  for(;;) {
    if(!ReadFile(input.value,buffer,sizeof(buffer),&count,nullptr)) throw std::runtime_error("Không đọc được file.");
    if(!count) break;
    DWORD offset=0;
    while(offset<count) {DWORD written=0;if(!WinHttpWriteData(request.value,buffer+offset,count-offset,&written)||!written) throw std::runtime_error("Gửi file bị ngắt. Hãy thử lại.");offset+=written;}
    completed+=count; unsigned percent=total?(unsigned)(completed*100/total):100;
    if(percent!=last) {post({{"kind","progress"},{"percent",percent},{"bytes",completed},{"size",total},{"currentName",utf8(path.filename().wstring())}});last=percent;}
  }
  responseJson(request.value);
}
void layout();
std::wstring amount(uint64_t bytes){double n=(double)bytes;const wchar_t* units[]={L"B",L"KB",L"MB",L"GB",L"TB",L"PB"};int i=0;while(n>=1024&&i<5){n/=1024;i++;}wchar_t value[96];swprintf(value,96,L"%.1f %ls",n,units[i]);return value;}
std::wstring sessionState(const json& item){
  if(!item.value("connectionError",std::string()).empty())return L"Mất kết nối · Đang thử lại";
  auto state=item.value("state",std::string());
  if(state=="pending")return L"Chờ chấp nhận";if(state=="accepted")return L"Đã chấp nhận · Đang bắt đầu";if(state=="transferring")return item.value("bytes",uint64_t(0))>=item.value("size",uint64_t(0))&&item.value("filesDone",0)<item.value("count",0)?L"Đang hoàn tất lưu file":L"Đang truyền";if(state=="completed")return L"Hoàn tất · Đã lưu đủ file";if(state=="rejected")return L"Đã từ chối";if(state=="expired")return L"Yêu cầu đã hết hạn";if(state=="failed")return L"Truyền chưa hoàn tất";if(state=="untracked")return L"Máy nhận chưa hỗ trợ tiến độ";return L"Đang chuẩn bị file";
}
void renderSessions(){
  int top=(int)SendMessageW(sessionList,LB_GETTOPINDEX,0,0);SendMessageW(sessionList,WM_SETREDRAW,FALSE,0);SendMessageW(sessionList,LB_RESETCONTENT,0,0);
  if(!preparingSession.is_null())SendMessageW(sessionList,LB_ADDSTRING,0,(LPARAM)L"Đang chuẩn bị file");
  int active=preparingSession.is_null()?0:1;
  for(const auto& item:sessions){auto label=wide(item.value("name",std::string("thiết bị")))+L" · "+sessionState(item);SendMessageW(sessionList,LB_ADDSTRING,0,(LPARAM)label.c_str());auto state=item.value("state",std::string());if(state=="pending"||state=="accepted"||state=="transferring")active++;}
  if(top>0)SendMessageW(sessionList,LB_SETTOPINDEX,top,0);SendMessageW(sessionList,WM_SETREDRAW,TRUE,0);InvalidateRect(sessionList,nullptr,TRUE);
  SetWindowTextW(sessionsButton,(L"Phiên truyền ("+std::to_wstring(active)+L")").c_str());
  SetWindowTextW(sessionsHelp,sessions.empty()&&preparingSession.is_null()?L"Chưa có phiên truyền. Chọn thiết bị rồi gửi file để bắt đầu.":L"Tiến độ do thiết bị nhận xác nhận. Hoàn tất khi tất cả file đã lưu xong.");
}
void showSessions(bool enabled){sessionMode=enabled;layout();renderSessions();}
void refreshEnabled() {
  uint64_t bytes=0;for(const auto& path:selectedFiles){std::error_code e;auto n=fs::file_size(path,e);if(!e)bytes+=n;}
  wchar_t summary[128];double amount=(double)bytes;const wchar_t* unit=L"B";if(amount>=1024){amount/=1024;unit=L"KB";}if(amount>=1024){amount/=1024;unit=L"MB";}if(amount>=1024){amount/=1024;unit=L"GB";}swprintf(summary,128,L"%zu file  ·  %.1f %ls",selectedFiles.size(),amount,unit);SetWindowTextW(queueLabel,selectedFiles.empty()?L"Kéo thả file vào cửa sổ hoặc bấm Chọn file":summary);
  EnableWindow(pickButton,ready&&!sending);EnableWindow(folderPickButton,ready&&!sending); EnableWindow(clearButton,ready&&!sending);
  EnableWindow(sendButton,ready&&!sending&&!selectedFiles.empty()&&!selectedPeerId.empty());
  EnableWindow(codeOnlyButton,ready&&!sending&&!selectedFiles.empty());
  std::wstring destination=L"Chọn thiết bị để gửi";for(const auto& peer:peers)if(peer.at("id")==selectedPeerId)destination=L"Gửi đến "+wide(peer.value("name",std::string("thiết bị")));
  SetWindowTextW(sendButton,destination.c_str());EnableWindow(peerList,ready&&!sending);EnableWindow(rescanButton,ready&&!polling);
  EnableWindow(copyButton,ready&&!sentCode.empty()); EnableWindow(revokeButton,ready&&!sending&&!sentCode.empty());
  EnableWindow(receiveButton,ready&&!receiving); EnableWindow(receiveCode,ready&&!receiving);
  EnableWindow(folderButton,ready&&!receiving&&!updatingSettings); EnableWindow(openButton,ready&&!updatingSettings);
  EnableWindow(autoCheck,ready&&!updatingSettings);
  EnableWindow(updateButton,ready&&!applyingUpdate&&!checkingUpdate&&!updateState.value("accepted",false));EnableWindow(renameButton,ready&&!applyingUpdate&&!renamingDevice);EnableWindow(updateAutoCheck,ready&&!applyingUpdate);EnableWindow(lanButton,ready&&!applyingUpdate);
}
std::string normalizedCode(const std::wstring& input){std::string result;for(char c:utf8(input)){if(c==' '||c=='-'||c=='\t'||c=='\r'||c=='\n')continue;if(c>='a'&&c<='z')c-=32;result+=c;}return result;}
bool validCode(const std::string& code) {
  if(code.size()!=8) return false;
  for(char c:code) if(!(c>='A'&&c<='Z')&&!(c>='2'&&c<='9')) return false; return true;
}
void receiveFiles() {
  std::string code=normalizedCode(text(receiveCode));
  if(!ready||receiving) return;
  if(!validCode(code)) {SetWindowTextW(statusLabel,L"Nhập đủ mã nhận 8 ký tự.");return;}
  receiving=true;lastAutoCode=code;refreshEnabled();SetWindowTextW(statusLabel,L"Đang nhận và lưu file…");
  const auto token=desktopToken;
  auto preferred=selectedPeerId;
  backgroundTask("receive",[code,token,preferred] {json body={{"code",code},{"peerId",preferred}};auto result=requestJson(L"POST","/api/desktop/receive",&body,token);post({{"kind","received"},{"result",result}});});
}
void sendFiles(bool direct=true) {
  if(!ready||sending||selectedFiles.empty()) return;
  if(direct&&selectedPeerId.empty())return;
  if(direct){uint64_t bytes=0;for(const auto& file:selectedFiles){std::error_code error;auto n=fs::file_size(file,error);if(!error)bytes+=n;}std::string name="thiết bị";for(const auto& peer:peers)if(peer.at("id")==selectedPeerId)name=peer.value("name",name);preparingSession={{"state","preparing"},{"direction","send"},{"name",name},{"count",selectedFiles.size()},{"size",bytes},{"bytes",0},{"filesDone",0}};showSessions(true);}
  auto destination=direct?selectedPeerId:std::string();auto files=selectedFiles;auto folderFiles=selectedFolders;sending=true;refreshEnabled();SetWindowTextW(statusLabel,L"Đang chuẩn bị file…");SendMessageW(progressBar,PBM_SETPOS,0,0);
  backgroundTask("send",[files,folderFiles,destination] {
    json items=json::array();uint64_t total=0,completed=0;
    for(const auto& path:files) {
      auto size=fs::file_size(path);
      if(size>9007199254740991ULL-total)throw std::runtime_error("Dung lượng vượt phạm vi giao thức.");total+=size;items.push_back({{"name",utf8(path.filename().wstring())},{"size",size},{"type",std::find(folderFiles.begin(),folderFiles.end(),path)!=folderFiles.end()?"application/vnd.flowdrop.folder+zip":path.extension()==L".zip"?"application/zip":"application/octet-stream"}});
    }
    json body={{"files",items}},created=requestJson(L"POST","/api/transfers",&body,desktopToken);
    const auto code=created.at("code").get<std::string>(),token=created.at("token").get<std::string>();
    try {
      for(size_t i=0;i<files.size();i++) uploadFile(files[i],created.at("files").at(i),code,token,completed,total);
      requestJson(L"POST","/api/transfers/"+code+"/complete",nullptr,token,true);
    } catch(...) {try{requestJson(L"DELETE","/api/transfers/"+code,nullptr,token,true);}catch(...){}throw;}
    if(!destination.empty()){json offer={{"peerId",destination},{"code",code}};try{requestJson(L"POST","/api/desktop/send-offer",&offer,desktopToken);}catch(...){post({{"kind","sent"},{"code",code},{"token",token},{"count",files.size()},{"offerFailed",true}});throw;}}
    post({{"kind","sent"},{"code",code},{"token",token},{"count",files.size()},{"direct",!destination.empty()}});
  });
}
void scanPeers(bool rescan=false){
  if(!ready||closing||polling.exchange(true))return;
  auto token=desktopToken;
  std::thread([token,rescan]{try{json body={{"rescan",rescan}};auto state=requestJson(L"POST","/api/desktop/peers",&body,token,false,8000);post({{"kind","peers"},{"state",state}});}catch(const std::exception& e){post({{"kind","scanError"},{"message",e.what()}});}polling=false;}).detach();
}
void prepareFolders(const std::vector<fs::path>& folders,bool append=false) {
  if(!ready||sending||folders.empty())return;sending=true;refreshEnabled();SetWindowTextW(statusLabel,L"Đang chuẩn bị thư mục…");SendMessageW(progressBar,PBM_SETPOS,0,0);
  backgroundTask("folder",[folders,append]{
    json selected=json::array();
    for(const auto& folder:folders){
      json input={{"directory",utf8(folder.wstring())}};auto created=requestJson(L"POST","/api/desktop/archive-folder",&input,desktopToken);json query={{"id",created.at("id")}};
      for(;;){
        auto state=requestJson(L"POST","/api/desktop/archive-status",&query,desktopToken);
        if(state.at("state")=="failed")throw std::runtime_error(state.value("error",std::string("Không đóng gói được thư mục.")));
        if(state.at("state")=="ready"){selected.push_back(state.at("result").at("path"));break;}
        post({{"kind","folderProgress"},{"state",state}});Sleep(250);
      }
    }
    post({{"kind","folderReady"},{"paths",selected},{"append",append}});
  });
}
void chooseFiles(bool directories=false) {
  IFileOpenDialog* dialog=nullptr;
  if(FAILED(CoCreateInstance(CLSID_FileOpenDialog,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&dialog)))) return;
  DWORD options=0;dialog->GetOptions(&options);dialog->SetOptions(options|FOS_ALLOWMULTISELECT|FOS_FORCEFILESYSTEM|(directories?FOS_PICKFOLDERS:FOS_FILEMUSTEXIST));
  dialog->SetTitle(directories?L"Chọn thư mục để gửi":L"Chọn file để gửi");
  if(SUCCEEDED(dialog->Show(window))) {
    IShellItemArray* items=nullptr;
    if(SUCCEEDED(dialog->GetResults(&items))) {
      DWORD count=0;items->GetCount(&count);std::vector<fs::path> paths;
      for(DWORD i=0;i<count;i++) {
        IShellItem* item=nullptr;PWSTR value=nullptr;
        if(SUCCEEDED(items->GetItemAt(i,&item))) {if(SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH,&value))) {paths.emplace_back(value);CoTaskMemFree(value);}item->Release();}
      }
      if(!paths.empty()) {if(directories)prepareFolders(paths);else{selectedFolders.clear();selectedFiles=std::move(paths);SendMessageW(fileList,LB_RESETCONTENT,0,0);for(const auto& path:selectedFiles) SendMessageW(fileList,LB_ADDSTRING,0,(LPARAM)path.filename().c_str());}}
      items->Release();refreshEnabled();
    }
  }
  dialog->Release();
}
fs::path appDirectory();
void allowLan(bool force=false){
  auto program=appDirectory()/L"runtime"/L"node.exe";wchar_t saved[32768]{};DWORD length=sizeof(saved);
  if(!force&&RegGetValueW(HKEY_CURRENT_USER,L"Software\\FlowDrop",L"LanProgram",RRF_RT_REG_SZ,nullptr,saved,&length)==ERROR_SUCCESS&&program.wstring()==saved)return;
  auto script=appDirectory()/L"Allow-LAN.ps1";auto parameters=L"-NoProfile -ExecutionPolicy Bypass -File \""+script.wstring()+L"\"";
  auto result=(INT_PTR)ShellExecuteW(window,L"runas",L"powershell.exe",parameters.c_str(),nullptr,SW_HIDE);
  if(result>32){HKEY key;if(RegCreateKeyExW(HKEY_CURRENT_USER,L"Software\\FlowDrop",0,nullptr,0,KEY_SET_VALUE,nullptr,&key,nullptr)==ERROR_SUCCESS){RegSetValueExW(key,L"LanProgram",0,REG_SZ,(const BYTE*)program.c_str(),(DWORD)((program.wstring().size()+1)*sizeof(wchar_t)));RegCloseKey(key);}}
  else if(force)SetWindowTextW(statusLabel,L"Chưa cấp quyền Firewall. Bấm Cho phép Wi-Fi để thử lại.");
}
void applyUpdate(){
  if(applyingUpdate||sending||receiving||!ready||promptingOffer||promptingUpdate||renamingDevice||!pendingShellPaths.empty())return;applyingUpdate=true;ready=false;refreshEnabled();auto token=desktopToken;
  backgroundTask("update",[token]{auto result=requestJson(L"POST","/api/desktop/update/apply",nullptr,token);post({{"kind","installUpdate"},{"result",result}});});
}
void checkUpdate(){
  if(applyingUpdate||!ready||promptingUpdate)return;
  checkingUpdate=true;refreshEnabled();auto token=desktopToken;
  backgroundTask("update",[token]{auto result=requestJson(L"POST","/api/desktop/update/check",nullptr,token);post({{"kind","updateChecked"},{"result",result}});});
}
void updateSubtitle(){SetWindowTextW(subtitle,wide("Máy này: "+currentDeviceName+" · Chọn thiết bị trong Wi-Fi để gửi trực tiếp.").c_str());}
INT_PTR CALLBACK nameDialog(HWND dialog,UINT message,WPARAM wp,LPARAM lp){
  if(message==WM_INITDIALOG){SetWindowLongPtrW(dialog,DWLP_USER,lp);auto* value=reinterpret_cast<std::wstring*>(lp);SetDlgItemTextW(dialog,6002,value->c_str());SendDlgItemMessageW(dialog,6002,EM_SETLIMITTEXT,100,0);SendDlgItemMessageW(dialog,6002,EM_SETSEL,0,-1);SetFocus(GetDlgItem(dialog,6002));return FALSE;}
  if(message==WM_COMMAND){if(LOWORD(wp)==IDCANCEL){EndDialog(dialog,IDCANCEL);return TRUE;}if(LOWORD(wp)==IDOK){auto value=text(GetDlgItem(dialog,6002));size_t first=value.find_first_not_of(L" "),last=value.find_last_not_of(L" ");value=first==std::wstring::npos?L"":value.substr(first,last-first+1);unsigned count=0;bool invalid=false;for(wchar_t c:value){if(c<32||c==127||c==0x2028||c==0x2029)invalid=true;if(c<0xdc00||c>0xdfff)count++;}if(invalid||!count||count>50){MessageBoxW(dialog,L"Tên thiết bị cần từ 1 đến 50 ký tự, không chứa ký tự điều khiển.",L"Đổi tên thiết bị",MB_OK|MB_ICONINFORMATION);return TRUE;}*reinterpret_cast<std::wstring*>(GetWindowLongPtrW(dialog,DWLP_USER))=value;EndDialog(dialog,IDOK);return TRUE;}}
  return FALSE;
}
void renameDevice(){
  if(!ready||renamingDevice||promptingUpdate||applyingUpdate)return;renamingDevice=true;std::wstring value=wide(currentDeviceName);
  if(DialogBoxParamW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(6001),window,nameDialog,reinterpret_cast<LPARAM>(&value))!=IDOK){renamingDevice=false;return;}
  auto token=desktopToken;auto name=utf8(value);backgroundTask("rename",[token,name]{json body={{"name",name}};auto result=requestJson(L"POST","/api/desktop/device-name",&body,token);post({{"kind","renamed"},{"result",result}});});
}
void handleUpdateStatus(){
  const auto phase=updateState.value("phase",std::string());checkingUpdate=phase=="checking";
  SendMessageW(updateAutoCheck,BM_SETCHECK,updateState.value("automatic",true)?BST_CHECKED:BST_UNCHECKED,0);
  SetWindowTextW(updateButton,phase=="downloading"?L"Đang tải…":phase=="checking"?L"Đang kiểm tra…":L"Cập nhật");
  if(phase=="deferred")SetWindowTextW(statusLabel,L"Đã chọn cập nhật. Chờ các phiên truyền kết thúc để tải và cài bản mới.");
  if(phase=="downloading")SetWindowTextW(statusLabel,wide("Đang tải FlowDrop "+updateState.value("latest",std::string())+" · "+std::to_string(updateState.value("bytes",uint64_t(0))*100/std::max(uint64_t(1),updateState.value("size",uint64_t(1))))+"%").c_str());
  if(promptingUpdate||promptingOffer||renamingDevice||closing||applyingUpdate)return;
  auto id=updateState.value("checkId",uint64_t(0));bool manual=updateState.value("manual",false);
  if(phase=="error"&&updateState.value("errorId",uint64_t(0))!=handledUpdateError&&id==handledUpdateCheck){handledUpdateError=updateState.value("errorId",uint64_t(0));promptingUpdate=true;auto message=wide("Cập nhật chưa hoàn tất.\n"+updateState.value("error",std::string()));MessageBoxW(window,message.c_str(),L"FlowDrop · Cập nhật",MB_OK|MB_ICONWARNING);promptingUpdate=false;}
  if(id&&id!=handledUpdateCheck&&(phase=="available"||phase=="current"||phase=="error")){
    if(!manual&&(!updateState.value("automatic",true)||sending||receiving||updateState.value("busy",false)))return;
    handledUpdateCheck=id;if(phase=="error")handledUpdateError=updateState.value("errorId",uint64_t(0));promptingUpdate=true;
    if(phase=="available"){
      const auto version=updateState.value("latest",std::string());auto title=wide("Có FlowDrop "+version+" mới");
      TASKDIALOG_BUTTON buttons[]={{100,L"Cập nhật ngay"},{101,L"Để sau"}};TASKDIALOGCONFIG config{sizeof(config)};config.hwndParent=window;config.dwFlags=TDF_ALLOW_DIALOG_CANCELLATION|TDF_SIZE_TO_CONTENT;config.pszWindowTitle=L"FlowDrop · Cập nhật";config.pszMainInstruction=title.c_str();config.pszContent=L"Tải và cài đè phiên bản mới, giữ nguyên cài đặt. Nếu đang truyền file, FlowDrop sẽ chờ phiên truyền kết thúc.";config.cButtons=2;config.pButtons=buttons;config.nDefaultButton=101;int choice=101;TaskDialogIndirect(&config,&choice,nullptr,nullptr);
      auto token=desktopToken;backgroundTask("update",[token,version,id,choice]{json body={{"version",version},{"checkId",id}};auto result=requestJson(L"POST",choice==100?"/api/desktop/update/accept":"/api/desktop/update/later",&body,token);post({{"kind","updateChecked"},{"result",result}});});
    }else if(manual){auto message=phase=="current"?wide("Chưa có phiên bản mới. Bạn đang dùng FlowDrop "+updateState.value("version",std::string())+"."):wide("Không kiểm tra được cập nhật.\n"+updateState.value("error",std::string("Kiểm tra kết nối mạng rồi thử lại.")));MessageBoxW(window,message.c_str(),L"FlowDrop · Kiểm tra cập nhật",MB_OK|(phase=="error"?MB_ICONWARNING:MB_ICONINFORMATION));}
    else if(phase=="error")SetWindowTextW(statusLabel,wide(updateState.value("error",std::string())).c_str());
    promptingUpdate=false;
  }
  if(updateState.value("accepted",false)&&updateState.value("canApply",false))applyUpdate();
}
bool validShellPath(const fs::path& value){auto name=value.wstring();if(!value.is_absolute()||name.empty()||name.find(L'\0')!=std::wstring::npos)return false;for(auto c:name)if(c<32)return false;DWORD attributes=GetFileAttributesW(name.c_str());return attributes!=INVALID_FILE_ATTRIBUTES;}
void drainShellPaths(){
  if(pendingShellPaths.empty()||!ready||sending||receiving||updatingSettings||promptingOffer||promptingUpdate||renamingDevice||applyingUpdate)return;
  auto paths=std::move(pendingShellPaths);pendingShellPaths.clear();std::vector<fs::path> folders;
  for(const auto& file:paths){if(!validShellPath(file))continue;DWORD attributes=GetFileAttributesW(file.c_str());if(attributes&FILE_ATTRIBUTE_DIRECTORY){if(std::find(folders.begin(),folders.end(),file)==folders.end())folders.push_back(file);}else if(std::find(selectedFiles.begin(),selectedFiles.end(),file)==selectedFiles.end()){selectedFiles.push_back(file);SendMessageW(fileList,LB_ADDSTRING,0,(LPARAM)file.filename().c_str());}}
  showSessions(false);if(!folders.empty())prepareFolders(folders,true);else SetWindowTextW(statusLabel,L"Đã thêm file từ Explorer. Chọn thiết bị nhận rồi bấm Gửi.");refreshEnabled();
}
void saveSettings(const std::string& directory,bool autoSave) {
  updatingSettings=true;refreshEnabled();auto token=desktopToken;
  backgroundTask("settings",[directory,autoSave,token] {json body={{"directory",directory},{"autoSave",autoSave}};auto result=requestJson(L"POST","/api/desktop/settings",&body,token);post({{"kind","settings"},{"result",result}});});
}
void chooseFolder() {
  IFileOpenDialog* dialog=nullptr;
  if(FAILED(CoCreateInstance(CLSID_FileOpenDialog,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&dialog)))) return;
  DWORD options=0;dialog->GetOptions(&options);dialog->SetOptions(options|FOS_PICKFOLDERS|FOS_FORCEFILESYSTEM);dialog->SetTitle(L"Chọn thư mục lưu file FlowDrop");
  if(SUCCEEDED(dialog->Show(window))) {
    IShellItem* item=nullptr;PWSTR value=nullptr;
    if(SUCCEEDED(dialog->GetResult(&item))) {if(SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH,&value))) {saveSettings(utf8(value),automatic);CoTaskMemFree(value);}item->Release();}
  }
  dialog->Release();
}
void copyCode() {
  auto code=wide(sentCode);
  if(code.empty()||!OpenClipboard(window)) return;
  HGLOBAL data=GlobalAlloc(GMEM_MOVEABLE,(code.size()+1)*sizeof(wchar_t));
  if(data) {auto* pointer=GlobalLock(data);if(pointer){memcpy(pointer,code.c_str(),(code.size()+1)*sizeof(wchar_t));GlobalUnlock(data);EmptyClipboard();if(!SetClipboardData(CF_UNICODETEXT,data))GlobalFree(data);}else GlobalFree(data);}
  CloseClipboard();SetWindowTextW(statusLabel,L"Đã sao chép mã gửi. Nhập mã này trên điện thoại để nhận file.");
}
std::wstring quote(const fs::path& path) {return L"\""+path.wstring()+L"\"";}
fs::path appDirectory() {wchar_t buffer[32768];DWORD length=GetModuleFileNameW(nullptr,buffer,32768);return fs::path(std::wstring(buffer,length)).parent_path();}
void startServer() {
  auto app=appDirectory();PWSTR local=nullptr;
  if(FAILED(SHGetKnownFolderPath(FOLDERID_LocalAppData,0,nullptr,&local))) throw std::runtime_error("Không tìm được thư mục dữ liệu ứng dụng.");
  fs::path data=fs::path(local)/L"FlowDrop"/L"Data";CoTaskMemFree(local);fs::create_directories(data);
  SetEnvironmentVariableW(L"FLOWDROP_DATA_DIR",data.c_str());SetEnvironmentVariableW(L"FLOWDROP_DESKTOP",L"1");SetEnvironmentVariableW(L"FLOWDROP_DESKTOP_NATIVE",L"1");SetEnvironmentVariableW(L"PORT",L"0");
  PWSTR downloads=nullptr;
  if(SUCCEEDED(SHGetKnownFolderPath(FOLDERID_Downloads,0,nullptr,&downloads))) {auto target=fs::path(downloads)/L"FlowDrop";SetEnvironmentVariableW(L"FLOWDROP_DEFAULT_RECEIVE_DIR",target.c_str());CoTaskMemFree(downloads);}
  auto node=app/L"runtime"/L"node.exe";
  STARTUPINFOW stopInfo{sizeof(stopInfo)};PROCESS_INFORMATION old{};std::wstring stop=quote(node)+L" "+quote(app/L"scripts"/L"stop.mjs");
  if(CreateProcessW(node.c_str(),stop.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,app.c_str(),&stopInfo,&old)) {WaitForSingleObject(old.hProcess,5000);CloseHandle(old.hThread);CloseHandle(old.hProcess);}
  SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE};HANDLE output=nullptr,writer=nullptr;
  if(!CreatePipe(&output,&writer,&security,0)) throw std::runtime_error("Không khởi tạo được máy chủ.");
  SetHandleInformation(output,HANDLE_FLAG_INHERIT,0);
  STARTUPINFOW info{sizeof(info)};info.dwFlags=STARTF_USESTDHANDLES;info.hStdOutput=writer;info.hStdError=writer;info.hStdInput=nullptr;
  PROCESS_INFORMATION process{};std::wstring command=quote(node)+L" "+quote(app/L"scripts"/L"dev.mjs")+L" --host 0.0.0.0";
  if(!CreateProcessW(node.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,app.c_str(),&info,&process)) {CloseHandle(output);CloseHandle(writer);throw std::runtime_error("Không chạy được Node đi kèm bộ cài. Thử cài lại FlowDrop.");}
  CloseHandle(writer);serverProcess=process.hProcess;
  if(!AssignProcessToJobObject(serverJob,process.hProcess)) {TerminateProcess(process.hProcess,1);CloseHandle(process.hThread);CloseHandle(output);throw std::runtime_error("Không quản lý được tiến trình máy chủ.");}
  ResumeThread(process.hThread);CloseHandle(process.hThread);
  std::string pending;ULONGLONG started=GetTickCount64();bool connected=false;
  while(GetTickCount64()-started<20000) {
    DWORD available=0;
    if(!PeekNamedPipe(output,nullptr,0,nullptr,&available,nullptr)) break;
    if(!available) {if(WaitForSingleObject(serverProcess,0)==WAIT_OBJECT_0) break;Sleep(50);continue;}
    char buffer[4096];DWORD count=0;
    if(!ReadFile(output,buffer,sizeof(buffer),&count,nullptr)||!count) break;
    pending.append(buffer,count);
    size_t newline;
    while((newline=pending.find('\n'))!=std::string::npos) {
      auto line=pending.substr(0,newline);pending.erase(0,newline+1);
      constexpr char prefix[]="FLOWDROP_READY ";
      if(line.rfind(prefix,0)==0) {
        auto metadata=json::parse(line.substr(sizeof(prefix)-1));serverPort=metadata.at("port").get<unsigned>();desktopToken=metadata.at("token").get<std::string>();
        auto settings=requestJson(L"GET","/api/desktop/settings",nullptr,desktopToken);auto config=requestJson(L"GET","/api/config");
        post({{"kind","ready"},{"settings",settings},{"deviceName",config.value("deviceName",std::string("Máy tính"))}});connected=true;break;
      }
    }
    if(connected) break;
    if(pending.size()>8192) pending.erase(0,pending.size()-8192);
  }
  if(!connected) {CloseHandle(output);throw std::runtime_error("Máy chủ chưa khởi động được. Đóng và mở lại FlowDrop.");}
  char discard[4096];DWORD count=0;while(ReadFile(output,discard,sizeof(discard),&count,nullptr)&&count){} CloseHandle(output);
  post({{"kind","serverStopped"}});
}
HWND control(const wchar_t* type,const wchar_t* label,DWORD style,int id=0,DWORD ex=0) {
  if(std::wstring(type)==L"BUTTON"&&(style&BS_TYPEMASK)!=BS_AUTOCHECKBOX)style=(style&~BS_TYPEMASK)|BS_OWNERDRAW;
  HWND result=CreateWindowExW(ex,type,label,WS_CHILD|WS_VISIBLE|style,0,0,0,0,window,(HMENU)(INT_PTR)id,GetModuleHandleW(nullptr),nullptr);
  SendMessageW(result,WM_SETFONT,(WPARAM)bodyFont,TRUE);return result;
}
void roundRect(HDC dc,RECT rect,COLORREF fill,COLORREF line,int radius=20) {
  HBRUSH brush=CreateSolidBrush(fill);HPEN pen=CreatePen(PS_SOLID,1,line);auto oldBrush=SelectObject(dc,brush),oldPen=SelectObject(dc,pen);
  RoundRect(dc,rect.left,rect.top,rect.right,rect.bottom,radius,radius);SelectObject(dc,oldBrush);SelectObject(dc,oldPen);DeleteObject(brush);DeleteObject(pen);
}
void layout() {
  RECT rect{};GetClientRect(window,&rect);int w=rect.right,h=rect.bottom,p=24,gap=18,peerWidth=238,left=p+peerWidth+gap,col=(w-left-p-gap)/2,right=left+col+gap;
  int top=122,bottom=h-202,inside=20,inner=col-40,footer=bottom+18;
  peerPanel={p,top,p+238,bottom};sendPanel={left,top,left+col,bottom};receivePanel={right,top,right+col,bottom};savePanel={p,footer,w-p,h-67};
  auto place=[](HWND c,int x,int y,int width,int height){MoveWindow(c,x,y,width,height,TRUE);};
  place(heading,p,20,w-2*p-465,44);place(updateButton,w-p-438,23,132,40);place(transferButton,w-p-294,23,132,40);place(sessionsButton,w-p-150,23,150,40);place(subtitle,p,72,w-2*p-112,30);place(renameButton,w-p-104,70,104,32);
  place(peerTitle,p+16,top+19,210,29);place(peerHelp,p+16,top+60,206,65);place(peerList,p+12,top+139,214,std::max(60,bottom-top-258));place(rescanButton,p+16,bottom-104,206,39);place(lanButton,p+16,bottom-57,206,39);
  place(sendTitle,left+inside,top+19,inner,29);place(receiveTitle,right+inside,top+19,inner,29);
  place(pickButton,left+inside,top+66,(inner-20)/3,39);place(folderPickButton,left+inside+(inner-20)/3+10,top+66,(inner-20)/3,39);place(clearButton,left+inside+2*((inner-20)/3+10),top+66,inner-2*((inner-20)/3+10),39);
  place(queueLabel,left+inside,top+119,inner,24);
  int listHeight=std::max(56,bottom-top-335),sendY=top+154+listHeight+12;
  place(fileList,left+inside,top+154,inner,listHeight);place(sendButton,left+inside,sendY,inner-105,43);place(codeOnlyButton,left+inside+inner-95,sendY,95,43);place(progressBar,left+inside,sendY+50,inner,5);
  place(sendCode,left+inside,sendY+69,inner,40);place(copyButton,left+inside,sendY+119,inner/2-5,36);place(revokeButton,left+inside+inner/2+5,sendY+119,inner/2-5,36);
  place(receiveHelp,right+inside,top+68,inner,48);place(receiveCode,right+inside,top+135,inner,49);place(receiveButton,right+inside,top+200,inner,43);place(receiveList,right+inside,top+261,inner,std::max(50,bottom-top-282));
  place(folderLabel,p+inside,footer+13,180,25);place(folderText,p+inside,footer+49,w-2*p-290,28);place(folderButton,w-p-245,footer+44,110,36);place(openButton,w-p-125,footer+44,105,36);
  place(autoCheck,p+inside,footer+92,(w-2*p-40)/2,25);place(updateAutoCheck,p+inside+(w-2*p-40)/2,footer+92,(w-2*p-40)/2,25);place(statusLabel,p,h-48,w-2*p,43);
  sessionsPanel={p,top,w-p,bottom};place(sessionsTitle,p+20,top+18,w-2*p-40,32);place(sessionsHelp,p+20,top+61,w-2*p-40,30);place(sessionList,p+16,top+105,w-2*p-32,bottom-top-122);
  for(auto c:{peerTitle,peerHelp,peerList,rescanButton,lanButton,sendTitle,pickButton,folderPickButton,clearButton,queueLabel,fileList,sendButton,codeOnlyButton,progressBar,sendCode,copyButton,revokeButton,receiveTitle,receiveHelp,receiveCode,receiveButton,receiveList})ShowWindow(c,sessionMode?SW_HIDE:SW_SHOW);
  for(auto c:{sessionsTitle,sessionsHelp,sessionList})ShowWindow(c,sessionMode?SW_SHOW:SW_HIDE);
  InvalidateRect(window,nullptr,TRUE);
}
LRESULT CALLBACK windowProc(HWND hwnd,UINT message,WPARAM wp,LPARAM lp) {
  switch(message) {
    case WM_CREATE: {
      window=hwnd;for(auto name:{L"BeVietnamPro-Regular.ttf",L"BeVietnamPro-Medium.ttf",L"BeVietnamPro-Bold.ttf"})AddFontResourceExW((appDirectory()/L"web"/L"assets"/L"fonts"/name).c_str(),FR_PRIVATE,nullptr);
      BOOL dark=TRUE;auto dwm=LoadLibraryW(L"dwmapi.dll");if(dwm){using SetAttr=HRESULT(WINAPI*)(HWND,DWORD,LPCVOID,DWORD);auto attr=(SetAttr)GetProcAddress(dwm,"DwmSetWindowAttribute");if(attr)attr(hwnd,20,&dark,sizeof(dark));FreeLibrary(dwm);}
      bodyFont=CreateFontW(-14,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Be Vietnam Pro");
      titleFont=CreateFontW(-32,0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Be Vietnam Pro");
      codeFont=CreateFontW(-28,0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Consolas");
      background=CreateSolidBrush(BG);whiteBrush=CreateSolidBrush(FIELD);surfaceBrush=CreateSolidBrush(SURFACE);sectionFont=CreateFontW(-20,0,0,0,FW_BOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Be Vietnam Pro");
      heading=control(L"STATIC",L"FlowDrop.",0);SendMessageW(heading,WM_SETFONT,(WPARAM)titleFont,TRUE);
      subtitle=control(L"STATIC",L"Đang khởi động…",0);renameButton=control(L"BUTTON",L"Đổi tên",BS_OWNERDRAW|WS_TABSTOP,RENAME_DEVICE);
      updateButton=control(L"BUTTON",L"Cập nhật",WS_TABSTOP,UPDATE_CHECK);
      transferButton=control(L"BUTTON",L"Gửi / Nhận",WS_TABSTOP,TRANSFER_VIEW);sessionsButton=control(L"BUTTON",L"Phiên truyền (0)",WS_TABSTOP,SESSION_VIEW);
      sessionsTitle=control(L"STATIC",L"Phiên truyền · Gửi và nhận",0);SendMessageW(sessionsTitle,WM_SETFONT,(WPARAM)sectionFont,TRUE);
      sessionsHelp=control(L"STATIC",L"Chưa có phiên truyền.",0);sessionList=control(L"LISTBOX",L"",WS_VSCROLL|LBS_NOINTEGRALHEIGHT|LBS_OWNERDRAWFIXED|LBS_HASSTRINGS,SESSION_LIST);SetWindowTheme(sessionList,L"",L"");
      sendTitle=control(L"STATIC",L"01   Gửi file",0);SendMessageW(sendTitle,WM_SETFONT,(WPARAM)sectionFont,TRUE);
      pickButton=control(L"BUTTON",L"Chọn file…",WS_TABSTOP,PICK);folderPickButton=control(L"BUTTON",L"Thư mục…",WS_TABSTOP,PICK_FOLDER);clearButton=control(L"BUTTON",L"Bỏ chọn",WS_TABSTOP,CLEAR_FILES);
      queueLabel=control(L"STATIC",L"Chọn ảnh, video hoặc tài liệu để gửi",0);
      fileList=control(L"LISTBOX",L"",WS_VSCROLL|LBS_NOINTEGRALHEIGHT|LBS_OWNERDRAWFIXED|LBS_HASSTRINGS,0);
      sendButton=control(L"BUTTON",L"Chọn thiết bị để gửi",WS_TABSTOP|BS_DEFPUSHBUTTON,SEND);
      codeOnlyButton=control(L"BUTTON",L"Tạo mã",WS_TABSTOP,CODE_ONLY);
      peerTitle=control(L"STATIC",L"Thiết bị gần bạn",0);SendMessageW(peerTitle,WM_SETFONT,(WPARAM)sectionFont,TRUE);
      peerHelp=control(L"STATIC",L"Đang quét trong Wi-Fi…\nMở FlowDrop trên thiết bị kia.",0);
      peerList=control(L"LISTBOX",L"",WS_TABSTOP|WS_VSCROLL|LBS_NOTIFY|LBS_NOINTEGRALHEIGHT|LBS_OWNERDRAWFIXED|LBS_HASSTRINGS,PEER_LIST);
      rescanButton=control(L"BUTTON",L"Tìm lại thiết bị",WS_TABSTOP,RESCAN);lanButton=control(L"BUTTON",L"Cho phép Wi-Fi",WS_TABSTOP,ALLOW_LAN);
      progressBar=control(PROGRESS_CLASSW,L"",0);SendMessageW(progressBar,PBM_SETRANGE32,0,100);
      sendCode=control(L"EDIT",L"--------",ES_READONLY|ES_CENTER,1001);SendMessageW(sendCode,WM_SETFONT,(WPARAM)codeFont,TRUE);
      copyButton=control(L"BUTTON",L"Sao chép mã",WS_TABSTOP,COPY_CODE);revokeButton=control(L"BUTTON",L"Thu hồi mã",WS_TABSTOP,REVOKE);
      receiveTitle=control(L"STATIC",L"02   Nhận file",0);SendMessageW(receiveTitle,WM_SETFONT,(WPARAM)sectionFont,TRUE);receiveHelp=control(L"STATIC",L"Yêu cầu gửi sẽ hiện để bạn chấp nhận.\nHoặc nhập mã 8 ký tự để nhận dự phòng.",0);
      receiveCode=control(L"EDIT",L"",ES_UPPERCASE|ES_CENTER|WS_TABSTOP|WS_BORDER,RECEIVE+100);SendMessageW(receiveCode,EM_SETLIMITTEXT,16,0);SendMessageW(receiveCode,WM_SETFONT,(WPARAM)codeFont,TRUE);
      receiveButton=control(L"BUTTON",L"Nhận và lưu file",WS_TABSTOP,RECEIVE);receiveList=control(L"LISTBOX",L"",WS_VSCROLL|LBS_NOINTEGRALHEIGHT|LBS_OWNERDRAWFIXED|LBS_HASSTRINGS,1003);
      folderLabel=control(L"STATIC",L"Lưu file theo cách của bạn",0);folderText=control(L"EDIT",L"",ES_READONLY|ES_AUTOHSCROLL,0);
      folderButton=control(L"BUTTON",L"Thay đổi…",WS_TABSTOP,CHOOSE_FOLDER);openButton=control(L"BUTTON",L"Mở thư mục",WS_TABSTOP,OPEN_FOLDER);
      autoCheck=control(L"BUTTON",L"Tự động nhận và lưu khi nhập đủ mã",BS_AUTOCHECKBOX|WS_TABSTOP,AUTO_SAVE);
      updateAutoCheck=control(L"BUTTON",L"Tự động kiểm tra cập nhật",BS_AUTOCHECKBOX|WS_TABSTOP,UPDATE_AUTO);SetWindowTheme(updateAutoCheck,L"DarkMode_Explorer",nullptr);SendMessageW(updateAutoCheck,BM_SETCHECK,BST_CHECKED,0);
      statusLabel=control(L"STATIC",L"Đang khởi động máy chủ trong Wi-Fi…",0,1002);
      SetWindowTheme(peerList,L"",L"");SetWindowTheme(fileList,L"",L"");SetWindowTheme(receiveList,L"",L"");SetWindowTheme(autoCheck,L"DarkMode_Explorer",nullptr);SetWindowTheme(progressBar,L"",L"");SendMessageW(progressBar,PBM_SETBARCOLOR,0,ACCENT);SendMessageW(progressBar,PBM_SETBKCOLOR,0,BORDER);refreshEnabled();layout();
      DragAcceptFiles(hwnd,TRUE);backgroundTask("startup",[]{startServer();});return 0;
    }
    case WM_GETMINMAXINFO: {auto* info=(MINMAXINFO*)lp;info->ptMinTrackSize={1060,790};return 0;}
    case WM_SIZE: layout();return 0;
    case WM_COPYDATA: {
      auto* packet=reinterpret_cast<COPYDATASTRUCT*>(lp);if(!packet||packet->dwData!=SHELL_FILES||!packet->lpData||!packet->cbData||packet->cbData>8*1024*1024||closing||applyingUpdate)return FALSE;
      try{auto values=json::parse(static_cast<const char*>(packet->lpData),static_cast<const char*>(packet->lpData)+packet->cbData);if(!values.is_array()||values.empty())return FALSE;std::vector<fs::path> accepted;for(const auto& item:values){if(!item.is_string())return FALSE;fs::path file(wide(item.get<std::string>()));if(!validShellPath(file))return FALSE;accepted.push_back(file);}pendingShellPaths.insert(pendingShellPaths.end(),accepted.begin(),accepted.end());ShowWindow(hwnd,SW_RESTORE);SetForegroundWindow(hwnd);drainShellPaths();return TRUE;}catch(...){return FALSE;}
    }
    case WM_DROPFILES: {
      HDROP drop=(HDROP)wp;UINT count=DragQueryFileW(drop,0xffffffff,nullptr,0);
      if(ready&&!sending&&count>0) {
        std::vector<fs::path> paths;
        for(UINT i=0;i<count;i++) {UINT length=DragQueryFileW(drop,i,nullptr,0);std::wstring value(length+1,L'\0');DragQueryFileW(drop,i,value.data(),length+1);value.resize(length);if(fs::is_regular_file(fs::path(value)))paths.emplace_back(value);}
        if(!paths.empty()) {selectedFolders.clear();selectedFiles=std::move(paths);SendMessageW(fileList,LB_RESETCONTENT,0,0);for(const auto& path:selectedFiles)SendMessageW(fileList,LB_ADDSTRING,0,(LPARAM)path.filename().c_str());refreshEnabled();}
      }
      DragFinish(drop);return 0;
    }
    case WM_CTLCOLORSTATIC: case WM_CTLCOLORBTN: {
      HDC dc=(HDC)wp;HWND item=(HWND)lp;bool outer=item==heading||item==subtitle||item==statusLabel;
      SetBkMode(dc,TRANSPARENT);SetTextColor(dc,item==heading||item==sendCode?ACCENT:(item==subtitle||item==statusLabel||item==queueLabel||item==receiveHelp||item==peerHelp||item==sessionsHelp?MUTED:TEXT));
      if(item==sendCode||item==folderText){SetBkColor(dc,FIELD);return (LRESULT)whiteBrush;}return (LRESULT)(outer?background:surfaceBrush);
    }
    case WM_CTLCOLOREDIT: case WM_CTLCOLORLISTBOX: {SetBkColor((HDC)wp,FIELD);SetTextColor((HDC)wp,ACCENT);return (LRESULT)whiteBrush;}
    case WM_MEASUREITEM: {auto* measure=(MEASUREITEMSTRUCT*)lp;measure->itemHeight=measure->CtlID==SESSION_LIST?134:38;return TRUE;}
    case WM_DRAWITEM: {
      auto* item=(DRAWITEMSTRUCT*)lp;HDC dc=item->hDC;RECT rect=item->rcItem;
      if(item->CtlType==ODT_LISTBOX&&item->hwndItem==sessionList){
        FillRect(dc,&rect,whiteBrush);if(item->itemID==(UINT)-1)return TRUE;int index=(int)item->itemID;
        json record;if(!preparingSession.is_null()&&index==0)record=preparingSession;else{index-=preparingSession.is_null()?0:1;if(index<0||index>=(int)sessions.size())return TRUE;record=sessions.at(index);}
        RECT card=rect;InflateRect(&card,-5,-5);roundRect(dc,card,SURFACE,BORDER,16);SelectObject(dc,bodyFont);SetBkMode(dc,TRANSPARENT);
        auto state=record.value("state",std::string());COLORREF color=state=="failed"||!record.value("connectionError",std::string()).empty()?RGB(255,170,170):ACCENT;
        RECT line={card.left+16,card.top+10,card.right-16,card.top+32};SetTextColor(dc,TEXT);auto title=wide((record.value("direction",std::string())=="send"?"↑ Gửi đến ":"↓ Nhận từ ")+record.value("name",std::string("thiết bị")));DrawTextW(dc,title.c_str(),-1,&line,DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
        line.top+=25;line.bottom+=25;SetTextColor(dc,color);auto label=sessionState(record);DrawTextW(dc,label.c_str(),-1,&line,DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
        uint64_t bytes=record.value("bytes",uint64_t(0)),size=record.value("size",uint64_t(0));int count=record.value("count",0),done=record.value("filesDone",0),percent=size?(int)(bytes*100/size):count?done*100/count:0;
        RECT track={card.left+16,card.top+65,card.right-16,card.top+71};roundRect(dc,track,BORDER,BORDER,5);if(percent>0){auto bar=track;bar.right=bar.left+(track.right-track.left)*std::min(100,percent)/100;roundRect(dc,bar,color,color,5);}
        std::wstring detail=std::to_wstring(percent)+L"% · "+amount(bytes)+L" / "+amount(size)+L" · "+std::to_wstring(done)+L" / "+std::to_wstring(count)+L" file";
        auto started=record.value("startedAt",uint64_t(0));FILETIME ft;GetSystemTimeAsFileTime(&ft);uint64_t now=(((uint64_t)ft.dwHighDateTime<<32)|ft.dwLowDateTime)/10000-11644473600000ULL;
        if(state=="transferring"&&started&&now>started)detail+=L" · "+amount(bytes*1000/(now-started))+L"/s";
        line={card.left+16,card.top+78,card.right-16,card.top+99};SetTextColor(dc,MUTED);DrawTextW(dc,detail.c_str(),-1,&line,DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
        std::wstring extra=wide(record.value("error",std::string()));if(extra.empty())extra=wide(record.value("currentName",std::string()));
        auto finished=record.value("finishedAt",uint64_t(0));if(extra.empty()&&finished){ULARGE_INTEGER time;time.QuadPart=(finished+11644473600000ULL)*10000;FILETIME utc{time.LowPart,time.HighPart},local;SYSTEMTIME t;FileTimeToLocalFileTime(&utc,&local);FileTimeToSystemTime(&local,&t);wchar_t stamp[64];swprintf(stamp,64,L"Kết thúc %02d:%02d:%02d",t.wHour,t.wMinute,t.wSecond);extra=stamp;}
        line.top+=22;line.bottom+=22;DrawTextW(dc,extra.c_str(),-1,&line,DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);return TRUE;
      }
      if(item->CtlType==ODT_LISTBOX) {
        FillRect(dc,&rect,whiteBrush);if(item->hwndItem==peerList&&(item->itemState&ODS_SELECTED))roundRect(dc,rect,RGB(27,69,57),ACCENT,10);if(item->itemID==(UINT)-1)return TRUE;
        int len=(int)SendMessageW(item->hwndItem,LB_GETTEXTLEN,item->itemID,0);if(len<0)return TRUE;std::wstring value(len+1,L'\0');SendMessageW(item->hwndItem,LB_GETTEXT,item->itemID,(LPARAM)value.data());
        RECT iconRect={rect.left+10,rect.top+8,rect.left+27,rect.bottom-8};roundRect(dc,iconRect,RGB(35,54,81),RGB(55,83,116),5);
        rect.left+=38;rect.right-=12;SetBkMode(dc,TRANSPARENT);SetTextColor(dc,TEXT);SelectObject(dc,bodyFont);DrawTextW(dc,value.c_str(),len,&rect,DT_SINGLELINE|DT_VCENTER|DT_END_ELLIPSIS|DT_NOPREFIX);return TRUE;
      }
      if(item->CtlType==ODT_BUTTON) {
        bool primary=item->CtlID==SEND||item->CtlID==RECEIVE||item->CtlID==SESSION_VIEW&&sessionMode||item->CtlID==TRANSFER_VIEW&&!sessionMode;bool disabled=(item->itemState&ODS_DISABLED)!=0,pressed=(item->itemState&ODS_SELECTED)!=0;
        COLORREF fill=primary?(disabled?RGB(39,75,62):pressed?RGB(66,190,136):ACCENT):(pressed?RGB(43,60,84):RGB(28,41,62));
        FillRect(dc,&rect,surfaceBrush);roundRect(dc,rect,fill,primary?fill:BORDER,15);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,disabled?MUTED:primary?RGB(8,36,25):TEXT);SelectObject(dc,bodyFont);
        auto value=text(item->hwndItem);DrawTextW(dc,value.c_str(),-1,&rect,DT_CENTER|DT_VCENTER|DT_SINGLELINE|DT_NOPREFIX);
        if(item->itemState&ODS_FOCUS){InflateRect(&rect,-4,-4);DrawFocusRect(dc,&rect);}return TRUE;
      }break;
    }
    case WM_ERASEBKGND: return 1;
    case WM_PAINT: {
      PAINTSTRUCT paint{};HDC dc=BeginPaint(hwnd,&paint);RECT rect{};GetClientRect(hwnd,&rect);FillRect(dc,&rect,background);
      if(sessionMode)roundRect(dc,sessionsPanel,SURFACE,BORDER,24);else{roundRect(dc,peerPanel,SURFACE,BORDER,24);roundRect(dc,sendPanel,SURFACE,BORDER,24);roundRect(dc,receivePanel,SURFACE,BORDER,24);}roundRect(dc,savePanel,SURFACE,BORDER,24);EndPaint(hwnd,&paint);return 0;
    }
    case WM_COMMAND: {
      if(LOWORD(wp)==PEER_LIST&&HIWORD(wp)==LBN_SELCHANGE){int index=(int)SendMessageW(peerList,LB_GETCURSEL,0,0);selectedPeerId=index>=0&&index<(int)peers.size()?peers.at(index).at("id").get<std::string>():"";refreshEnabled();return 0;}
      if(LOWORD(wp)==RECEIVE+100&&HIWORD(wp)==EN_CHANGE) {if(ready&&automatic&&!receiving)SetTimer(hwnd,3,700,nullptr);return 0;}
      if(HIWORD(wp)!=BN_CLICKED) break;
      switch(LOWORD(wp)) {
        case SESSION_VIEW:showSessions(true);break;
        case TRANSFER_VIEW:showSessions(false);break;
        case PICK:chooseFiles();break;
        case PICK_FOLDER:chooseFiles(true);break;
        case CLEAR_FILES:selectedFolders.clear();selectedFiles.clear();SendMessageW(fileList,LB_RESETCONTENT,0,0);refreshEnabled();break;
        case SEND:sendFiles();break;
        case CODE_ONLY:sendFiles(false);break;
        case RESCAN:scanPeers(true);break;
        case ALLOW_LAN:allowLan(true);break;
        case RENAME_DEVICE:renameDevice();break;
        case UPDATE_CHECK:checkUpdate();break;
        case UPDATE_AUTO:{auto token=desktopToken;bool enabled=SendMessageW(updateAutoCheck,BM_GETCHECK,0,0)==BST_CHECKED;backgroundTask("update",[token,enabled]{json body={{"automatic",enabled}};auto result=requestJson(L"POST","/api/desktop/update/settings",&body,token);post({{"kind","updateChecked"},{"result",result}});});break;}
        case COPY_CODE:copyCode();break;
        case RECEIVE:receiveFiles();break;
        case CHOOSE_FOLDER:chooseFolder();break;
        case AUTO_SAVE:saveSettings(saveDirectory,SendMessageW(autoCheck,BM_GETCHECK,0,0)==BST_CHECKED);break;
        case OPEN_FOLDER:backgroundTask("open",[]{auto result=requestJson(L"POST","/api/desktop/reveal-directory",nullptr,desktopToken);post({{"kind","openDirectory"},{"directory",result.at("directory")}});});break;
        case REVOKE: {auto code=sentCode,token=uploadToken;sending=true;refreshEnabled();backgroundTask("revoke",[code,token]{requestJson(L"DELETE","/api/transfers/"+code,nullptr,token,true);post({{"kind","revoked"}});});break;}
      } return 0;
    }
    case WM_TIMER: if(wp==5){scanPeers();return 0;}if(wp==3) {KillTimer(hwnd,3);auto code=normalizedCode(text(receiveCode));if(ready&&automatic&&!receiving&&validCode(code)&&code!=lastAutoCode)receiveFiles();return 0;}break;
    case UI_EVENT: {
      std::unique_ptr<json> data((json*)lp);const auto& event=*data;auto kind=event.value("kind",std::string());
      if(kind=="peers") {
        const auto& state=event.at("state");const auto& next=state.at("peers");
        sessions=state.value("sessions",json::array());renderSessions();
        if(state.contains("deviceName")){currentDeviceName=state.at("deviceName").get<std::string>();updateSubtitle();}
        updateState=state.value("update",json::object());handleUpdateStatus();
        if(next!=peers){peers=next;SendMessageW(peerList,LB_RESETCONTENT,0,0);int selected=-1;for(size_t i=0;i<peers.size();i++){const auto& peer=peers.at(i);auto label=wide((peer.value("platform",std::string())=="android"?"Android · ":"PC · ")+peer.value("name",std::string("Thiết bị")));SendMessageW(peerList,LB_ADDSTRING,0,(LPARAM)label.c_str());if(peer.at("id")==selectedPeerId)selected=(int)i;}if(selected>=0)SendMessageW(peerList,LB_SETCURSEL,selected,0);else selectedPeerId.clear();}
        SetWindowTextW(peerHelp,peers.empty()?L"Chưa thấy thiết bị. Mở FlowDrop ở máy kia. Kiểm tra cùng Wi-Fi và Firewall.":wide("Tìm thấy "+std::to_string(peers.size())+" thiết bị.\nChọn tên rồi chọn file để gửi.").c_str());
        if(!applyingUpdate&&!receiving&&!promptingOffer&&!promptingUpdate&&!renamingDevice&&!state.at("offers").empty()){
          auto offer=state.at("offers").at(0);promptingOffer=true;
          auto question=wide(offer.at("name").get<std::string>()+" muốn gửi "+std::to_string(offer.at("count").get<size_t>())+" file.\nNhận và lưu vào thư mục đã chọn?");
          bool accept=MessageBoxW(hwnd,question.c_str(),L"FlowDrop · Nhận file",MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2)==IDYES;
          if(accept){showSessions(true);receiving=true;SetWindowTextW(statusLabel,L"Đang nhận và lưu file…");}
          auto token=desktopToken;auto id=offer.at("id").get<std::string>();
          backgroundTask("receive",[id,accept,token]{json body={{"id",id},{"accept",accept}};auto result=requestJson(L"POST","/api/desktop/answer-offer",&body,token);post({{"kind",accept?"received":"offerRejected"},{"result",result}});});
        }
      } else if(kind=="offerRejected"){promptingOffer=false;SetWindowTextW(statusLabel,L"Đã từ chối yêu cầu nhận file.");}
      else if(kind=="scanError"){SetWindowTextW(peerHelp,L"Chưa quét được thiết bị. Bấm Tìm lại hoặc mở lại FlowDrop.");}
      else if(kind=="ready") {SetTimer(hwnd,5,1500,nullptr);
        const auto& settings=event.at("settings");desktopToken=settings.at("token").get<std::string>();saveDirectory=settings.at("directory").get<std::string>();automatic=settings.value("autoSave",true);ready=true;
        currentDeviceName=event.at("deviceName").get<std::string>();updateSubtitle();
        allowLan();SetWindowTextW(folderText,wide(saveDirectory).c_str());SendMessageW(autoCheck,BM_SETCHECK,automatic?BST_CHECKED:BST_UNCHECKED,0);SetWindowTextW(statusLabel,L"Sẵn sàng chuyển file lớn. Giữ ứng dụng mở và đảm bảo thiết bị còn đủ dung lượng trống.");
      } else if(kind=="folderProgress") {const auto& state=event.at("state");auto size=state.value("size",uint64_t(0)),bytes=state.value("bytes",uint64_t(0));SendMessageW(progressBar,PBM_SETPOS,size?(unsigned)(bytes*100/size):0,0);SetWindowTextW(statusLabel,wide("Đang chuẩn bị thư mục · "+state.value("currentName",std::string())).c_str());}
      else if(kind=="folderReady") {sending=false;if(!event.value("append",false)){selectedFolders.clear();selectedFiles.clear();SendMessageW(fileList,LB_RESETCONTENT,0,0);}for(const auto& item:event.at("paths")){fs::path file(wide(item.get<std::string>()));selectedFiles.push_back(file);selectedFolders.push_back(file);auto label=file.stem().wstring()+L" (thư mục)";SendMessageW(fileList,LB_ADDSTRING,0,(LPARAM)label.c_str());}SendMessageW(progressBar,PBM_SETPOS,100,0);SetWindowTextW(statusLabel,L"Thư mục đã sẵn sàng. Máy nhận 1.11 sẽ tự tạo lại tên và cấu trúc. Bấm Gửi hoặc Tạo mã.");}
      else if(kind=="progress") {SendMessageW(progressBar,PBM_SETPOS,event.value("percent",0),0);if(!preparingSession.is_null()){preparingSession["bytes"]=event.value("bytes",uint64_t(0));preparingSession["currentName"]=event.value("currentName",std::string());renderSessions();}}
      else if(kind=="sent") {preparingSession=nullptr;renderSessions();scanPeers();sending=false;sentCode=event.at("code").get<std::string>();uploadToken=event.at("token").get<std::string>();SetWindowTextW(sendCode,wide(sentCode).c_str());SendMessageW(progressBar,PBM_SETPOS,100,0);SetWindowTextW(statusLabel,event.value("direct",false)?L"Đã gửi yêu cầu. Chấp nhận trên thiết bị nhận để lưu file.":L"Đã tạo mã. Nhập mã trên thiết bị cùng Wi-Fi để nhận; giữ máy gửi còn mở.");}
      else if(kind=="revoked") {sending=false;sentCode.clear();uploadToken.clear();SetWindowTextW(sendCode,L"--------");SetWindowTextW(statusLabel,L"Đã thu hồi mã gửi. File đã lưu trên máy nhận vẫn được giữ lại.");}
      else if(kind=="received") {
        receiving=false;promptingOffer=false;for(const auto& file:event.at("result").at("files")) {auto label=wide(file.at("name").get<std::string>()+(file.value("alreadySaved",false)?" — đã có":file.value("kind",std::string())=="folder"?" — đã nhận thư mục":" — đã lưu"));SendMessageW(receiveList,LB_ADDSTRING,0,(LPARAM)label.c_str());}
        SetWindowTextW(statusLabel,L"Đã lưu file. Bấm Mở thư mục để xem.");
      } else if(kind=="settings") {updatingSettings=false;const auto& settings=event.at("result");saveDirectory=settings.at("directory").get<std::string>();automatic=settings.value("autoSave",true);SetWindowTextW(folderText,wide(saveDirectory).c_str());SendMessageW(autoCheck,BM_SETCHECK,automatic?BST_CHECKED:BST_UNCHECKED,0);SetWindowTextW(statusLabel,L"Đã lưu cài đặt.");}
      else if(kind=="openDirectory") {auto directory=wide(event.at("directory").get<std::string>());SHELLEXECUTEINFOW open{sizeof(open)};open.fMask=SEE_MASK_FLAG_NO_UI;open.hwnd=hwnd;open.lpVerb=L"open";open.lpFile=directory.c_str();open.nShow=SW_SHOWNORMAL;if(!ShellExecuteExW(&open)){PIDLIST_ABSOLUTE pidl=nullptr;HRESULT result=SHParseDisplayName(directory.c_str(),nullptr,&pidl,0,nullptr);if(SUCCEEDED(result)){result=SHOpenFolderAndSelectItems(pidl,0,nullptr,0);CoTaskMemFree(pidl);}if(FAILED(result))SetWindowTextW(statusLabel,wide("Không mở được thư mục: "+event.at("directory").get<std::string>()).c_str());else SetWindowTextW(statusLabel,L"Đã mở thư mục nhận file.");}else SetWindowTextW(statusLabel,L"Đã mở thư mục nhận file.");}
      else if(kind=="renamed"){renamingDevice=false;currentDeviceName=event.at("result").at("deviceName").get<std::string>();updateSubtitle();SetWindowTextW(statusLabel,L"Đã lưu tên thiết bị và cập nhật trong Wi-Fi.");}
      else if(kind=="updateChecked") {updateState=event.at("result");handleUpdateStatus();}
      else if(kind=="installUpdate") {auto installer=wide(event.at("result").at("path").get<std::string>());auto parameters=L"/S /UPDATE /D="+appDirectory().wstring();SHELLEXECUTEINFOW info{sizeof(info)};info.fMask=SEE_MASK_NOCLOSEPROCESS;info.hwnd=hwnd;info.lpFile=installer.c_str();info.lpParameters=parameters.c_str();info.nShow=SW_SHOWNORMAL;
        if(ShellExecuteExW(&info)){if(info.hProcess)CloseHandle(info.hProcess);PostMessageW(hwnd,WM_CLOSE,0,0);}
        else{applyingUpdate=false;ready=true;auto token=desktopToken;backgroundTask("update",[token]{requestJson(L"POST","/api/desktop/update/failed",nullptr,token);});SetWindowTextW(statusLabel,L"Chưa chạy được bộ cài. Bấm Cập nhật để thử lại.");}
      }
      else if(kind=="serverStopped") {ready=false;SetWindowTextW(statusLabel,L"Máy chủ đã dừng. Đóng và mở lại FlowDrop để kết nối lại.");}
      else if(kind=="error") {auto operation=event.value("operation",std::string());if(operation=="send"||operation=="revoke"||operation=="folder"){sending=false;if(!preparingSession.is_null()){preparingSession["state"]="failed";preparingSession["error"]=event.value("message",std::string());renderSessions();}}if(operation=="receive"){receiving=false;promptingOffer=false;}if(operation=="rename")renamingDevice=false;if(operation=="update"){applyingUpdate=false;checkingUpdate=false;ready=true;MessageBoxW(hwnd,wide(event.value("message",std::string())).c_str(),L"FlowDrop · Cập nhật",MB_OK|MB_ICONWARNING);}if(operation=="settings"){updatingSettings=false;SendMessageW(autoCheck,BM_SETCHECK,automatic?BST_CHECKED:BST_UNCHECKED,0);}SetWindowTextW(statusLabel,wide(event.value("message",std::string("Chưa hoàn tất được thao tác."))).c_str());}
      drainShellPaths();refreshEnabled();return 0;
    }
    case WM_CLOSE:
      if(closing)return 0;
      closing=true;EnableWindow(hwnd,FALSE);SetWindowTextW(statusLabel,L"Đang dừng phiên chuyển file…");
      if(ready)std::thread([]{try{requestJson(L"POST","/api/desktop/stop",nullptr,desktopToken,false,2000);Sleep(350);}catch(...){}PostMessageW(window,UI_CLOSE,0,0);}).detach();
      else DestroyWindow(hwnd);
      return 0;
    case UI_CLOSE:DestroyWindow(hwnd);return 0;
    case WM_DESTROY:if(serverJob){CloseHandle(serverJob);serverJob=nullptr;}PostQuitMessage(0);return 0;
  }
  return DefWindowProcW(hwnd,message,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR command,int show) {
  if(command&&std::wstring(command)==L"--shutdown") {
    if(auto other=FindWindowW(CLASS_NAME,nullptr)) {PostMessageW(other,WM_CLOSE,0,0);for(int i=0;i<100&&FindWindowW(CLASS_NAME,nullptr);i++)Sleep(50);}
    return 0;
  }
  int argc=0;LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);std::vector<fs::path> shellPaths;
  if(argv&&argc>=2&&std::wstring(argv[1])==L"--send-files")for(int i=2;i<argc;i++){fs::path file(argv[i]);if(validShellPath(file))shellPaths.push_back(file);}if(argv)LocalFree(argv);
  HANDLE mutex=CreateMutexW(nullptr,TRUE,L"Local\\FlowDrop.NativeDesktop.1");
  if(GetLastError()==ERROR_ALREADY_EXISTS){HWND other=nullptr;for(int i=0;i<100&&!other;i++){other=FindWindowW(CLASS_NAME,nullptr);if(!other)Sleep(50);}bool delivered=shellPaths.empty();if(other){ShowWindow(other,SW_RESTORE);SetForegroundWindow(other);if(!shellPaths.empty()){json values=json::array();for(const auto& file:shellPaths)values.push_back(utf8(file.wstring()));auto bytes=values.dump();COPYDATASTRUCT packet{SHELL_FILES,(DWORD)bytes.size(),bytes.data()};DWORD_PTR result=0;delivered=bytes.size()<=8*1024*1024&&SendMessageTimeoutW(other,WM_COPYDATA,0,(LPARAM)&packet,SMTO_ABORTIFHUNG|SMTO_BLOCK,10000,&result)&&result;}}CloseHandle(mutex);if(!delivered)MessageBoxW(nullptr,L"Chưa thêm được file. Chờ FlowDrop khởi động hoặc cập nhật xong rồi chọn Send to → FlowDrop lại.",L"FlowDrop",MB_OK|MB_ICONINFORMATION);return delivered?0:1;}
  pendingShellPaths=std::move(shellPaths);
  if(FAILED(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED))) return 1;
  serverJob=CreateJobObjectW(nullptr,nullptr);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limit{};limit.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  if(!serverJob||!SetInformationJobObject(serverJob,JobObjectExtendedLimitInformation,&limit,sizeof(limit))) {MessageBoxW(nullptr,L"Không khởi tạo được FlowDrop.",L"FlowDrop",MB_OK|MB_ICONERROR);return 1;}
  INITCOMMONCONTROLSEX controls{sizeof(controls),ICC_PROGRESS_CLASS|ICC_STANDARD_CLASSES};InitCommonControlsEx(&controls);
  WNDCLASSW type{};type.lpfnWndProc=windowProc;type.hInstance=instance;type.lpszClassName=CLASS_NAME;type.hCursor=LoadCursorW(nullptr,IDC_ARROW);type.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(1));RegisterClassW(&type);
  RECT work{};SystemParametersInfoW(SPI_GETWORKAREA,0,&work,0);
  int width=std::min(1320,(int)(work.right-work.left)-24),height=std::min(860,(int)(work.bottom-work.top)-24);
  window=CreateWindowExW(0,CLASS_NAME,L"FlowDrop",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,width,height,nullptr,nullptr,instance,nullptr);
  if(!window) return 1;ShowWindow(window,show);UpdateWindow(window);
  MSG message{};while(GetMessageW(&message,nullptr,0,0)>0){if(!IsDialogMessageW(window,&message)){TranslateMessage(&message);DispatchMessageW(&message);}}
  CoUninitialize();CloseHandle(mutex);return 0;
}
