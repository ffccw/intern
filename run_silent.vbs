Set WshShell = CreateObject("WScript.Shell")
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
strPS1 = strDir & "\run_daily.ps1"
WshShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & strPS1 & """", 0, False
