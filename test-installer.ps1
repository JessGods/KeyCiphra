param(
    [string]$Installer = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VersionSource = Get-Content -LiteralPath (Join-Path $ProjectRoot "app\version.py") -Raw
if ($VersionSource -notmatch 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
    throw "Não foi possível ler APP_VERSION de app\version.py."
}
$Version = $Matches[1]
if ([string]::IsNullOrWhiteSpace($Installer)) {
    $Installer = Join-Path $ProjectRoot "dist\KeyCiphra-Setup-$Version.exe"
}
$Installer = (Resolve-Path -LiteralPath $Installer).Path
$TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("KeyCiphraInstallerTest-" + [guid]::NewGuid())
$InstallDirectory = Join-Path $TestRoot "program"
$IsolatedLocalAppData = Join-Path $TestRoot "local-app-data"
$InstallerLog = Join-Path $TestRoot "install.log"
$Sentinel = Join-Path $IsolatedLocalAppData "KeyCiphra\preserve-on-uninstall.sentinel"

New-Item -ItemType Directory -Path $InstallDirectory, (Split-Path -Parent $Sentinel) -Force | Out-Null
Set-Content -LiteralPath $Sentinel -Value "Dados privados devem sobreviver à desinstalação." -Encoding utf8

try {
    $InstallProcess = Start-Process -FilePath $Installer -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/DIR=$InstallDirectory",
        "/LOG=$InstallerLog"
    ) -WindowStyle Hidden -Wait -PassThru
    if ($InstallProcess.ExitCode -ne 0) {
        throw "O instalador terminou com o código $($InstallProcess.ExitCode). Consulte $InstallerLog."
    }

    $InstalledExecutable = Join-Path $InstallDirectory "KeyCiphra.exe"
    $Uninstaller = Join-Path $InstallDirectory "unins000.exe"
    if (-not (Test-Path -LiteralPath $InstalledExecutable) -or -not (Test-Path -LiteralPath $Uninstaller)) {
        throw "A instalação não criou os arquivos esperados."
    }
    $ProductVersion = (Get-Item -LiteralPath $InstalledExecutable).VersionInfo.ProductVersion
    if ($ProductVersion -ne $Version) {
        throw "Versão instalada inesperada: $ProductVersion."
    }

    $PreviousLocalAppData = $env:LOCALAPPDATA
    try {
        $env:LOCALAPPDATA = $IsolatedLocalAppData
        $SmokeProcess = Start-Process -FilePath $InstalledExecutable -ArgumentList "--smoke-test" -WindowStyle Hidden -Wait -PassThru
        if ($SmokeProcess.ExitCode -ne 0) {
            throw "O executável instalado falhou no smoke test com o código $($SmokeProcess.ExitCode)."
        }
    } finally {
        $env:LOCALAPPDATA = $PreviousLocalAppData
    }

    $UninstallProcess = Start-Process -FilePath $Uninstaller -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART"
    ) -WindowStyle Hidden -Wait -PassThru
    if ($UninstallProcess.ExitCode -ne 0) {
        throw "O desinstalador terminou com o código $($UninstallProcess.ExitCode)."
    }
    if (Test-Path -LiteralPath $InstalledExecutable) {
        throw "O executável continuou presente após a desinstalação."
    }
    if (-not (Test-Path -LiteralPath $Sentinel)) {
        throw "A desinstalação removeu indevidamente a área privada do usuário."
    }

    Write-Host "Instalação, smoke test e desinstalação concluídos com sucesso."
    Write-Host "Dados privados preservados após a desinstalação."
} finally {
    $ResolvedTestRoot = [System.IO.Path]::GetFullPath($TestRoot)
    $ResolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($ResolvedTestRoot.StartsWith($ResolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $ResolvedTestRoot).StartsWith("KeyCiphraInstallerTest-")) {
        Remove-Item -LiteralPath $ResolvedTestRoot -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning "A pasta temporária não foi removida porque seu caminho não passou na validação: $ResolvedTestRoot"
    }
}
