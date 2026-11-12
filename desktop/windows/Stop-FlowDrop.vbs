Option Explicit
Dim shell, fso, appDir, env, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set env = shell.Environment("PROCESS")
env("FLOWDROP_DATA_DIR") = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\FlowDrop\Data"
cmd = Chr(34) & appDir & "\runtime\node.exe" & Chr(34) & " " & Chr(34) & appDir & "\scripts\stop.mjs" & Chr(34)
shell.Run cmd, 0, True
