# =============================================================================
#  自动化验证：静默安装 -> 检查结果 -> 静默卸载 -> 检查是否卸干净
#  默认验证「由设计器生成」的免提权安装包。
#  用法：  powershell -ExecutionPolicy Bypass -File .\verify.ps1
#          powershell -ExecutionPolicy Bypass -File .\verify.ps1 -Setup <安装包路径>
# =============================================================================
param(
    [string]$Setup = (Join-Path $PSScriptRoot 'out\我的小工具-1.0.0-Setup-PerUser.exe')
)

$ErrorActionPreference = 'Stop'

$Root    = $PSScriptRoot
$TestDir = Join-Path $env:TEMP 'aipack-demo-test'

if (-not (Test-Path $Setup)) { throw "找不到 $Setup，请先运行 build.ps1" }

$fail = 0
function Check([string]$Name, [bool]$Ok, [string]$Detail = '') {
    if ($Ok) {
        Write-Host ("  [通过] {0} {1}" -f $Name, $Detail) -ForegroundColor Green
    } else {
        Write-Host ("  [失败] {0} {1}" -f $Name, $Detail) -ForegroundColor Red
        $script:fail++
    }
}

# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '=== 1. 静默安装到临时目录' -ForegroundColor Cyan
if (Test-Path $TestDir) { Remove-Item $TestDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $TestDir | Out-Null

# NSIS 静默安装：/S ；/D= 必须放在最后，且不能加引号
& $Setup /S "/D=$TestDir" | Out-Null
Start-Sleep -Seconds 3

Check '主程序已释放'   (Test-Path (Join-Path $TestDir 'MyApp.exe'))
Check '说明文件已释放' (Test-Path (Join-Path $TestDir '使用说明.txt'))
Check '卸载程序已生成' (Test-Path (Join-Path $TestDir 'Uninstall.exe'))

$desktopLnk = Join-Path ([Environment]::GetFolderPath('Desktop')) '我的小工具.lnk'
$startLnk   = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\我的小工具\我的小工具.lnk'
Check '桌面快捷方式'   (Test-Path $desktopLnk)
Check '开始菜单快捷方式' (Test-Path $startLnk)

$reg = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MyApp'
Check '卸载注册表项'   (Test-Path $reg)
if (Test-Path $reg) {
    $p = Get-ItemProperty $reg
    Check '  卸载项-显示名称' ($p.DisplayName -eq '我的小工具') "-> $($p.DisplayName)"
    Check '  卸载项-发行者'   ($p.Publisher -eq '示例软件工作室') "-> $($p.Publisher)"
    Check '  卸载项-版本'     ($p.DisplayVersion -eq '1.0.0') "-> $($p.DisplayVersion)"
}

# 运行一次示例程序，让它生成用户配置文件
Write-Host '  （启动示例程序，生成用户配置数据...）'
Start-Process (Join-Path $TestDir 'MyApp.exe') | Out-Null
Start-Sleep -Seconds 4
Get-Process MyApp -ErrorAction SilentlyContinue | Stop-Process -Force
$userData = Join-Path $env:APPDATA '我的小工具'
Check '用户数据已生成' (Test-Path $userData) "-> $userData"

# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '=== 2. 静默卸载（保留用户数据）' -ForegroundColor Cyan
& (Join-Path $TestDir 'Uninstall.exe') /S | Out-Null
Start-Sleep -Seconds 4

Check '安装目录已删除'     (-not (Test-Path $TestDir))
Check '桌面快捷方式已删除' (-not (Test-Path $desktopLnk))
Check '开始菜单已删除'     (-not (Test-Path $startLnk))
Check '注册表项已删除'     (-not (Test-Path $reg))
Check '用户数据按预期保留' (Test-Path $userData)

# 清理现场
if (Test-Path $TestDir) { Remove-Item $TestDir -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $userData) { Remove-Item $userData -Recurse -Force -ErrorAction SilentlyContinue }

# ---------------------------------------------------------------------------
Write-Host ''
if ($fail -eq 0) {
    Write-Host '全部检查通过：安装 / 快捷方式 / 注册表 / 卸载 链路正常。' -ForegroundColor Green
} else {
    Write-Host ("有 {0} 项检查未通过，请查看上面的红色输出。" -f $fail) -ForegroundColor Red
    exit 1
}
