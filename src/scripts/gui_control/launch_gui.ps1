#Requires -Version 5.1
<#
.SYNOPSIS
    One-click launcher for the LCA Agent Gradio GUI (foreground mode).

.DESCRIPTION
    Launches the Gradio GUI in the foreground and binds the whole process tree
    (uv / python / gradio) to a Windows Job Object with KILL_ON_JOB_CLOSE.
    When this window is closed or Ctrl+C is pressed, the Job handle closes and
    the entire process tree is terminated automatically by the OS, so no gradio
    orphan process remains.

    This script lives under src/scripts/gui_control/, alongside start_gui.py etc.
    ProjectRoot is 3 levels up (gui_control -> scripts -> src -> project root).

.NOTES
    Run via src/scripts/_launch_gui.bat, or right-click -> Run with PowerShell.
#>

$ErrorActionPreference = 'Stop'
# Script lives in src/scripts/gui_control/, go up 3 levels to project root
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..\..\..') | Select-Object -ExpandProperty Path
Set-Location $ProjectRoot

$Port      = 7860
$Url       = "http://127.0.0.1:$Port"
$GuiScript = Join-Path $ProjectRoot 'src\GUI\main.py'

# ---------- Pre-flight checks ----------
if (-not (Test-Path $GuiScript)) {
    Write-Host "GUI entry script not found: $GuiScript" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found in PATH. Please install uv and restart your terminal." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "Port $Port is already in use (PID=$($busy.OwningProcess -join ','))." -ForegroundColor Yellow
    Write-Host "Run this first: python src\scripts\gui_control\stop_gui.py" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# ---------- Create Job Object: child processes die when this script exits ----------
$sig = @'
using System;
using System.Runtime.InteropServices;

public static class JobMgr
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

    [DllImport("kernel32.dll")]
    public static extern bool SetInformationJobObject(IntPtr hJob, int infoType, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

    [DllImport("kernel32.dll")]
    public static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr hObject);

    public const int  JobObjectExtendedLimitInformation = 9;
    public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
    public const uint PROCESS_ALL_ACCESS = 0x1F0FFF;
}

[StructLayout(LayoutKind.Sequential)]
public struct JOBOBJECT_BASIC_LIMIT_INFORMATION
{
    public long PerProcessUserTimeLimit;
    public long PerJobUserTimeLimit;
    public uint LimitFlags;
    public uint MinimumWorkingSetSize;
    public uint MaximumWorkingSetSize;
    public uint ActiveProcessLimit;
    public long Affinity;
    public uint PriorityClass;
    public uint SchedulingClass;
}

[StructLayout(LayoutKind.Sequential)]
public struct IO_COUNTERS
{
    public ulong ReadOperationCount;
    public ulong WriteOperationCount;
    public ulong OtherOperationCount;
    public ulong ReadTransferCount;
    public ulong WriteTransferCount;
    public ulong OtherTransferCount;
}

[StructLayout(LayoutKind.Sequential)]
public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
{
    public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
    public IO_COUNTERS IoInfo;
    public uint ProcessMemoryLimit;
    public uint JobMemoryLimit;
    public uint PeakProcessMemoryUsed;
    public uint PeakJobMemoryUsed;
}
'@
Add-Type -TypeDefinition $sig

$job  = [JobMgr]::CreateJobObject([IntPtr]::Zero, $null)
$info = New-Object JOBOBJECT_EXTENDED_LIMIT_INFORMATION
$info.BasicLimitInformation.LimitFlags = [JobMgr]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
# Hardcoded size: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 112 bytes
#   BASIC_LIMIT_INFO (48) + IO_COUNTERS (48) + 4*uint (16) = 112
$size  = 112
$ptr   = [System.Runtime.InteropServices.Marshal]::AllocHGlobal($size)
[System.Runtime.InteropServices.Marshal]::StructureToPtr($info, $ptr, $false)
[void][JobMgr]::SetInformationJobObject($job, [JobMgr]::JobObjectExtendedLimitInformation, $ptr, $size)
[System.Runtime.InteropServices.Marshal]::FreeHGlobal($ptr)

# ---------- Launch GUI ----------
Write-Host "Starting Gradio GUI..." -ForegroundColor Green
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = 'uv'
$psi.Arguments        = "run python `"$GuiScript`""
$psi.UseShellExecute  = $false
$psi.WorkingDirectory = $ProjectRoot
$psi.CreateNoWindow   = $false
$proc = [System.Diagnostics.Process]::Start($psi)

# Bind the uv process to the Job; its children (python / gradio) inherit it
$hProc = [JobMgr]::OpenProcess([JobMgr]::PROCESS_ALL_ACCESS, $false, $proc.Id)
[void][JobMgr]::AssignProcessToJobObject($job, $hProc)
[void][JobMgr]::CloseHandle($hProc)

Write-Host ("GUI process started (PID: {0}), bound to Job. Closing this window will terminate it." -f $proc.Id) -ForegroundColor Cyan
Write-Host "URL: $Url" -ForegroundColor Cyan
Write-Host "Press Ctrl+C or close this window to stop the GUI." -ForegroundColor DarkGray

# ---------- Wait for port to be ready, then open browser ----------
$opened = $false
while (-not $proc.HasExited -and -not $opened) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
        Start-Process $Url
        $opened = $true
        Write-Host "Opened in default browser: $Url" -ForegroundColor Green
    } catch {
        # Port not ready yet, keep waiting
    }
}

# ---------- Wait for process exit / cleanup ----------
try {
    $proc.WaitForExit()
}
finally {
    if ($proc -and -not $proc.HasExited) {
        taskkill /PID $proc.Id /T /F 2>$null | Out-Null
    }
    if ($job -ne [IntPtr]::Zero) { [void][JobMgr]::CloseHandle($job) }
    Write-Host "GUI stopped." -ForegroundColor Green
}
