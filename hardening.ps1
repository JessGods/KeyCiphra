$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RuffPath = Join-Path $ProjectRoot ".venv\Scripts\ruff.exe"
$BanditPath = Join-Path $ProjectRoot ".venv\Scripts\bandit.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Ambiente virtual não encontrado. Instale requirements-dev.txt."
}

& $RuffPath check app packaging tests run.py
if ($LASTEXITCODE -ne 0) { throw "Ruff encontrou problemas." }

& $BanditPath -r app packaging run.py -q
if ($LASTEXITCODE -ne 0) { throw "Bandit encontrou um possível problema de segurança." }

& $PythonPath -m pip_audit -r requirements.txt --progress-spinner off
if ($LASTEXITCODE -ne 0) { throw "pip-audit encontrou vulnerabilidades conhecidas." }

& $PythonPath -m pip_audit --local --progress-spinner off
if ($LASTEXITCODE -ne 0) { throw "O ambiente de desenvolvimento contém vulnerabilidades conhecidas." }

& $PythonPath -m pip check
if ($LASTEXITCODE -ne 0) { throw "O ambiente possui dependências incompatíveis." }

& $PythonPath -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "A suíte de testes falhou." }

Write-Host "Hardening concluído: lint, segurança, dependências e testes aprovados."
