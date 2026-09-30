Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

sh.Run """" & dir & "\venv\Scripts\pythonw.exe"" pc-bridge.py --kiosk", 0, False