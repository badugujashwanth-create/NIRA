[CmdletBinding()]
param(
    [string]$ReleaseTag = "latest",
    [string]$DestinationRoot = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[llama.cpp-download] $Message"
}

try {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
        $DestinationRoot = Join-Path $repoRoot "runtime"
    }

    if (Test-Path $DestinationRoot) {
        if (-not $Force) {
            throw "Destination already exists: $DestinationRoot. Use -Force to overwrite."
        }
        Write-Info "Removing existing destination: $DestinationRoot"
        Remove-Item -Recurse -Force $DestinationRoot
    }

    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null

    $apiUrls = if ($ReleaseTag -eq "latest") {
        @(
            "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest",
            "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
        )
    } else {
        @(
            "https://api.github.com/repos/ggerganov/llama.cpp/releases/tags/$ReleaseTag",
            "https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/$ReleaseTag"
        )
    }

    $release = $null
    foreach ($apiUrl in $apiUrls) {
        try {
            Write-Info "Fetching release metadata from: $apiUrl"
            $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "Accept" = "application/vnd.github+json" }
            if ($release -and $release.assets) {
                break
            }
        }
        catch {
            Write-Info "Metadata fetch failed for $apiUrl : $($_.Exception.Message)"
        }
    }
    if (-not $release -or -not $release.assets) {
        throw "Could not read release metadata or assets list."
    }

    $asset = $release.assets | Where-Object { $_.name -match '^llama-b\d+-bin-win-cpu-x64\.zip$' } | Select-Object -First 1
    if (-not $asset) {
        # Fallback for potential future naming changes.
        $asset = $release.assets | Where-Object { $_.name -match 'win.*cpu.*x64.*\.zip$' } | Select-Object -First 1
    }
    if (-not $asset) {
        $names = ($release.assets | Select-Object -ExpandProperty name) -join ", "
        throw "No Windows CPU x64 zip asset found in release '$($release.tag_name)'. Assets: $names"
    }

    $zipPath = Join-Path $env:TEMP $asset.name
    Write-Info "Downloading asset: $($asset.name)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath
    if (-not (Test-Path $zipPath)) {
        throw "Download failed. Zip file not found at: $zipPath"
    }
    if ((Get-Item $zipPath).Length -le 0) {
        throw "Download failed. Zip file is empty: $zipPath"
    }

    Write-Info "Extracting to: $DestinationRoot"
    Expand-Archive -Path $zipPath -DestinationPath $DestinationRoot -Force

    $serverExe = Get-ChildItem -Path $DestinationRoot -Recurse -File |
        Where-Object { $_.Name -eq "llama-server.exe" } |
        Select-Object -First 1

    if (-not $serverExe) {
        throw "Extraction completed but llama-server.exe was not found under $DestinationRoot."
    }

    $cliExe = Get-ChildItem -Path $DestinationRoot -Recurse -File |
        Where-Object { $_.Name -eq "llama-cli.exe" } |
        Select-Object -First 1

    if (-not $cliExe) {
        throw "Extraction completed but llama-cli.exe was not found under $DestinationRoot."
    }

    # Ensure key executables are available directly under runtime\ for simpler command usage.
    $runtimeServer = Join-Path $DestinationRoot "llama-server.exe"
    $runtimeCli = Join-Path $DestinationRoot "llama-cli.exe"
    Copy-Item -Path $serverExe.FullName -Destination $runtimeServer -Force
    Copy-Item -Path $cliExe.FullName -Destination $runtimeCli -Force

    Write-Info "Done."
    Write-Info "Release: $($release.tag_name)"
    Write-Info "Server binary: $runtimeServer"
    Write-Info "CLI binary: $runtimeCli"
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
