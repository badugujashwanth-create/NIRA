[CmdletBinding()]
param(
    [ValidateRange(180, 360)]
    [int]$DurationSeconds = 245,
    [string]$FfmpegPath = ""
)

$ErrorActionPreference = "Stop"
[void][System.Reflection.Assembly]::LoadWithPartialName("System.Drawing")
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = (Resolve-Path (Join-Path $repoRoot ".venv\Scripts\python.exe")).Path
$demoDir = Join-Path $repoRoot "docs\demo"
$verificationDir = Join-Path $demoDir "verification"
[System.IO.Directory]::CreateDirectory($verificationDir) | Out-Null

function Resolve-Ffmpeg {
    param([string]$RequestedPath)
    if ($RequestedPath) {
        return (Resolve-Path $RequestedPath).Path
    }
    if ($env:NIRA_FFMPEG) {
        return (Resolve-Path $env:NIRA_FFMPEG).Path
    }
    $installed = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($null -ne $installed) {
        return $installed.Source
    }
    if ($null -eq (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "FFmpeg is unavailable and GitHub CLI is required for the pinned temporary download."
    }
    $cache = Join-Path $env:TEMP "nira-ffmpeg-8.1.2"
    $executable = Get-ChildItem $cache -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $executable) {
        return $executable.FullName
    }
    [System.IO.Directory]::CreateDirectory($cache) | Out-Null
    $zip = Join-Path $cache "ffmpeg-8.1.2-essentials_build.zip"
    if (-not (Test-Path -LiteralPath $zip)) {
        gh release download 8.1.2 -R GyanD/codexffmpeg -p "ffmpeg-8.1.2-essentials_build.zip" -D $cache
        if ($LASTEXITCODE -ne 0) {
            throw "Pinned FFmpeg download failed."
        }
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $cache -Force
    $executable = Get-ChildItem $cache -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if ($null -eq $executable) {
        throw "The pinned FFmpeg archive did not contain ffmpeg.exe."
    }
    return $executable.FullName
}

function New-Narration {
    param([string]$OutputPath)
    try {
        Add-Type -AssemblyName System.Speech
        $paragraphs = (Get-Content -Raw -Encoding utf8 (Join-Path $demoDir "NARRATION.md")) -split "(?:\r?\n){2,}" |
            Where-Object { $_ -and $_ -notmatch '^#' } |
            ForEach-Object { ($_ -replace '[`*_#]', '').Trim() }
        $builder = New-Object System.Speech.Synthesis.PromptBuilder
        foreach ($paragraph in $paragraphs) {
            $builder.AppendText($paragraph)
            $builder.AppendBreak([TimeSpan]::FromSeconds(3))
        }
        $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
        try {
            $voice.Rate = -1
            $voice.Volume = 90
            $voice.SetOutputToWaveFile($OutputPath)
            $voice.Speak($builder)
        }
        finally {
            $voice.Dispose()
        }
        return Test-Path -LiteralPath $OutputPath
    }
    catch {
        Write-Warning "Narration could not be generated; the video will retain complete WebVTT captions. $($_.Exception.Message)"
        return $false
    }
}

Add-Type -ReferencedAssemblies "System.Drawing" -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class NiraDemoWindow {
    private delegate bool EnumWindowsCallback(IntPtr handle, IntPtr parameter);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr handle, out RECT rect);
    [DllImport("dwmapi.dll")]
    public static extern int DwmGetWindowAttribute(IntPtr handle, int attribute, out RECT rect, int size);
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr parameter);
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr handle, out uint processId);
    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr handle);
    [DllImport("user32.dll")]
    private static extern bool IsIconic(IntPtr handle);
    [DllImport("user32.dll")]
    private static extern bool PrintWindow(IntPtr handle, IntPtr deviceContext, uint flags);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr handle, int command);
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr handle, IntPtr insertAfter, int x, int y, int width, int height, uint flags);

    private static RECT PhysicalBounds(IntPtr handle) {
        RECT rect;
        int status = DwmGetWindowAttribute(handle, 9, out rect, Marshal.SizeOf(typeof(RECT)));
        if (status != 0) throw new InvalidOperationException("DWM bounds failed with status " + status + ".");
        return rect;
    }

    private static Bitmap RenderWindow(IntPtr handle, int width, int height) {
        Bitmap bitmap = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        using (Graphics graphics = Graphics.FromImage(bitmap)) {
            graphics.Clear(Color.FromArgb(8, 17, 27));
            IntPtr dc = graphics.GetHdc();
            try {
                if (!PrintWindow(handle, dc, 2)) throw new InvalidOperationException("PrintWindow failed.");
            }
            finally { graphics.ReleaseHdc(dc); }
        }
        return bitmap;
    }

    public static void CaptureProcessWindows(IntPtr mainHandle, uint processId, string path) {
        RECT main = PhysicalBounds(mainHandle);
        int width = main.Right - main.Left;
        int height = main.Bottom - main.Top;
        using (Bitmap canvas = RenderWindow(mainHandle, width, height)) {
            List<IntPtr> overlays = new List<IntPtr>();
            EnumWindows(delegate(IntPtr handle, IntPtr parameter) {
                uint owner;
                GetWindowThreadProcessId(handle, out owner);
                if (owner == processId && handle != mainHandle && IsWindowVisible(handle) && !IsIconic(handle)) {
                    overlays.Add(handle);
                }
                return true;
            }, IntPtr.Zero);
            overlays.Reverse();
            using (Graphics graphics = Graphics.FromImage(canvas)) {
                foreach (IntPtr handle in overlays) {
                    RECT rect = PhysicalBounds(handle);
                    int overlayWidth = rect.Right - rect.Left;
                    int overlayHeight = rect.Bottom - rect.Top;
                    if (overlayWidth <= 0 || overlayHeight <= 0) continue;
                    using (Bitmap overlay = RenderWindow(handle, overlayWidth, overlayHeight)) {
                        graphics.DrawImageUnscaled(overlay, rect.Left - main.Left, rect.Top - main.Top);
                    }
                }
            }
            canvas.Save(path, ImageFormat.Png);
        }
    }
}
"@

