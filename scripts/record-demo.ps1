[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host 'No terminal recorder is bundled with this repository.'
Write-Host 'Follow docs/demo/DEMO_SCRIPT.md with a 720p or 1080p terminal recorder.'
Write-Host 'Do not record environment values, tokens, private URLs, or personal paths.'
exit 2

