# =============================================================================
#  「应用安装向导打包软件」 —— 可行性验证 demo 构建脚本
#  用法：  powershell -ExecutionPolicy Bypass -File .\build.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'

# 让控制台正确显示中文（否则 makensis 的输出会是乱码）
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
& chcp.com 65001 | Out-Null

$Root   = $PSScriptRoot
$SrcDir = Join-Path $Root 'src'
$InDir  = Join-Path $Root 'input'
$OutDir = Join-Path $Root 'out'

function Step([string]$Message) {
    Write-Host ''
    Write-Host "=== $Message" -ForegroundColor Cyan
}

function Ensure-Utf8Bom([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        return
    }
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    [System.IO.File]::WriteAllText($Path, $text, (New-Object System.Text.UTF8Encoding $true))
    Write-Host ("  加 UTF-8 BOM: {0}" -f (Split-Path $Path -Leaf))
}

# ---------------------------------------------------------------------------
# 1. 定位 NSIS 编译器
# ---------------------------------------------------------------------------
Step '定位 makensis.exe'
$Makensis = $null
$candidates = @(
    'C:\Program Files (x86)\NSIS\makensis.exe',
    'C:\Program Files\NSIS\makensis.exe',
    (Join-Path $Root 'vendor\nsis\makensis.exe')
)
foreach ($p in $candidates) {
    if (Test-Path $p) { $Makensis = $p; break }
}
if (-not $Makensis) {
    $cmd = Get-Command makensis.exe -ErrorAction SilentlyContinue
    if ($cmd) { $Makensis = $cmd.Source }
}
if (-not $Makensis) {
    throw '没有找到 makensis.exe。请先安装 NSIS：winget install NSIS.NSIS'
}
Write-Host ("  使用编译器: {0}" -f $Makensis)

# ---------------------------------------------------------------------------
# 2. 生成图形资源（图标、欢迎页位图、页头位图）
# ---------------------------------------------------------------------------
Step '生成图形资源'
& python (Join-Path $SrcDir 'make_assets.py')
if ($LASTEXITCODE -ne 0) { throw '图形资源生成失败。' }

# ---------------------------------------------------------------------------
# 3. 编译示例程序（用系统自带的 csc.exe，模拟"用户要打包的软件"）
# ---------------------------------------------------------------------------
Step '编译示例程序 MyApp.exe'
New-Item -ItemType Directory -Force -Path $InDir | Out-Null

$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path $csc)) { throw '没有找到 csc.exe，无法编译示例程序。' }

$exeOut  = Join-Path $InDir 'MyApp.exe'
$icoPath = Join-Path $Root 'assets\app.ico'
$cscBase = @(
    '/nologo', '/target:winexe', '/optimize+', '/codepage:65001',
    ('/out:' + $exeOut),
    '/r:System.dll', '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll',
    (Join-Path $SrcDir 'MyApp.cs')
)

& $csc @cscBase ("/win32icon:" + $icoPath) | Write-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host '  带图标编译失败，改为不带图标重试...' -ForegroundColor Yellow
    & $csc @cscBase | Write-Host
    if ($LASTEXITCODE -ne 0) { throw '示例程序编译失败。' }
}
Write-Host ("  已生成: {0}" -f $exeOut)

# ---------------------------------------------------------------------------
# 4. 准备要打包的内容（input 目录 = 用户在 GUI 里选中的文件）
# ---------------------------------------------------------------------------
Step '准备打包内容'
foreach ($f in @('许可协议.txt', '使用说明.txt')) {
    Copy-Item (Join-Path $SrcDir $f) $InDir -Force
}
# 许可协议页由 MUI 读取，需要 UTF-8 BOM 才能正确显示中文
Get-ChildItem -Path $InDir -Filter '*.txt' | ForEach-Object { Ensure-Utf8Bom $_.FullName }

# 更新日志是运行期由自定义页面用 FileRead 读取的。
# NSIS 的 FileRead 不识别 UTF-8，必须存成 UTF-16LE（带 BOM）。
$changelog = [System.IO.File]::ReadAllText((Join-Path $SrcDir '更新日志.txt'), [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText(
    (Join-Path $InDir '更新日志.txt'),
    $changelog,
    (New-Object System.Text.UnicodeEncoding($false, $true)))
Write-Host '  更新日志.txt -> UTF-16LE (含 BOM)'

Get-ChildItem -Path $InDir | Select-Object Name, Length | Format-Table -AutoSize | Out-String | Write-Host

# ---------------------------------------------------------------------------
# 5. 编译安装包（两种安装模式各出一个）
# ---------------------------------------------------------------------------
Step '编译安装程序'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$nsi = Join-Path $Root 'demo.nsi'
Ensure-Utf8Bom $nsi

$targets = @(
    @{ Defines = @();                       File = 'DemoSetup-PerMachine.exe'; Mode = '为所有用户安装（需管理员权限）' },
    @{ Defines = @('/DPER_USER');           File = 'DemoSetup-PerUser.exe';    Mode = '仅当前用户安装（免提权）' }
)

foreach ($t in $targets) {
    $args = @($t.Defines) + @('/DOUTFILE_NAME=' + $t.File) + @($nsi)
    & $Makensis @args | Write-Host
    if ($LASTEXITCODE -ne 0) { throw ("编译失败: {0}" -f $t.File) }
}

# ---------------------------------------------------------------------------
# 6. 结果汇总
# ---------------------------------------------------------------------------
Step '构建结果'
Get-ChildItem $OutDir -Filter *.exe | ForEach-Object {
    $v = $_.VersionInfo
    [PSCustomObject]@{
        文件名     = $_.Name
        大小       = ("{0:N0} KB" -f ($_.Length / 1KB))
        产品名称   = $v.ProductName
        公司       = $v.CompanyName
        版本       = $v.ProductVersion
        版权       = $v.LegalCopyright
    }
} | Format-List | Out-String | Write-Host

Write-Host '完成。请到 out 目录双击 DemoSetup-PerMachine.exe 试装。' -ForegroundColor Green
