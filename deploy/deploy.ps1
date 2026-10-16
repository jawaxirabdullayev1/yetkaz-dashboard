# YETKAZ prod deploy: GitHub main -> bot.py ishlayotgan papka.
# GitHub Actions (.github/workflows/deploy.yml, self-hosted runner "yetkaz-prod") har push'da chaqiradi.
# Qo'lda:  powershell -ExecutionPolicy Bypass -File "D:\Yetkaz dashboard\deploy\deploy.ps1" [-Restart]
#
#  - faqat fast-forward: papkada commit qilinmagan o'zgarish yoki GitHub'da yo'q commit bo'lsa
#    to'xtaydi va hech narsani o'zgartirmaydi;
#  - config_local.py, leads.db, rasmlar/, data/filiallar.json, python/ - .gitignore'da, tegilmaydi;
#  - faqat dashboard/, offer.txt, *.md, deploy/, .github/ o'zgarsa bot qayta ishga tushmaydi
#    (index.html va offer.txt har safar diskdan o'qiladi); boshqa o'zgarishda - qayta ishga tushadi;
#  - yangi versiya ishga tushmasa - oldingi commit'ga qaytariladi va bot eskisi bilan ishga tushadi.
param([switch]$Restart)   # -Restart: o'zgarish bo'lmasa ham botni qayta ishga tushirish

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Port = if ($env:YETKAZ_PORT) { [int]$env:YETKAZ_PORT } else { 8800 }
$TaskName = if ($env:YETKAZ_TASK) { $env:YETKAZ_TASK } else { "YETKAZ lid bot va dashboard" }
$NoRestart = '^(dashboard/|deploy/|\.github/)|^offer\.txt$|\.md$'

$Auth = @()
if ($env:GH_TOKEN) {   # workflow beradi: repo yopiq (private) bo'lsa ham fetch ishlaydi
    $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$env:GH_TOKEN"))
    $Auth = @("-c", "http.https://github.com/.extraheader=AUTHORIZATION: basic $b64")
}

function Invoke-Git {
    $ErrorActionPreference = "Continue"   # git progressni stderr'ga yozadi - PowerShell 5.1 buni xato deb olmasin
    $out = & git -C $Root @Auth @args 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw ("git " + ($args -join " ") + ":`n" + ($out -join "`n")) }
    $out
}

function Test-Port {
    $c = New-Object Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $Port); $true } catch { $false } finally { $c.Close() }
}

function Wait-Port([bool]$Open, [int]$Seconds) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if ((Test-Port) -eq $Open) { return $true }
        Start-Sleep -Seconds 1
    }
    (Test-Port) -eq $Open
}

function Test-Login {
    try { (Invoke-WebRequest "http://127.0.0.1:$Port/login" -UseBasicParsing -TimeoutSec 15).StatusCode -eq 200 } catch { $false }
}

function Get-BotTask { Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }

function Stop-Bot {
    if (Get-BotTask) { Stop-ScheduledTask -TaskName $TaskName }
    $pyDir = "$Root\python\"
    $ids = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -match 'bot\.py' -and
            ("$($_.ExecutablePath) $($_.CommandLine)").IndexOf($pyDir, [StringComparison]::OrdinalIgnoreCase) -ge 0 } |
        ForEach-Object { $_.ProcessId })
    # 8800-portni ushlab turgan python ham shu bot (bitta nusxa himoyasi)
    $ids += @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { $_.OwningProcess } |
        Where-Object { (Get-Process -Id $_ -ErrorAction SilentlyContinue).ProcessName -like "python*" })
    foreach ($id in ($ids | Sort-Object -Unique)) {
        Write-Host "Bot to'xtatilmoqda: PID $id"
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
    if (-not (Wait-Port $false 30)) { throw "$Port-port 30 soniyada bo'shamadi" }
}

