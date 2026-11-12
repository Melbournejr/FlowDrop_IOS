#define UNICODE
#define _UNICODE
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <commctrl.h>
#include <winhttp.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <functional>
#include "json.hpp"
using json=nlohmann::json;namespace fs=std::filesystem;
unsigned port=0;
std::wstring wide(const std::string&s){int n=MultiByteToWideChar(CP_UTF8,0,s.data(),(int)s.size(),nullptr,0);std::wstring r(n,L'\0');MultiByteToWideChar(CP_UTF8,0,s.data(),(int)s.size(),r.data(),n);return r;}
void check(bool test,const char* message){if(!test)throw std::runtime_error(message);}
void wait(std::function<bool()> predicate,const char* message,int seconds=40){auto start=GetTickCount64();while(GetTickCount64()-start<(unsigned)seconds*1000){if(predicate())return;Sleep(100);}throw std::runtime_error(message);}
std::wstring text(HWND control){wchar_t value[1024]{};DWORD_PTR result=0;SendMessageTimeoutW(control,WM_GETTEXT,1024,(LPARAM)value,SMTO_ABORTIFHUNG,1000,&result);return value;}
std::string http(const wchar_t* method,const std::string& route,const std::string& body="",const std::string& token="",bool desktop=false){
 HINTERNET session=WinHttpOpen(L"FlowDropSmoke",WINHTTP_ACCESS_TYPE_NO_PROXY,nullptr,nullptr,0);WinHttpSetTimeouts(session,3000,3000,10000,10000);
 auto connection=WinHttpConnect(session,L"127.0.0.1",port,0);auto request=WinHttpOpenRequest(connection,method,wide(route).c_str(),nullptr,nullptr,nullptr,0);
 std::wstring headers=L"Content-Type: application/json\r\n";if(!token.empty())headers+=(desktop?L"X-Desktop-Token: ":L"X-Upload-Token: ")+wide(token)+L"\r\n";
 check(WinHttpSendRequest(request,headers.c_str(),-1,body.empty()?nullptr:(void*)body.data(),body.size(),body.size(),0),"HTTP send failed");
 check(WinHttpReceiveResponse(request,nullptr),"HTTP response failed");DWORD status=0,size=sizeof(status);WinHttpQueryHeaders(request,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,nullptr,&status,&size,nullptr);
 std::string result;char buffer[16384];DWORD count=0;while(WinHttpReadData(request,buffer,sizeof(buffer),&count)&&count)result.append(buffer,count);
 WinHttpCloseHandle(request);WinHttpCloseHandle(connection);WinHttpCloseHandle(session);check(status>=200&&status<300,"HTTP status not successful");return result;
}
void verifyLarge(const std::string& route,uint64_t length){
 HINTERNET session=WinHttpOpen(L"FlowDropLargeSmoke",WINHTTP_ACCESS_TYPE_NO_PROXY,nullptr,nullptr,0);auto connection=WinHttpConnect(session,L"127.0.0.1",port,0);auto request=WinHttpOpenRequest(connection,L"GET",wide(route).c_str(),nullptr,nullptr,nullptr,0);
 check(WinHttpSendRequest(request,nullptr,0,nullptr,0,0,0)&&WinHttpReceiveResponse(request,nullptr),"Large download failed");char buffer[65536],zeros[65536]{};DWORD n=0;uint64_t received=0;
 while(WinHttpReadData(request,buffer,sizeof(buffer),&n)&&n){for(DWORD i=0;i<n;i++)if((received+i==0&&buffer[i]!='A')||(received+i==length-1&&buffer[i]!='Z')||(received+i>0&&received+i<length-1&&buffer[i]!=0))throw std::runtime_error("Large download bytes changed");received+=n;}
 WinHttpCloseHandle(request);WinHttpCloseHandle(connection);WinHttpCloseHandle(session);check(received==length,"Large download truncated at 4 GiB");
}
void capture(HWND app,const fs::path& file){
 RECT r{};GetWindowRect(app,&r);int w=r.right-r.left,h=r.bottom-r.top;HDC src=GetWindowDC(app),dc=CreateCompatibleDC(src);HBITMAP bitmap=CreateCompatibleBitmap(src,w,h);auto old=SelectObject(dc,bitmap);BitBlt(dc,0,0,w,h,src,0,0,SRCCOPY);
 BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bi.bmiHeader.biWidth=w;bi.bmiHeader.biHeight=h;bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;std::vector<char> pixels(w*h*4);GetDIBits(dc,bitmap,0,h,pixels.data(),&bi,DIB_RGB_COLORS);
 BITMAPFILEHEADER header{};header.bfType=0x4d42;header.bfOffBits=sizeof(header)+sizeof(BITMAPINFOHEADER);header.bfSize=header.bfOffBits+pixels.size();std::ofstream out(file,std::ios::binary);out.write((char*)&header,sizeof(header));out.write((char*)&bi.bmiHeader,sizeof(bi.bmiHeader));out.write(pixels.data(),pixels.size());SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);ReleaseDC(app,src);
}
int wmain(int argc,wchar_t**argv){
 try{
 check(argc==2,"Expected application path");fs::path exe=argv[1];std::wstring command=L"\""+exe.wstring()+L"\"";STARTUPINFOW info{sizeof(info)};PROCESS_INFORMATION process{};
 check(CreateProcessW(exe.c_str(),command.data(),nullptr,nullptr,FALSE,0,nullptr,exe.parent_path().c_str(),&info,&process),"CreateProcess failed");CloseHandle(process.hThread);
 HWND app=nullptr;wait([&]{app=FindWindowW(L"FlowDrop.NativeDesktop",nullptr);return app&&GetDlgItem(app,101);},"Native window did not appear");
 wait([&]{return IsWindowEnabled(GetDlgItem(app,101))&&text(GetDlgItem(app,1002)).find(L"Sẵn sàng")!=std::wstring::npos;},"Native backend did not become ready",60);
 std::wcout<<L"Native window ready; status: "<<text(GetDlgItem(app,1002))<<std::endl;
 PWSTR local=nullptr;SHGetKnownFolderPath(FOLDERID_LocalAppData,0,nullptr,&local);fs::path state=fs::path(local)/L"FlowDrop"/L"Data"/L"desktop-state.json";CoTaskMemFree(local);
 json metadata;{std::ifstream stream(state);stream>>metadata;}port=metadata.at("port");
 check(GetDlgItem(app,2013)&&GetDlgItem(app,2030)&&GetDlgItem(app,2031)&&GetDlgItem(app,2032),"Folder, update or LAN controls missing");
 auto settings=json::parse(http(L"GET","/api/desktop/settings","",metadata.at("token").get<std::string>(),true));auto token=settings.at("token").get<std::string>();
 auto root=exe.parent_path()/L"native-smoke";fs::remove_all(root);fs::create_directories(root);
 json updated={{"directory",root.string()},{"autoSave",true}};http(L"POST","/api/desktop/settings",updated.dump(),token,true);
 bool peerMode=GetEnvironmentVariableW(L"FLOWDROP_PEER_SMOKE",nullptr,0)>0;
 if(peerMode){wait([&]{return SendMessageW(GetDlgItem(app,2010),LB_GETCOUNT,0,0)>0;},"Native nearby peer list stayed empty",60);SendMessageW(GetDlgItem(app,2010),LB_SETCURSEL,0,0);SendMessageW(app,WM_COMMAND,MAKEWPARAM(2010,LBN_SELCHANGE),(LPARAM)GetDlgItem(app,2010));std::cout<<"Native automatic peer list populated and target selected."<<std::endl;}
 bool large=GetEnvironmentVariableW(L"FLOWDROP_LARGE_SMOKE",nullptr,0)>0;uint64_t largeLength=4ULL*1024*1024*1024+131089;
 auto source=root/L"nguon-kiem-tra.bin",empty=root/L"empty.txt";std::string bytes(1024*1024,'\0');for(size_t i=0;i<bytes.size();i++)bytes[i]=(char)(i%251);
 {std::ofstream stream(source,std::ios::binary);if(large){stream.put('A');stream.seekp(largeLength-1);stream.put('Z');}else stream.write(bytes.data(),bytes.size());}{std::ofstream stream(empty,std::ios::binary);}
 capture(app,exe.parent_path()/L"native-dark-ui.bmp");
 // A real file picker avoids passing process-local HDROP handles between test processes.
 PostMessageW(app,WM_COMMAND,MAKEWPARAM(101,BN_CLICKED),0);
 HWND picker=nullptr;wait([&]{picker=FindWindowW(L"#32770",L"Chọn file để gửi");return picker!=nullptr;},"Native file picker did not open");
 struct EditSearch {HWND edit=nullptr;LONG bottom=-1;} search;
 wait([&]{EnumChildWindows(picker,[](HWND child,LPARAM parameter)->BOOL {auto* found=(EditSearch*)parameter;wchar_t type[64]{};GetClassNameW(child,type,64);if(std::wstring(type)==L"Edit"&&IsWindowVisible(child)&&IsWindowEnabled(child)){RECT r{};GetWindowRect(child,&r);if(r.bottom>found->bottom){found->edit=child;found->bottom=r.bottom;}}return TRUE;},(LPARAM)&search);return search.edit!=nullptr;},"Native file-name edit missing");
 std::wstring names=L"\""+source.wstring()+L"\" \""+empty.wstring()+L"\"";
 SetWindowTextW(search.edit,names.c_str());PostMessageW(picker,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),0);
 wait([&]{return IsWindowEnabled(GetDlgItem(app,peerMode?102:2012));},"Native file picker did not select files");
 SendMessageW(app,WM_COMMAND,MAKEWPARAM(peerMode?102:2012,BN_CLICKED),0);
 std::wstring code;wait([&]{code=text(GetDlgItem(app,1001));return code.size()==8&&code!=L"--------";},"Native send did not produce a code",large?600:40);std::string code8(code.begin(),code.end());
 auto transfer=json::parse(http(L"GET","/api/transfers/"+code8));check(transfer.at("files").size()==2,"Two files missing");
 if(large){check(transfer["files"][0]["size"]==largeLength,"Large metadata size changed");verifyLarge("/api/transfers/"+code8+"/files/"+transfer["files"][0]["id"].get<std::string>(),largeLength);std::cout<<"Large native WinHTTP upload and download passed: "<<largeLength<<" bytes."<<std::endl;}else check(http(L"GET","/api/transfers/"+code8+"/files/"+transfer["files"][0]["id"].get<std::string>())==bytes,"Native upload bytes changed");
 SetWindowTextW(GetDlgItem(app,204),code.c_str());wait([&]{return SendMessageW(GetDlgItem(app,1003),LB_GETCOUNT,0,0)==2;},"Native automatic receive failed",large?600:40);
 auto saved=root/L"nguon-kiem-tra (1).bin";check(fs::exists(saved),"Permanent received copy missing");{std::ifstream stream(saved,std::ios::binary);if(large){check(fs::file_size(saved)==largeLength,"Large permanent copy truncated");char b[65536];uint64_t read=0;while(stream){stream.read(b,sizeof(b));for(std::streamsize i=0;i<stream.gcount();i++)check(b[i]==(read+i==0?'A':read+i==largeLength-1?'Z':0),"Large saved bytes changed");read+=stream.gcount();}check(read==largeLength,"Large saved read incomplete");}else{std::string received((std::istreambuf_iterator<char>(stream)),{});check(received==bytes,"Native received bytes changed");}}
 capture(app,exe.parent_path()/L"native-dark-ui-sent.bmp");
 if(peerMode){
  // The Linux peer checks saved bytes before signalling via the shared test workspace.
  wait([&]{return fs::exists(exe.parent_path()/L"peer-received.ok");},"Selected peer did not accept and save files",60);
  std::cout<<"Native selected-device send produced request and peer permanently saved exact bytes."<<std::endl;
  check(IsWindowVisible(GetDlgItem(app,2022)),"Session view did not open automatically");
  wait([&]{HWND list=GetDlgItem(app,2022);int count=(int)SendMessageW(list,LB_GETCOUNT,0,0);for(int i=0;i<count;i++){int n=(int)SendMessageW(list,LB_GETTEXTLEN,i,0);std::wstring label(n+1,L'\0');SendMessageW(list,LB_GETTEXT,i,(LPARAM)label.data());if(label.find(L"Hoàn tất")!=std::wstring::npos)return true;}return false;},"Native session UI did not learn peer completion",30);
  capture(app,exe.parent_path()/L"native-sessions-completed.bmp");std::cout<<"Native session screen shows receiver-confirmed completion."<<std::endl;
  {std::ofstream trigger(exe.parent_path()/L"peer-request-incoming.json");trigger<<json({{"port",port}}).dump();}
  HWND prompt=nullptr;wait([&]{prompt=FindWindowW(L"#32770",L"FlowDrop · Nhận file");return prompt!=nullptr;},"Native incoming consent prompt did not appear",60);
  PostMessageW(prompt,WM_COMMAND,MAKEWPARAM(IDYES,BN_CLICKED),0);
  wait([&]{return SendMessageW(GetDlgItem(app,1003),LB_GETCOUNT,0,0)==4;},"Native incoming accepted transfer did not save",60);
  {std::ifstream in(root/L"tu-thiet-bi-kia.bin",std::ios::binary);std::string received((std::istreambuf_iterator<char>(in)),{});check(received=="FlowDrop incoming native consent test","Incoming native saved bytes changed");}
  std::cout<<"Native incoming request, consent dialog and remote-source permanent save passed."<<std::endl;
 }
 SendMessageW(app,WM_COMMAND,MAKEWPARAM(109,BN_CLICKED),0);wait([&]{return text(GetDlgItem(app,1001))==L"--------";},"Native revoke failed");check(fs::exists(saved),"Revoke deleted received file");
 auto archiveJob=json::parse(http(L"POST","/api/desktop/archive-folder",json({{"directory",root.string()}}).dump(),token,true));json packed;
 wait([&]{packed=json::parse(http(L"POST","/api/desktop/archive-status",json({{"id",archiveJob.at("id")}}).dump(),token,true));return packed.at("state")=="ready";},"Windows folder job did not complete");
 auto zip=fs::path(wide(packed["result"]["path"].get<std::string>()));check(fs::exists(zip),"Windows folder archive missing");
 http(L"POST","/api/desktop/update/settings",json({{"automatic",false}}).dump(),token,true);
 wait([&]{return SendMessageW(GetDlgItem(app,2031),BM_GETCHECK,0,0)==BST_UNCHECKED;},"Update setting did not reach native checkbox");
 std::cout<<"Native folder/update/LAN controls exist; Windows folder archive and persisted update toggle passed."<<std::endl;

 // Restore a folder produced by the native folder picker, preserving all names.
 SendMessageW(app,WM_COMMAND,MAKEWPARAM(2021,BN_CLICKED),0);
 auto folderSource=root/L"Thư mục gửi";for(const auto& dir:{folderSource,folderSource/L"Con",folderSource/L"Con"/L"Rỗng"}){if(!CreateDirectoryW(dir.c_str(),nullptr)&&GetLastError()!=ERROR_ALREADY_EXISTS)throw std::runtime_error("CreateDirectoryW fixture failed: "+std::to_string(GetLastError()));}
 {HANDLE out=CreateFileW((folderSource/L"Con"/L"Tên gốc.txt").c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);check(out!=INVALID_HANDLE_VALUE,"Unicode fixture CreateFileW failed");const char* content="original folder contents";DWORD written;check(WriteFile(out,content,strlen(content),&written,nullptr),"Unicode fixture write failed");CloseHandle(out);}
 PostMessageW(app,WM_COMMAND,MAKEWPARAM(2013,BN_CLICKED),0);
 HWND folderPicker=nullptr;wait([&]{folderPicker=FindWindowW(L"#32770",L"Chọn thư mục để gửi");return folderPicker!=nullptr;},"Native folder picker did not open");
 EditSearch folderSearch;
 wait([&]{EnumChildWindows(folderPicker,[](HWND child,LPARAM parameter)->BOOL{auto* found=(EditSearch*)parameter;wchar_t type[64]{};GetClassNameW(child,type,64);if(std::wstring(type)==L"Edit"&&IsWindowVisible(child)&&IsWindowEnabled(child)){RECT r{};GetWindowRect(child,&r);if(r.bottom>found->bottom){found->edit=child;found->bottom=r.bottom;}}return TRUE;},(LPARAM)&folderSearch);return folderSearch.edit!=nullptr;},"Native folder picker edit missing");
 SetWindowTextW(folderSearch.edit,folderSource.c_str());PostMessageW(folderPicker,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),0);
 wait([&]{return text(GetDlgItem(app,1002)).find(L"Thư mục đã sẵn sàng")!=std::wstring::npos;},"Native folder preparation did not finish");
 SendMessageW(app,WM_COMMAND,MAKEWPARAM(2012,BN_CLICKED),0);std::wstring folderCode;wait([&]{folderCode=text(GetDlgItem(app,1001));return folderCode.size()==8&&folderCode!=L"--------";},"Native folder did not produce a code");
 std::string folderCode8(folderCode.begin(),folderCode.end());auto folderMetadata=json::parse(http(L"GET","/api/transfers/"+folderCode8));check(folderMetadata["files"].size()==1&&folderMetadata["files"][0]["type"]=="application/vnd.flowdrop.folder+zip","Native folder did not carry explicit folder type");
 int before=(int)SendMessageW(GetDlgItem(app,1003),LB_GETCOUNT,0,0);SetWindowTextW(GetDlgItem(app,204),folderCode.c_str());wait([&]{return SendMessageW(GetDlgItem(app,1003),LB_GETCOUNT,0,0)==before+1;},"Native folder receive did not complete");
 auto folderCopy=root/L"Thư mục gửi (1)";DWORD attributes=GetFileAttributesW((folderCopy/L"Con"/L"Rỗng").c_str());check(attributes!=INVALID_FILE_ATTRIBUTES&&(attributes&FILE_ATTRIBUTE_DIRECTORY),"Empty nested folder was lost");{HANDLE in=CreateFileW((folderCopy/L"Con"/L"Tên gốc.txt").c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);check(in!=INVALID_HANDLE_VALUE,"Restored Unicode filename missing");char content[100]{};DWORD read;check(ReadFile(in,content,99,&read,nullptr),"Restored file read failed");CloseHandle(in);check(std::string(content,read)=="original folder contents","Folder filename/content changed");}
 SendMessageW(app,WM_COMMAND,MAKEWPARAM(106,BN_CLICKED),0);wait([&]{return text(GetDlgItem(app,1002)).find(L"Đã mở thư mục nhận file")!=std::wstring::npos;},"Native Windows folder open failed");
 HWND explorer=nullptr;wait([&]{EnumWindows([](HWND child,LPARAM p)->BOOL{auto* found=(HWND*)p;if(IsWindowVisible(child)&&text(child).find(L"native-smoke")!=std::wstring::npos){*found=child;return FALSE;}return TRUE;},(LPARAM)&explorer);return explorer!=nullptr;},"Explorer folder window did not become visible");PostMessageW(explorer,WM_CLOSE,0,0);
 std::cout<<"Native folder picker, explicit folder transfer, exact structure/names, conflict root and visible Explorer window passed."<<std::endl;
 PostMessageW(app,WM_CLOSE,0,0);check(WaitForSingleObject(process.hProcess,10000)==WAIT_OBJECT_0,"Native application did not close");CloseHandle(process.hProcess);
 std::cout<<"PASS: native window, backend startup, file picker, 1 MiB or >4 GiB + empty upload, exact bytes, automatic permanent receive, no overwrite, revoke and close."<<std::endl;return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL: "<<e.what()<<std::endl;if(auto app=FindWindowW(L"FlowDrop.NativeDesktop",nullptr)){std::wcerr<<L"Status: "<<text(GetDlgItem(app,1002))<<std::endl;PostMessageW(app,WM_CLOSE,0,0);}return 1;}
}
