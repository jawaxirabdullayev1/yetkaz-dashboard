# Bir martalik: GitHub runner Windows'ga kirganda o'zi ishga tushadigan bo'lsin.
# Prod kompyuterida, bot ishlaydigan foydalanuvchi nomidan, ODDIY (administrator emas) PowerShell'da:
#   powershell -ExecutionPolicy Bypass -File "D:\Yetkaz dashboard\deploy\install-runner.ps1" -RunnerDir C:\actions-runner
# Qiladi: runner'ga prod papka yo'lini yozadi (.env), "YETKAZ GitHub runner" vazifasini yaratib ishga tushiradi,
# so'ng deploy.ps1 -Restart bilan to'liq tekshiradi (git, botni to'xtatish/ishga tushirish, /login).
param([Parameter(Mandatory = $true)][string]$RunnerDir)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TaskName = "YETKAZ GitHub runner"
$RunnerDir = (Resolve-Path $RunnerDir).Path
if (-not (Test-Path (Join-Path $RunnerDir "run.cmd"))) { throw "$RunnerDir\run.cmd yo'q - avval runner'ni yuklab oching" }
if (-not (Test-Path (Join-Path $RunnerDir ".runner"))) { throw "Runner sozlanmagan - avval config.cmd ni ishga tushiring" }

# 1. Runner job'lari prod papkani shu o'zgaruvchidan oladi (deploy.yml)
$envFile = Join-Path $RunnerDir ".env"
$lines = @(if (Test-Path $envFile) { Get-Content $envFile | Where-Object { $_ -notmatch '^YETKAZ_PROD_DIR=' } })
$lines += "YETKAZ_PROD_DIR=$Root"
[IO.File]::WriteAllLines($envFile, [string[]]$lines)   # UTF-8, BOM'siz

# 2. Windows'ga kirganda runner yashirin oynada ishga tushadi
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $RunnerDir `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"& '$RunnerDir\run.cmd'`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "OK: '$TaskName' vazifasi yaratildi va ishga tushdi (runner: $RunnerDir, prod: $Root)"

# 3. To'liq tekshiruv: shu foydalanuvchi botni to'xtatib-ishga tushira oladimi
& (Join-Path $PSScriptRoot "deploy.ps1") -Restart
