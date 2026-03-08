$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "[NIRA] Virtual environment not found. Run .\nira\scripts\install.ps1 first."
}

Write-Host "[NIRA] Starting dev app with $pythonExe"
Push-Location $repoRoot
try {
    & $pythonExe -m nira
} finally {
    Pop-Location
}

