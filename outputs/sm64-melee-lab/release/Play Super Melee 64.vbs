Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
launcher = root & "\Super Melee 64.exe"
If Not fs.FileExists(launcher) Then
  launcher = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Super Melee 64\SuperMelee64.exe"
End If
If fs.FileExists(launcher) Then
  shell.Run Chr(34) & launcher & Chr(34), 1, False
Else
  MsgBox "Install the Windows Setup.exe from the project release page, then open Super Melee 64 from the Start menu.", 48, "Super Melee 64"
  shell.Run "https://github.com/memelees/super-melee-64/releases", 1, False
End If
