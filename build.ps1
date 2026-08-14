$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Ambiente virtual não encontrado. Crie .venv e instale requirements-dev.txt."
}

& $PythonPath -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "KeyCiphra.spec")
if ($LASTEXITCODE -ne 0) {
    throw "A geração do KeyCiphra.exe falhou."
}

$Executable = Join-Path $ProjectRoot "dist\KeyCiphra.exe"
Write-Host "Executável criado em: $Executable"
