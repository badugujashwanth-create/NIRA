$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "[NIRA] Virtual environment not found. Run .\nira\scripts\install.ps1 first."
}

Write-Host "[NIRA] Building PyInstaller executable..."
Push-Location $repoRoot
try {
    & $pythonExe -m PyInstaller `
        --name NIRA `
        --windowed `
        --noconfirm `
        --collect-all pyttsx3 `
        --hidden-import win32timezone `
        nira\main.py
    Write-Host "[NIRA] Build complete. See dist\NIRA\ or dist\NIRA.exe depending on PyInstaller mode."
} finally {
    Pop-Location
}

