# Genera los dos ejecutables de un release en dist\release-<versión>-<fecha>\
#
#   CFL-Launcher-real.exe  -> launcher completo (PyInstaller, main.spec)
#   CFL-Launcher.exe       -> "puente" liviano (tools\UpdateBridge.cs): los
#                             launchers viejos lo descargan, y él baja
#                             CFL-Launcher-real.exe del release <versión>.
#
# Uso (desde la raíz del proyecto):
#   powershell -ExecutionPolicy Bypass -File tools\build_release.ps1
#   powershell -ExecutionPolicy Bypass -File tools\build_release.ps1 -SkipTests
#
# Después sube AMBOS archivos a un release de GitHub cuyo tag sea exactamente
# la versión (p. ej. 5.3.6, sin "v").
param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "No se encontró $py (crea el entorno .venv)" }

$pyVersion = (Select-String -Path "core\launcherUpdate.py" -Pattern '^LAUNCHER_VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$csVersion = (Select-String -Path "tools\UpdateBridge.cs" -Pattern 'const string Version = "([^"]+)"').Matches[0].Groups[1].Value
if ($pyVersion -ne $csVersion) {
    throw "Versiones distintas: launcherUpdate.py=$pyVersion, UpdateBridge.cs=$csVersion"
}
Write-Host "== Release $pyVersion ==" -ForegroundColor Cyan

if (-not $SkipTests) {
    Write-Host "-- Tests" -ForegroundColor Cyan
    & $py -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) { throw "Los tests fallaron; no se genera el release." }
}

$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "dist\release-$pyVersion-$stamp"
$tmpDist = Join-Path $root "build\release-$pyVersion-$stamp-dist"
$workDir = Join-Path $root "build\release-$pyVersion-$stamp-real"
New-Item -ItemType Directory -Force $outDir | Out-Null

Write-Host "-- PyInstaller (CFL-Launcher-real.exe)" -ForegroundColor Cyan
& $py -m PyInstaller main.spec --noconfirm --clean --distpath $tmpDist --workpath $workDir
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }
Copy-Item (Join-Path $tmpDist "CFL-Launcher.exe") (Join-Path $outDir "CFL-Launcher-real.exe") -Force

Write-Host "-- Puente C# (CFL-Launcher.exe)" -ForegroundColor Cyan
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe" }
& $csc /nologo /target:winexe /optimize+ /platform:anycpu `
    "/win32icon:assets\logo.ico" `
    /reference:System.Windows.Forms.dll `
    "/out:$(Join-Path $outDir 'CFL-Launcher.exe')" `
    tools\UpdateBridge.cs
if ($LASTEXITCODE -ne 0) { throw "csc falló" }

Write-Host "-- Prueba de arranque (--self-test)" -ForegroundColor Cyan
foreach ($exe in @("CFL-Launcher-real.exe", "CFL-Launcher.exe")) {
    $path = Join-Path $outDir $exe
    $p = Start-Process -FilePath $path -ArgumentList "--self-test" -PassThru -Wait -WindowStyle Hidden
    if ($p.ExitCode -ne 0) { throw "$exe no pasó --self-test (código $($p.ExitCode))" }
    $info = Get-Item $path
    $hash = (Get-FileHash $path -Algorithm SHA256).Hash
    Write-Host ("   OK  {0,-24} {1,8:N1} MB  SHA256 {2}" -f $exe, ($info.Length / 1MB), $hash)
}

Write-Host ""
Write-Host "Listo: $outDir" -ForegroundColor Green
Write-Host "Crea el release de GitHub con tag '$pyVersion' y sube los DOS archivos."
