param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function Find-SignTool {
    $command = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $kitsRoot = "C:\Program Files (x86)\Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitsRoot) {
        $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter "signtool.exe" -File -Recurse |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($null -ne $candidate) {
            return $candidate.FullName
        }
    }
    throw "SignTool não encontrado. Instale o Windows SDK antes de assinar uma versão."
}

$SignTool = Find-SignTool
$CertificatePath = $env:KEYCIPHRA_SIGN_CERTIFICATE_PATH
$CertificatePassword = $env:KEYCIPHRA_SIGN_CERTIFICATE_PASSWORD
$CertificateThumbprint = $env:KEYCIPHRA_SIGN_CERTIFICATE_THUMBPRINT

if ([string]::IsNullOrWhiteSpace($CertificatePath) -and [string]::IsNullOrWhiteSpace($CertificateThumbprint)) {
    throw "Defina KEYCIPHRA_SIGN_CERTIFICATE_PATH ou KEYCIPHRA_SIGN_CERTIFICATE_THUMBPRINT."
}

foreach ($artifact in $Path) {
    $ResolvedArtifact = (Resolve-Path -LiteralPath $artifact).Path
    $arguments = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")
    if (-not [string]::IsNullOrWhiteSpace($CertificatePath)) {
        $ResolvedCertificate = (Resolve-Path -LiteralPath $CertificatePath).Path
        $arguments += @("/f", $ResolvedCertificate)
        if (-not [string]::IsNullOrWhiteSpace($CertificatePassword)) {
            $arguments += @("/p", $CertificatePassword)
        }
    } else {
        $arguments += @("/sha1", $CertificateThumbprint)
    }
    $arguments += $ResolvedArtifact
    & $SignTool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao assinar $ResolvedArtifact."
    }
    & $SignTool verify /pa /all $ResolvedArtifact
    if ($LASTEXITCODE -ne 0) {
        throw "A assinatura de $ResolvedArtifact não passou na verificação Authenticode."
    }
}
