[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host 'Starting the complete NIRA v0.4 guided demo with a fresh temporary state directory.'
Write-Host 'The walkthrough uses real local handlers, synthetic session labels, no credentials, and no model claim.'
$stateDir = Join-Path $env:TEMP ("nira-full-demo-" + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python -m nira --full-demo --state-dir $stateDir

