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
$CertificateThumbprint = $env:KEYCIPHRA_SIGN_CERTIFICATE_THUMBPRINT

if ([string]::IsNullOrWhiteSpace($CertificateThumbprint)) {
    throw "Instale o certificado no Windows e defina KEYCIPHRA_SIGN_CERTIFICATE_THUMBPRINT."
}

foreach ($artifact in $Path) {
    $ResolvedArtifact = (Resolve-Path -LiteralPath $artifact).Path
    $arguments = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")
    # O certificado instalado evita expor senha de PFX na linha de comando do processo.
    $arguments += @("/sha1", $CertificateThumbprint)
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
