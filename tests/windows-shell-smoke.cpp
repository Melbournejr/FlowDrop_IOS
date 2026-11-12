#define wWinMain flowdrop_app_entry
#include "../desktop/windows/FlowDrop.cpp"
#undef wWinMain
#include <iostream>
#include <fstream>
void check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
void waitFor(std::function<bool()> condition,const char* why,unsigned seconds=45){auto until=GetTickCount64()+seconds*1000;while(GetTickCount64()<until){if(condition())return;Sleep(100);}throw std::runtime_error(why);}
std::wstring remoteText(HWND item){wchar_t value[1024]{};DWORD_PTR result=0;SendMessageTimeoutW(item,WM_GETTEXT,1024,(LPARAM)value,SMTO_ABORTIFHUNG,2000,&result);return value;}
PROCESS_INFORMATION launch(const fs::path& exe,const std::wstring& args){std::wstring command=L"\""+exe.wstring()+L"\" "+args;STARTUPINFOW startup{sizeof(startup)};PROCESS_INFORMATION process{};check(CreateProcessW(exe.c_str(),command.data(),nullptr,nullptr,FALSE,0,nullptr,exe.parent_path().c_str(),&startup,&process),"Unable to start app");CloseHandle(process.hThread);return process;}
HWND queue(HWND app){HWND child=nullptr;while((child=FindWindowExW(app,child,L"LISTBOX",nullptr)))if(GetDlgCtrlID(child)==0)return child;return nullptr;}
int wmain(int argc,wchar_t** argv){
 HWND app=nullptr;PROCESS_INFORMATION first{};try{
 check(argc==2,"Expected FlowDrop.exe path");fs::path exe=argv[1],root=exe.parent_path()/L"shell-smoke";CreateDirectoryW(root.c_str(),nullptr);
 auto a=root/L"Tài liệu thứ nhất.txt",b=root/L"Tài liệu 2 📁.txt",c=root/L"Third file.txt";
 for(const auto& file:{a,b,c}){auto handle=CreateFileW(file.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);check(handle!=INVALID_HANDLE_VALUE,"Unable to create Unicode fixture");DWORD count=0;WriteFile(handle,"test",4,&count,nullptr);CloseHandle(handle);}
 first=launch(exe,L"--send-files "+quote(a)+L" "+quote(b));
 waitFor([&]{app=FindWindowW(CLASS_NAME,nullptr);return app&&GetDlgItem(app,101)&&IsWindowEnabled(GetDlgItem(app,101))&&!remoteText(GetDlgItem(app,1002)).empty()&&(remoteText(GetDlgItem(app,1002)).find(L"Sẵn sàng")!=std::wstring::npos||remoteText(GetDlgItem(app,1002)).find(L"Đã thêm file")!=std::wstring::npos);},"Backend did not become ready");
 waitFor([&]{return SendMessageW(queue(app),LB_GETCOUNT,0,0)==2;},"Cold-start Send To did not queue two files");
 PWSTR local=nullptr;SHGetKnownFolderPath(FOLDERID_LocalAppData,0,nullptr,&local);auto stateFile=fs::path(local)/L"FlowDrop"/L"Data"/L"desktop-state.json";CoTaskMemFree(local);json state;{std::ifstream stream(stateFile);stream>>state;}serverPort=state.at("port").get<unsigned>();desktopToken=state.at("token").get<std::string>();auto settings=requestJson(L"GET","/api/desktop/settings",nullptr,desktopToken);desktopToken=settings.at("token");auto before=requestJson(L"GET","/api/config");
 auto second=launch(exe,L"--send-files "+quote(b)+L" "+quote(c));check(WaitForSingleObject(second.hProcess,15000)==WAIT_OBJECT_0,"Second invocation did not return");DWORD code=1;GetExitCodeProcess(second.hProcess,&code);CloseHandle(second.hProcess);check(code==0,"Existing-instance IPC rejected files");
 waitFor([&]{return SendMessageW(queue(app),LB_GETCOUNT,0,0)==3;},"Existing instance lost files or duplicated selection");
 PostMessageW(app,WM_COMMAND,2033,0);HWND rename=nullptr;waitFor([&]{rename=FindWindowW(L"#32770",L"Đổi tên thiết bị");return rename&&GetDlgItem(rename,6002);},"Rename dialog missing",10);SetDlgItemTextW(rename,6002,L"Máy kiểm thử FlowDrop");PostMessageW(rename,WM_COMMAND,IDOK,0);
 waitFor([&]{try{return requestJson(L"GET","/api/config").value("deviceName",std::string())=="Máy kiểm thử FlowDrop";}catch(...){return false;}},"Rename did not reach live config",10);check(requestJson(L"GET","/api/config").at("deviceId")==before.at("deviceId"),"Renaming changed device ID");check(SendMessageW(queue(app),LB_GETCOUNT,0,0)==3,"Rename disturbed selected files");
 // Invalid IPC cannot replace a valid selection.
 auto invalid=json::array({"relative.txt"}).dump();COPYDATASTRUCT packet{SHELL_FILES,(DWORD)invalid.size(),invalid.data()};check(!SendMessageW(app,WM_COPYDATA,0,(LPARAM)&packet),"Relative shell path accepted");check(SendMessageW(queue(app),LB_GETCOUNT,0,0)==3,"Invalid IPC changed selected files");
 // Exercise the real native send path against the protected 1.13 backend.
 bool protectedSettings=false;try{requestJson(L"GET","/api/desktop/settings");}catch(...){protectedSettings=true;}check(protectedSettings,"Native bootstrap token leaked through unauthenticated settings");
 PostMessageW(app,WM_COMMAND,2012,0);std::string share;
 waitFor([&]{share=utf8(remoteText(GetDlgItem(app,1001)));return validCode(share);},"Native file creation failed with local capability",30);
 auto transfer=requestJson(L"GET","/api/transfers/"+share);check(transfer.at("files").size()==3,"Native send lost selected files");
 PostMessageW(app,WM_COMMAND,109,0);waitFor([&]{return remoteText(GetDlgItem(app,1001))==L"--------";},"Native revoke failed",15);
 bool revoked=false;try{requestJson(L"GET","/api/transfers/"+share);}catch(...){revoked=true;}check(revoked,"Revoked share remained readable");
 PostMessageW(app,WM_CLOSE,0,0);check(WaitForSingleObject(first.hProcess,15000)==WAIT_OBJECT_0,"App failed to close");CloseHandle(first.hProcess);first.hProcess=nullptr;
 first=launch(exe,L"");waitFor([&]{app=FindWindowW(CLASS_NAME,nullptr);return app&&GetDlgItem(app,101)&&IsWindowEnabled(GetDlgItem(app,101))&&!remoteText(GetDlgItem(app,1002)).empty()&&(remoteText(GetDlgItem(app,1002)).find(L"Sẵn sàng")!=std::wstring::npos||remoteText(GetDlgItem(app,1002)).find(L"Đã thêm file")!=std::wstring::npos);},"Restart failed");{std::ifstream stream(stateFile);stream>>state;}serverPort=state.at("port").get<unsigned>();check(requestJson(L"GET","/api/config").value("deviceName",std::string())=="Máy kiểm thử FlowDrop","Friendly name did not persist across restart");
 PostMessageW(app,WM_CLOSE,0,0);WaitForSingleObject(first.hProcess,15000);CloseHandle(first.hProcess);first.hProcess=nullptr;
 std::cout<<"PASS: cold-start multi-file Send To, existing-instance IPC merge/dedup, Unicode paths, invalid-path rejection, native rename dialog, stable identity, persisted name, protected bootstrap, authenticated native send and revoke."<<std::endl;return 0;
 }catch(const std::exception& error){if(app)std::cerr<<"Status: "<<utf8(remoteText(GetDlgItem(app,1002)))<<std::endl;if(app)PostMessageW(app,WM_CLOSE,0,0);if(first.hProcess){WaitForSingleObject(first.hProcess,5000);CloseHandle(first.hProcess);}std::cerr<<"FAIL: "<<error.what()<<std::endl;return 1;}
}
