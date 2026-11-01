# 把 AutoAIAnswer 推到 GitHub，并触发 macOS 打包
# 用法：双击同目录的 push-to-github.bat，或右键「使用 PowerShell 运行」
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $git)) {
    $git = "git"
}

function Fail($message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    Write-Host ""
    Read-Host "按回车退出"
    exit 1
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  AutoAIAnswer 上传助手" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "先在 GitHub 新建一个空仓库（不要勾 README），然后粘贴仓库地址。" -ForegroundColor Gray
Write-Host "例如：https://github.com/yourname/AutoAIAnswer.git" -ForegroundColor Gray
Write-Host ""

$url = Read-Host "仓库地址"
if ([string]::IsNullOrWhiteSpace($url)) {
    Fail "没有输入仓库地址。"
}
$url = $url.Trim()
if ($url -notmatch '^https://github\.com/[^/]+/[^/]+(\.git)?$') {
    Write-Host "地址看起来不太对，继续尝试：$url" -ForegroundColor Yellow
}
if ($url -notmatch '\.git$') {
    $url = "$url.git"
}

if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    Fail "当前目录不是 git 仓库：$repoRoot"
}

# 记录当前分支与标签
$branch = (& $git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) { $branch = "main" }
$tags = @(& $git tag -l)
if ($tags.Count -eq 0) {
    Fail "没有找到版本标签，先打标签（例如 git tag v0.2.63）。"
}
$tag = $tags[-1]

Write-Host ""
Write-Host ("准备推送分支 {0} 和标签 {1} → {2}" -f $branch, $tag, $url) -ForegroundColor Gray

# 远端
& $git remote remove origin 2>$null | Out-Null
& $git remote add origin $url
if ($LASTEXITCODE -ne 0) {
    Fail "无法设置远端仓库地址。"
}

function Invoke-GitPush([string[]]$arguments) {
    $output = & $git @arguments 2>&1 | Out-String
    Write-Host $output
    return @{ Code = $LASTEXITCODE; Output = $output }
}

function Use-SystemProxy {
    try {
        $settings = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction Stop
        if ($settings.ProxyEnable -eq 1 -and $settings.ProxyServer) {
            $proxy = "http://" + $settings.ProxyServer
            & $git config http.proxy $proxy | Out-Null
            Write-Host "已使用系统代理：$proxy" -ForegroundColor Yellow
            return $true
        }
    } catch {
    }
    return $false
}

Write-Host ""
Write-Host "== 推送 main ==" -ForegroundColor Cyan
Write-Host "如果弹出浏览器，请登录 GitHub 并点 Authorize / Sign in。" -ForegroundColor Yellow
$result = Invoke-GitPush @("push", "-u", "origin", $branch)

if ($result.Code -ne 0 -and $result.Output -match 'Could not resolve|Failed to connect|timed out|Connection refused') {
    Write-Host ""
    Write-Host "网络看起来不通，尝试系统代理后重试…" -ForegroundColor Yellow
    if (Use-SystemProxy) {
        $result = Invoke-GitPush @("push", "-u", "origin", $branch)
    }
}

if ($result.Code -ne 0) {
    Write-Host ""
    Fail "推送失败。常见原因：仓库地址写错、仓库不是空的、浏览器登录未完成、网络/代理问题。详见 docs/PUSH.md"
}

Write-Host ""
Write-Host "== 推送标签 $tag ==" -ForegroundColor Cyan
$tagResult = Invoke-GitPush @("push", "origin", $tag)
if ($tagResult.Code -ne 0) {
    Write-Host ""
    Fail "标签推送失败，但代码已经在 GitHub 上了。可以稍后手动执行：git push origin $tag"
}

Write-Host ""
Write-Host "完成。" -ForegroundColor Green
Write-Host "接下来：" -ForegroundColor Gray
Write-Host "  1. 打开仓库页面的 Actions，等 Build macOS app 跑完（8–15 分钟）。" -ForegroundColor Gray
Write-Host "  2. 到 Releases 下载 QQMusic-macOS-arm64.zip。" -ForegroundColor Gray
Write-Host "  3. 解压后右键 QQMusic.app → 打开，并在系统设置里允许屏幕录制与辅助功能。" -ForegroundColor Gray
Write-Host ""
Read-Host "按回车关闭"
