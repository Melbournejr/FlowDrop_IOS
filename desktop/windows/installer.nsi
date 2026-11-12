Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
Var UpdateMode
Function .onInit
 ${GetParameters} $R0
 ${GetOptions} $R0 "/UPDATE" $R1
 IfErrors +2 0
 StrCpy $UpdateMode "yes"
FunctionEnd
Function .onInstSuccess
 StrCmp $UpdateMode "yes" 0 +2
 Exec '$\"$INSTDIR\FlowDrop.exe$\"'
FunctionEnd
!define APPNAME "FlowDrop"
!define VERSION "1.13.0"
Name "FlowDrop"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\FlowDrop"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "1.13.0.0"
VIAddVersionKey /LANG=1033 "ProductName" "FlowDrop"
VIAddVersionKey /LANG=1033 "FileDescription" "FlowDrop Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.13.0"
VIAddVersionKey /LANG=1033 "LegalCopyright" "FlowDrop"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchFlowDrop"
!define MUI_FINISHPAGE_RUN_TEXT "Mo FlowDrop"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Section "FlowDrop" SEC_MAIN
 IfFileExists "$INSTDIR\FlowDrop.exe" 0 +3
 ExecWait '$\"$INSTDIR\FlowDrop.exe$\" --shutdown'
 Sleep 500
 IfFileExists "$INSTDIR\runtime\node.exe" 0 +4
 ExecWait '$\"$INSTDIR\runtime\node.exe$\" $\"$INSTDIR\scripts\stop.mjs$\"'
 Sleep 500
 ClearErrors
 SetOutPath "$INSTDIR"
 File /r "${PAYLOAD_DIR}/*"
 CreateDirectory "$SMPROGRAMS\FlowDrop"
 CreateShortcut "$SMPROGRAMS\FlowDrop\FlowDrop.lnk" "$INSTDIR\FlowDrop.exe"
 CreateShortcut "$SMPROGRAMS\FlowDrop\Stop FlowDrop.lnk" "$SYSDIR\wscript.exe" '$\"$INSTDIR\Stop-FlowDrop.vbs$\"'
 CreateShortcut "$DESKTOP\FlowDrop.lnk" "$INSTDIR\FlowDrop.exe"
 CreateShortcut "$SENDTO\FlowDrop.lnk" "$INSTDIR\FlowDrop.exe" "--send-files" "$INSTDIR\FlowDrop.exe" 0
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop" "DisplayName" "FlowDrop"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop" "DisplayVersion" "1.13.0"
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop" "NoRepair" 1
SectionEnd
Function LaunchFlowDrop
 Exec '$\"$INSTDIR\FlowDrop.exe$\"'
FunctionEnd
Section "Uninstall"
 ExecWait '$\"$INSTDIR\FlowDrop.exe$\" --shutdown'
 Sleep 300
 ExecWait '$\"$INSTDIR\runtime\node.exe$\" $\"$INSTDIR\scripts\stop.mjs$\"'
 Delete "$SENDTO\FlowDrop.lnk"
 Delete "$DESKTOP\FlowDrop.lnk"
 RMDir /r "$SMPROGRAMS\FlowDrop"
 RMDir /r "$INSTDIR"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FlowDrop"
SectionEnd
