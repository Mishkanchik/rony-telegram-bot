Dim sShell, sPython, sAgent, sLog, sCmd

Set sShell = CreateObject("WScript.Shell")

' Читаємо шлях до агента з реєстру (прописується install_startup.bat)
On Error Resume Next
sAgent = sShell.RegRead("HKCU\Software\RonyPCAgent\AgentPath")
sPython = sShell.RegRead("HKCU\Software\RonyPCAgent\PythonPath")
On Error GoTo 0

If sAgent = "" Then
    MsgBox "ERROR: AgentPath not found in registry." & vbCrLf & "Run install_startup.bat first!", vbCritical, "Rony PC Agent"
    WScript.Quit 1
End If

If sPython = "" Then
    sPython = "C:\Program Files\Python313\python.exe"
End If

' Лог поруч з agent.py
sLog = Left(sAgent, InStrRev(sAgent, "\")) & "agent_log.txt"

' Запускаємо python.exe приховано, вивід у лог
sCmd = "cmd /c """ & sPython & """ -u """ & sAgent & """ >> """ & sLog & """ 2>&1"

' NOTE: Do NOT set CurrentDirectory — WSH cannot handle Unicode/non-ASCII paths
' (error 0x8007007B). All paths in sCmd are already fully qualified.
sShell.Run sCmd, 0, False