$ffmpeg = Resolve-Ffmpeg $FfmpegPath
$ffprobe = Join-Path (Split-Path -Parent $ffmpeg) "ffprobe.exe"
if (-not (Test-Path -LiteralPath $ffprobe)) {
    throw "ffprobe.exe was not found beside ffmpeg.exe."
}
& $ffmpeg -version | Select-Object -First 1

Push-Location $repoRoot
try {
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "pip check failed before recording." }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed before recording." }
}
finally {
    Pop-Location
}

$runId = [guid]::NewGuid().ToString("N")
$stateDir = Join-Path $env:TEMP "nira-video-state-$runId"
$workDir = Join-Path $env:TEMP "nira-video-work-$runId"
[System.IO.Directory]::CreateDirectory($stateDir) | Out-Null
[System.IO.Directory]::CreateDirectory($workDir) | Out-Null
$narrationPath = Join-Path $workDir "narration.wav"
$videoOnlyPath = Join-Path $workDir "nira-window.mp4"
$framesDir = Join-Path $workDir "frames"
[System.IO.Directory]::CreateDirectory($framesDir) | Out-Null
$narrationReady = New-Narration $narrationPath

$existingWindowIds = @(Get-Process | Where-Object { $_.MainWindowTitle -eq "Nira Desktop Assistant" } | ForEach-Object { $_.Id })
$launcher = Start-Process -FilePath $python -ArgumentList @("-m", "nira", "--full-demo", "--state-dir", $stateDir) -WorkingDirectory $repoRoot -PassThru
$windowProcess = $null
try {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $windowProcess = Get-Process |
            Where-Object { $_.MainWindowTitle -eq "Nira Desktop Assistant" -and $_.Id -notin $existingWindowIds } |
            Sort-Object StartTime -Descending |
            Select-Object -First 1
    } while ($null -eq $windowProcess -and (Get-Date) -lt $deadline)
    if ($null -eq $windowProcess) {
        throw "NIRA did not open a capturable desktop window."
    }

    $handle = $windowProcess.MainWindowHandle
    $rect = New-Object NiraDemoWindow+RECT
    # gdigrab records the physical desktop. GetWindowRect is DPI-virtualized in
    # this PowerShell host, so use DWM's physical extended-frame bounds instead.
    $dwmStatus = [NiraDemoWindow]::DwmGetWindowAttribute(
        $handle,
        9,
        [ref]$rect,
        [Runtime.InteropServices.Marshal]::SizeOf($rect)
    )
    if ($dwmStatus -ne 0) {
        throw "Could not read the physical NIRA window bounds (DWM status $dwmStatus)."
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -lt 900 -or $height -lt 600) {
        throw "Unexpected NIRA window size: ${width}x${height}."
    }
    [NiraDemoWindow]::ShowWindow($handle, 9) | Out-Null
    [NiraDemoWindow]::SetWindowPos($handle, [IntPtr](-1), 0, 0, 0, 0, 0x0043) | Out-Null
    Start-Sleep -Milliseconds 2500

    # Render NIRA directly instead of sampling the desktop. This remains private
    # and deterministic even if the operator changes apps or virtual desktops.
    $captureRate = 2
    $frameCount = $DurationSeconds * $captureRate
    $timer = [Diagnostics.Stopwatch]::StartNew()
    for ($index = 0; $index -lt $frameCount; $index++) {
        if ($windowProcess.HasExited) {
            throw "NIRA exited before recording completed."
        }
        $framePath = Join-Path $framesDir ("frame-{0:D6}.png" -f $index)
        [NiraDemoWindow]::CaptureProcessWindows($handle, [uint32]$windowProcess.Id, $framePath)
        $remaining = ((($index + 1) / $captureRate) * 1000) - $timer.ElapsedMilliseconds
        if ($remaining -gt 0) { Start-Sleep -Milliseconds ([int]$remaining) }
    }
    $captureFilter = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x08111b,fps=10"
    & $ffmpeg -hide_banner -loglevel warning -y -framerate $captureRate `
        -i (Join-Path $framesDir "frame-%06d.png") -vf $captureFilter -an `
        -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p $videoOnlyPath
    if ($LASTEXITCODE -ne 0) { throw "FFmpeg frame encoding failed." }
}
finally {
    if ($null -ne $windowProcess) {
        try {
            if (-not $windowProcess.HasExited) {
                $windowProcess.CloseMainWindow() | Out-Null
                $windowProcess.WaitForExit(3000) | Out-Null
            }
        }
        catch [System.InvalidOperationException] {}
    }
    try {
        if (-not $launcher.HasExited) { $launcher.Kill() }
    }
    catch {
        # The application window is already closed at this point. Some Windows
        # launch shims deny a redundant Kill call while they are tearing down.
    }
}

