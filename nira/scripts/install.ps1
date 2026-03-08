$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$venvPath = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

Write-Host "[NIRA] Repo root: $repoRoot"

if (-not (Test-Path $venvPath)) {
    Write-Host "[NIRA] Creating virtual environment at $venvPath"
    python -m venv $venvPath
} else {
    Write-Host "[NIRA] Reusing existing virtual environment."
}

Write-Host "[NIRA] Upgrading pip/setuptools/wheel..."
& $pythonExe -m pip install --upgrade pip setuptools wheel

$requirementsPath = Join-Path $repoRoot "nira\requirements.txt"
Write-Host "[NIRA] Installing dependencies from $requirementsPath"
& $pythonExe -m pip install -r $requirementsPath

Write-Host "[NIRA] Install complete."

