"""Reviewed UI-driver adaptations in disposable test copies; never application source.

The original tests, fixtures, assertions and time limits remain in Git unchanged.
Only driving an initialized OS dialog differs from the original message shortcut.
"""
from .common import Blocked


def once(source, before, after):
    if source.count(before) != 1:
        raise Blocked('Reviewed test-driver adaptation no longer matches the original source')
    return source.replace(before, after, 1)


def windows_driver(name, source):
    if name == 'windows-native-smoke':
        function = '''void runtimeSetText(HWND edit,const std::wstring& value){
 DWORD_PTR accepted=0;SetLastError(0);
 auto sent=SendMessageTimeoutW(edit,WM_SETTEXT,0,(LPARAM)value.c_str(),SMTO_ABORTIFHUNG,5000,&accepted);
 check(sent&&accepted,("Cross-process WM_SETTEXT failed; Win32 error="+std::to_string(GetLastError())).c_str());
 wait([&]{return text(edit)==value;},"Native dialog did not retain the actual input");
}
void runtimeDialogInput(HWND dialog,HWND edit,const std::wstring& value){
 wait([&]{HWND ok=GetDlgItem(dialog,IDOK);return IsWindowVisible(dialog)&&ok&&IsWindowVisible(ok)&&IsWindowEnabled(ok);},"Native dialog primary button not ready");
 Sleep(750);runtimeSetText(edit,value);
 PostMessageW(GetDlgItem(dialog,IDOK),BM_CLICK,0,0);
}
'''
        source = once(source, 'int wmain(int argc,wchar_t**argv){', function + 'int wmain(int argc,wchar_t**argv){')
        source = once(source,
            'SetWindowTextW(search.edit,names.c_str());PostMessageW(picker,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),0);',
            'runtimeDialogInput(picker,search.edit,names);')
        source = once(source,
            'SetWindowTextW(folderSearch.edit,folderSource.c_str());PostMessageW(folderPicker,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),0);',
            'runtimeDialogInput(folderPicker,folderSearch.edit,folderSource.wstring());')
        for name in ['code', 'folderCode']:
            source = once(source, 'SetWindowTextW(GetDlgItem(app,204),' + name + '.c_str());',
                          'runtimeSetText(GetDlgItem(app,204),' + name + ');')
        source = once(source,
            'std::wcout<<L"Native window ready; status: "<<text(GetDlgItem(app,1002))<<std::endl;',
            '''{auto value=text(GetDlgItem(app,1002));int n=WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),nullptr,0,nullptr,nullptr);std::string log(n,' ');if(n)WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),log.data(),n,nullptr,nullptr);std::cout<<"Native window ready; status: "<<log<<std::endl;}''')
    elif name == 'windows-shell-smoke':
        source = once(source,
            'SetDlgItemTextW(rename,6002,L"Máy kiểm thử FlowDrop");PostMessageW(rename,WM_COMMAND,IDOK,0);',
            '''waitFor([&]{HWND ok=GetDlgItem(rename,IDOK);return IsWindowVisible(rename)&&ok&&IsWindowVisible(ok)&&IsWindowEnabled(ok);},"Rename controls not ready",10);
 Sleep(750);DWORD_PTR accepted=0;SetLastError(0);
 auto changed=SendMessageTimeoutW(GetDlgItem(rename,6002),WM_SETTEXT,0,(LPARAM)L"Máy kiểm thử FlowDrop",SMTO_ABORTIFHUNG,5000,&accepted);
 check(changed&&accepted,("Rename WM_SETTEXT failed; Win32 error="+std::to_string(GetLastError())).c_str());
 check(remoteText(GetDlgItem(rename,6002))==L"Máy kiểm thử FlowDrop","Rename input was not retained");
 PostMessageW(GetDlgItem(rename,IDOK),BM_CLICK,0,0);''')
    else:
        raise Blocked('Unreviewed Windows helper')
    return source
