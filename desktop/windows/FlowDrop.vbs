Option Explicit
Dim shell, fso, appDir
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = appDir
shell.Run Chr(34) & appDir & "\FlowDrop.exe" & Chr(34), 1, False
