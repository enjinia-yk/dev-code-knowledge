Set ws = CreateObject("WScript.Shell")
Dim batPath
batPath = ws.ExpandEnvironmentStrings("%USERPROFILE%\workspace\dev-code-knowledge\start.bat")
ws.Run "cmd /c """ & batPath & """", 0, False
