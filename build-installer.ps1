param(
    [switch]$SkipExecutableBuild,
    [switch]$Sign
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VersionSource = Get-Content -LiteralPath (Join-Path $ProjectRoot "app\version.py") -Raw
if ($VersionSource -notmatch 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
    throw "Não foi possível ler APP_VERSION de app\version.py."
}
$Version = $Matches[1]
$Executable = Join-Path $ProjectRoot "dist\KeyCiphra.exe"
$Installer = Join-Path $ProjectRoot "dist\KeyCiphra-Setup-$Version.exe"
$InstallerScript = Join-Path $ProjectRoot "installer\KeyCiphra.iss"

function Find-InnoCompiler {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "Inno Setup não encontrado. Instale com: winget install --id JRSoftware.InnoSetup -e --source winget"
}

if (-not $SkipExecutableBuild) {
    & (Join-Path $ProjectRoot "build.ps1")
}
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Executável não encontrado em $Executable. Execute build.ps1 primeiro."
}

if ($Sign) {
    & (Join-Path $ProjectRoot "sign-artifacts.ps1") -Path $Executable
}

$Compiler = Find-InnoCompiler
& $Compiler "/DMyAppVersion=$Version" $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "A geração do instalador falhou."
}
if (-not (Test-Path -LiteralPath $Installer)) {
    throw "O instalador esperado não foi criado em $Installer."
}

if ($Sign) {
    & (Join-Path $ProjectRoot "sign-artifacts.ps1") -Path $Installer
}

$Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
$HashFile = "$Installer.sha256"
Set-Content -LiteralPath $HashFile -Value "$Hash  KeyCiphra-Setup-$Version.exe" -Encoding ascii
Write-Host "Instalador criado em: $Installer"
Write-Host "SHA-256: $Hash"
