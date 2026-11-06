# Portable zip ve kurulum dosyasını üretir -> release\
# Kullanım: powershell -ExecutionPolicy Bypass -File build.ps1 -Version 1.0.0
# Gerekenler: pip install -r requirements.txt pyinstaller ; kurulum dosyası için Inno Setup 6
param([string]$Version = "1.0.0")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$name = "LegendsRO Helper"
$app = "dist\$name"

# 1) exe (tek klasör; yönetici izni ister, konsol penceresi açmaz)
python -m PyInstaller --noconfirm --clean --windowed --onedir --uac-admin `
    --name $name --collect-data customtkinter `
    --distpath dist --workpath build --specpath build gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız" }

# 2) exe'nin yanına okunan/yazılan dosyalar
Copy-Item config.json, ses.mp3, README.md $app
Copy-Item templates "$app\templates" -Recurse -Force

# 3) portable zip
New-Item -ItemType Directory -Force release | Out-Null
$zip = "release\LegendsRO-Helper-$Version-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $app -DestinationPath $zip
Write-Host "Portable: $zip"

# 4) kurulum dosyası (Inno Setup varsa)
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DAppVersion=$Version" installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup başarısız" }
    Write-Host "Kurulum: release\LegendsRO-Helper-$Version-Setup.exe"
} else {
    Write-Warning "Inno Setup bulunamadı; kurulum dosyası atlandı."
}
