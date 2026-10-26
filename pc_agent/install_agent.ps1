# install_agent.ps1 - Rony PC Agent installer
# Uses pythonw.exe (no console window) via Task Scheduler
# agent.py writes its own log via Python logging module
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  RONY PC AGENT - INSTALL"
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$agentPath  = Join-Path $scriptDir "agent.py"
$outLogPath = Join-Path $scriptDir "agent_out.txt"

# Find pythonw.exe - prefer system Python313, local copy may be empty/placeholder
$pythonwPath = $null
# 1. System Python313 pythonw.exe
$p = "C:\Program Files\Python313\pythonw.exe"
if ((Test-Path $p) -and (Get-Item $p).Length -gt 0) { $pythonwPath = $p }
# 2. Fallback to python.exe (has console, but works)
if (-not $pythonwPath) {
    $p = "C:\Program Files\Python313\python.exe"
    if ((Test-Path $p) -and (Get-Item $p).Length -gt 0) { $pythonwPath = $p }
}
# 3. Fallback to PATH python
if (-not $pythonwPath) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonwPath = $cmd.Source }
}
if (-not $pythonwPath) {
    Write-Host "[ERROR] Python not found!" -ForegroundColor Red
    Read-Host "Press Enter"
    exit 1
}

Write-Host "[1/4] Launcher : $pythonwPath"
Write-Host "       Agent   : $agentPath"
Write-Host "       Log     : $outLogPath"
Write-Host ""

# Step 2: Remove legacy VBS / Registry Run autostart
Write-Host "[2/4] Removing legacy autostart..." -ForegroundColor Yellow
$startup = [System.Environment]::GetFolderPath("Startup")
$oldVbs  = Join-Path $startup "RonyPCAgent.vbs"
if (Test-Path $oldVbs) { Remove-Item $oldVbs -Force; Write-Host '       Removed old VBS' }
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Get-ItemProperty -Path $runKey -Name "RonyPCAgent" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $runKey -Name "RonyPCAgent" -ErrorAction SilentlyContinue
    Write-Host "       Removed old Registry Run key"
}

# Step 3: Register Task Scheduler via schtasks.exe + XML
Write-Host "[3/4] Registering Task Scheduler task..." -ForegroundColor Yellow
$taskName    = "RonyPCAgent"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
schtasks /Delete /TN $taskName /F 2>&1 | Out-Null

$xmlPath = Join-Path $env:TEMP "rony_task.xml"
$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Rony PC Telegram Agent - auto-start at logon</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$currentUser</UserId>
      <Delay>PT15S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$currentUser</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$pythonwPath</Command>
      <Arguments>-u "$agentPath"</Arguments>
      <WorkingDirectory>$scriptDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

[System.IO.File]::WriteAllText($xmlPath, $taskXml, [System.Text.Encoding]::Unicode)
schtasks /Create /TN $taskName /XML $xmlPath /F
$schtasksOk = ($LASTEXITCODE -eq 0)
Remove-Item $xmlPath -Force -ErrorAction SilentlyContinue

if ($schtasksOk) {
    Write-Host "       OK: Task Scheduler task registered" -ForegroundColor Green
    Write-Host "       Trigger: logon + 15s delay, Restart: 3x on failure"
} else {
    Write-Host "       WARN: schtasks failed - falling back to Registry Run" -ForegroundColor Yellow
    $runValue = "`"$pythonwPath`" -u `"$agentPath`""
    Set-ItemProperty -Path $runKey -Name "RonyPCAgent" -Value $runValue -ErrorAction SilentlyContinue
    Write-Host "       Fallback: Registry Run key set"
}

# Step 4: Kill existing and launch agent now
Write-Host "[4/4] Launching agent now..." -ForegroundColor Yellow
# Kill old instances
taskkill /F /FI 'IMAGENAME eq pythonw.exe' 2>&1 | Out-Null
taskkill /F /FI 'IMAGENAME eq python.exe' 2>&1 | Out-Null
Start-Sleep -Seconds 1
# Launch with hidden window
Start-Process -FilePath $pythonwPath -ArgumentList "-u `"$agentPath`"" -WindowStyle Hidden -WorkingDirectory $scriptDir
Start-Sleep -Seconds 5
# Detect process name
$exeName = if ($pythonwPath -match 'pythonw') { 'pythonw.exe' } else { 'python.exe' }
$taskListOut = & tasklist /FI "IMAGENAME eq $exeName" /NH 2>&1
if ($taskListOut -match $exeName) {
    Write-Host "       OK: Agent is running!" -ForegroundColor Green
} else {
    Write-Host "       NOTE: Process may not be visible here (check Task Manager)" -ForegroundColor Yellow
}

# Verify log file was updated
Start-Sleep -Seconds 3
if (Test-Path $outLogPath) {
    $logSize = (Get-Item $outLogPath).Length
    $logAge  = ((Get-Date) - (Get-Item $outLogPath).LastWriteTime).TotalSeconds
    Write-Host "       Log: $logSize bytes, updated $([int]$logAge)s ago" -ForegroundColor Cyan
    if ($logAge -lt 30) {
        Write-Host "       CONFIRMED: Agent wrote to log - it is running!" -ForegroundColor Green
    } else {
        Write-Host "       WARNING: Log not recently updated - agent may have crashed!" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  DONE! Agent will auto-start 15s after logon."
Write-Host "  Log    : $outLogPath"
Write-Host "  Task   : $taskName (Task Scheduler)"
Write-Host "  Launch : $pythonwPath"
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
Start-Sleep -Seconds 3