function Start-Bot {
    if (Get-BotTask) {
        Start-ScheduledTask -TaskName $TaskName
    } else {
        Write-Host "Diqqat: '$TaskName' vazifasi topilmadi - bot oddiy jarayon sifatida ishga tushirilmoqda"
        $env:RUNNER_TRACKING_ID = ""   # runner job tugaganda botni o'chirib yubormasin
        Start-Process -FilePath (Join-Path $Root "python\pythonw.exe") -ArgumentList "bot.py" -WorkingDirectory $Root
    }
    if (-not (Wait-Port $true 90)) {
        $log = Join-Path $Root "logs\bot.log"
        $tail = if (Test-Path $log) { (Get-Content $log -Tail 20 -Encoding UTF8) -join "`n" } else { "(logs\bot.log yo'q)" }
        throw "Bot 90 soniyada ishga tushmadi ($Port-port yopiq). logs\bot.log oxiri:`n$tail"
    }
}

Write-Host "Papka: $Root"
if (-not (Test-Path (Join-Path $Root ".git"))) { throw "$Root - git papka emas" }
$branch = @(Invoke-Git rev-parse --abbrev-ref HEAD)[-1]
if ($branch -ne "main") { throw "Papka '$branch' branch'ida turibdi, main kerak" }
$dirty = @(Invoke-Git status --porcelain --untracked-files=no)
if ($dirty.Count) { throw ("Papkada commit qilinmagan o'zgarishlar bor - deploy to'xtadi, hech narsa o'zgarmadi:`n" + ($dirty -join "`n")) }

Invoke-Git fetch origin main | Out-Null
$old = @(Invoke-Git rev-parse HEAD)[-1]
$new = @(Invoke-Git rev-parse origin/main)[-1]
$changed = @()
if ($old -ne $new) {
    & git -C $Root merge-base --is-ancestor $old $new
    if ($LASTEXITCODE -ne 0) { throw "Papkada GitHub'da yo'q commit bor - deploy to'xtadi, hech narsa o'zgarmadi" }
    Invoke-Git merge --ff-only origin/main | Out-Null
    $changed = @(Invoke-Git diff --name-only $old $new)
    Write-Host ("Yangilandi: {0} -> {1}" -f $old.Substring(0, 7), $new.Substring(0, 7))
    $changed | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host ("Yangi o'zgarish yo'q ({0})" -f $new.Substring(0, 7))
}
$needRestart = $Restart -or (@($changed | Where-Object { $_ -notmatch $NoRestart }).Count -gt 0)

try {
    if ($changed -contains "requirements.txt") {
        Write-Host "requirements.txt o'zgardi - kutubxonalar o'rnatilmoqda"
        $ErrorActionPreference = "Continue"
        & (Join-Path $Root "python\python.exe") -m pip install -r (Join-Path $Root "requirements.txt")
        $code = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($code -ne 0) { throw "pip install xato bilan tugadi ($code)" }
    }
    if ($needRestart) { Stop-Bot; Start-Bot; Write-Host "Bot qayta ishga tushirildi" }
    elseif (-not (Test-Port)) { Write-Host "Bot ishlamayapti - ishga tushirilmoqda"; Start-Bot }
    else { Write-Host "Bot qayta ishga tushirilmadi: faqat diskdan o'qiladigan fayllar o'zgardi" }
    if (-not (Test-Login)) { throw "http://127.0.0.1:$Port/login javob bermadi" }
} catch {
    $err = $_
    if ($old -ne $new) {
        Write-Host "XATO: $err"
        Write-Host ("Oldingi versiyaga qaytarilmoqda: {0}" -f $old.Substring(0, 7))
        Invoke-Git reset --hard $old | Out-Null
        try { Stop-Bot; Start-Bot; Write-Host "Bot oldingi versiya bilan ishlayapti" }
        catch { Write-Host "Oldingi versiya ham ishga tushmadi: $_" }
    }
    throw $err
}
Write-Host ("OK: dashboard ishlayapti, versiya {0}" -f @(Invoke-Git rev-parse --short HEAD)[-1])
