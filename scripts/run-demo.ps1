[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host 'Starting NIRA Local AI Assistant in local demo mode.'
Write-Host 'Review environment placeholders and use synthetic data before continuing.'
.\.venv\Scripts\python -m nira