$outputVideo = Join-Path $demoDir "demo.webm"
if ($narrationReady) {
    $audioFilter = "[1:a]apad=pad_dur=$DurationSeconds[a]"
    & $ffmpeg -hide_banner -loglevel warning -y -i $videoOnlyPath -i $narrationPath `
        -filter_complex $audioFilter -map 0:v:0 -map "[a]" `
        -c:v libvpx-vp9 -crf 38 -b:v 0 -deadline good -cpu-used 5 `
        -c:a libopus -b:a 64k -t $DurationSeconds $outputVideo
}
else {
    & $ffmpeg -hide_banner -loglevel warning -y -i $videoOnlyPath `
        -c:v libvpx-vp9 -crf 38 -b:v 0 -deadline good -cpu-used 5 -an $outputVideo
}
if ($LASTEXITCODE -ne 0) {
    throw "FFmpeg final encoding failed."
}

& $ffmpeg -hide_banner -loglevel error -y -ss 00:02:22 -i $outputVideo -frames:v 1 (Join-Path $demoDir "demo-thumbnail.png")
$frameTimes = @("00:00:08", "00:00:32", "00:00:58", "00:01:28", "00:02:24", "00:03:14", "00:03:55")
for ($index = 0; $index -lt $frameTimes.Count; $index++) {
    $frameName = "{0:D2}-frame.png" -f ($index + 1)
    & $ffmpeg -hide_banner -loglevel error -y -ss $frameTimes[$index] -i $outputVideo -frames:v 1 (Join-Path $verificationDir $frameName)
}

$probeJson = (& $ffprobe -v error -show_entries "format=duration,size:stream=index,codec_type,codec_name,width,height" -of json $outputVideo) | Out-String
$probe = $probeJson | ConvertFrom-Json
$duration = [double]$probe.format.duration
$videoStream = $probe.streams | Where-Object { $_.codec_type -eq "video" } | Select-Object -First 1
$audioStream = $probe.streams | Where-Object { $_.codec_type -eq "audio" } | Select-Object -First 1
if ($duration -lt 180 -or $videoStream.width -ne 1280 -or $videoStream.height -ne 720) {
    throw "Demo acceptance failed: duration=$duration resolution=$($videoStream.width)x$($videoStream.height)."
}

$evidence = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    duration_seconds = [Math]::Round($duration, 3)
    width = $videoStream.width
    height = $videoStream.height
    video_codec = $videoStream.codec_name
    audio_codec = if ($null -ne $audioStream) { $audioStream.codec_name } else { $null }
    captions = "demo-captions.vtt"
    sha256 = (Get-FileHash -Algorithm SHA256 $outputVideo).Hash.ToLower()
    bytes = (Get-Item $outputVideo).Length
    verification_frames = $frameTimes.Count
}
[System.IO.File]::WriteAllText(
    (Join-Path $verificationDir "verification.json"),
    ($evidence | ConvertTo-Json -Depth 4) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output ($evidence | ConvertTo-Json -Depth 4)
