# =============================================================================
#  驱动 NSIS 安装向导走完所有页面并截图
#
#  关键点：必须用 PostMessage(WM_COMMAND, IDOK) 驱动，**不能用 BM_CLICK**。
#  BM_CLICK 会产生延迟的重复点击，导致自定义页面刚创建就被瞬间跳过，
#  排查起来非常费劲，这里记下来免得以后再踩。
#
#  用法：
#    powershell -ExecutionPolicy Bypass -File .\tools\capture-screenshots.ps1
#    powershell -ExecutionPolicy Bypass -File .\tools\capture-screenshots.ps1 `
#        -ProcName 'MyApp-Setup' -Exe 'D:\out\MyApp-Setup.exe' -Prefix g
# =============================================================================
param(
    [string]$ProcName = '我的小工具-1.0.0-Setup-PerUser',
    [string]$Exe = (Join-Path (Split-Path $PSScriptRoot -Parent) 'out\我的小工具-1.0.0-Setup-PerUser.exe'),
    [string]$Prefix = 's',
    [string]$OutDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'screenshots')
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms, System.Drawing

Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class Drv {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public static List<IntPtr> Children(IntPtr p0) {
    List<IntPtr> l = new List<IntPtr>();
    EnumChildWindows(p0, delegate(IntPtr h, IntPtr p) { l.Add(h); return true; }, IntPtr.Zero);
    return l;
  }
  public static string Text(IntPtr h) { StringBuilder s = new StringBuilder(512); GetWindowTextW(h, s, 512); return s.ToString(); }
  public static string Cls(IntPtr h) { StringBuilder s = new StringBuilder(256); GetClassNameW(h, s, 256); return s.ToString(); }
}
"@

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$log = Join-Path $env:TEMP 'capture-screenshots.log'
Set-Content $log '=== capture-screenshots ===' -Encoding UTF8
function Log($s) { $s | Add-Content $log -Encoding UTF8; Write-Host $s }

function Get-H {
    $p = Get-Process $ProcName -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $p) { return [IntPtr]::Zero }
    $p.Refresh(); return $p.MainWindowHandle
}

function Get-PageTitle {
    $h = Get-H
    if ($h -eq [IntPtr]::Zero) { return '(no window)' }
    foreach ($c in [Drv]::Children($h)) {
        if (-not [Drv]::IsWindowVisible($c)) { continue }
        $id = [Drv]::GetDlgCtrlID($c)
        if ($id -eq 1037 -or $id -eq 1201) { return ([Drv]::Text($c) -replace "`r?`n", ' ') }
    }
    return '(unknown)'
}

function Shot([string]$name) {
    $h = Get-H
    if ($h -eq [IntPtr]::Zero) { return }
    $r = New-Object Drv+RECT
    [Drv]::GetWindowRect($h, [ref]$r) | Out-Null
    $w = $r.R - $r.L; $ht = $r.B - $r.T
    if ($w -le 0 -or $ht -le 0) { return }
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
    $bmp.Save((Join-Path $OutDir $name), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}

function FindCtrl([scriptblock]$pred) {
    $h = Get-H
    if ($h -eq [IntPtr]::Zero) { return [IntPtr]::Zero }
    foreach ($c in [Drv]::Children($h)) {
        if (-not [Drv]::IsWindowVisible($c)) { continue }
        if (& $pred $c) { return $c }
    }
    return [IntPtr]::Zero
}

function PostNext {
    $h = Get-H
    # NSIS 的按钮 ID 固定：1=下一步/安装/完成，2=取消，3=上一步。
    # 注意 Win32 里"分组框"的类名也是 Button，所以必须按 ID 匹配。
    $btn = FindCtrl { param($c) ([Drv]::GetDlgCtrlID($c) -eq 1) -and ([Drv]::Cls($c) -eq 'Button') -and ([Drv]::Text($c) -ne '') }
    if ($btn -eq [IntPtr]::Zero) { Log '  -> 找不到下一步按钮'; return $false }
    if (-not [Drv]::IsWindowEnabled($btn)) { Log '  -> 下一步按钮当前不可用'; return $false }
    Log ('  -> PostMessage IDOK  [{0}]' -f [Drv]::Text($btn))
    [Drv]::PostMessage($h, 0x0111, [IntPtr]1, $btn) | Out-Null
    return $true
}

function AcceptLicense {
    $chk = FindCtrl { param($c) ([Drv]::Cls($c) -eq 'Button') -and ([Drv]::Text($c) -match '我接受') }
    if ($chk -eq [IntPtr]::Zero) { return }
    $st = [int][Drv]::SendMessage($chk, 0x00F0, [IntPtr]::Zero, [IntPtr]::Zero)
    if ($st -ne 1) {
        Log '  -> 勾选「我接受」'
        [Drv]::PostMessage($chk, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
        Start-Sleep -Milliseconds 600
    }
}

if (-not (Test-Path $Exe)) { throw "找不到安装包：$Exe" }

Get-Process $ProcName -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
Start-Process $Exe | Out-Null
Start-Sleep -Seconds 4

for ($i = 1; $i -le 10; $i++) {
    if (-not (Get-H)) { Log ("步骤 {0}: 进程已退出" -f $i); break }
    $title = Get-PageTitle
    Log ("步骤 {0}: 页面 = [{1}]" -f $i, $title)
    Shot ("{0}{1:D2}.png" -f $Prefix, $i)
    AcceptLicense
    if (-not (PostNext)) {
        Log '  （按钮暂不可用，等待安装结束）'
        Start-Sleep -Seconds 4
        continue
    }
    Start-Sleep -Milliseconds 1800
}

Get-Process $ProcName -ErrorAction SilentlyContinue | Stop-Process -Force
Log '完成。'
