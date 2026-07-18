param(
    [string]$PythonPath = ".\.venv\Scripts\python.exe",
    [string]$StateDir = "$env:TEMP\nira-ui-audit",
    [string]$OutputDir = ".\docs\design\verification"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NiraWindowCapture {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr handle, out RECT rect);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindow(string className, string windowName);
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr handle, IntPtr deviceContext, uint flags);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr handle, int command);
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr handle, IntPtr insertAfter, int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll")]
    public static extern bool RedrawWindow(IntPtr handle, IntPtr updateRect, IntPtr updateRegion, uint flags);
}
"@
[NiraWindowCapture]::SetProcessDPIAware() | Out-Null

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = (Resolve-Path (Join-Path $repositoryRoot $PythonPath)).Path
$output = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $OutputDir))
[System.IO.Directory]::CreateDirectory($output) | Out-Null
[System.IO.Directory]::CreateDirectory($StateDir) | Out-Null

function Save-WindowScreenshot {
    param([IntPtr]$Handle, [string]$Path)
    $rect = New-Object NiraWindowCapture+RECT
    if (-not [NiraWindowCapture]::GetWindowRect($Handle, [ref]$rect)) {
        throw "Could not read the NIRA window bounds."
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.Clear([System.Drawing.Color]::Black)
        $deviceContext = $graphics.GetHdc()
        try {
            if (-not [NiraWindowCapture]::PrintWindow($Handle, $deviceContext, 2)) {
                throw "Windows could not render the requested NIRA window."
            }
        }
        finally {
            $graphics.ReleaseHdc($deviceContext)
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Save-ScreenScreenshot {
    param([IntPtr]$Handle, [string]$Path)
    $rect = New-Object NiraWindowCapture+RECT
    if (-not [NiraWindowCapture]::GetWindowRect($Handle, [ref]$rect)) {
        throw "Could not read the NIRA window bounds."
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        [NiraWindowCapture]::RedrawWindow($Handle, [IntPtr]::Zero, [IntPtr]::Zero, 0x0585) | Out-Null
        Start-Sleep -Milliseconds 150
        $graphics.Clear([System.Drawing.Color]::Black)
        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Show-CaptureWindow {
    param([IntPtr]$Handle)
    $topmost = [IntPtr](-1)
    $noMoveNoSizeShow = 0x0001 -bor 0x0002 -bor 0x0040
    [NiraWindowCapture]::ShowWindow($Handle, 9) | Out-Null
    [NiraWindowCapture]::SetWindowPos($Handle, $topmost, 0, 0, 0, 0, $noMoveNoSizeShow) | Out-Null
    Start-Sleep -Milliseconds 300
}

$existingWindowIds = @(
    Get-Process |
        Where-Object { $_.MainWindowTitle -eq "Nira Desktop Assistant" } |
        ForEach-Object { $_.Id }
)
$windowProcess = $null
$process = Start-Process -FilePath $python -ArgumentList @("-m", "nira", "--ui-audit-demo", "--state-dir", $StateDir) -WorkingDirectory $repositoryRoot -PassThru
try {
    $deadline = (Get-Date).AddSeconds(25)
    do {
        Start-Sleep -Milliseconds 250
        $process.Refresh()
        $windowProcess = Get-Process |
            Where-Object {
                $_.MainWindowTitle -eq "Nira Desktop Assistant" -and
                $_.Id -notin $existingWindowIds
            } |
            Sort-Object StartTime -Descending |
            Select-Object -First 1
        $windowHandle = if ($null -ne $windowProcess) { $windowProcess.MainWindowHandle } else { [IntPtr]::Zero }
    } while ($windowHandle -eq 0 -and -not $process.HasExited -and (Get-Date) -lt $deadline)

    if ($process.HasExited -or $windowHandle -eq 0) {
        throw "NIRA did not open a capturable desktop window."
    }

    Show-CaptureWindow $windowHandle
    Start-Sleep -Milliseconds 450
    Save-ScreenScreenshot $windowHandle (Join-Path $output "01-empty-chat.png")

    Start-Sleep -Seconds 4
    Show-CaptureWindow $windowHandle
    Save-ScreenScreenshot $windowHandle (Join-Path $output "02-offline-response.png")

    $permissionHandleFile = Join-Path $StateDir "ui-audit-permission-window.txt"
    $permissionDeadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 250
    } while (-not (Test-Path -LiteralPath $permissionHandleFile) -and (Get-Date) -lt $permissionDeadline)
    if (-not (Test-Path -LiteralPath $permissionHandleFile)) {
        Save-WindowScreenshot $windowHandle (Join-Path $output "03-permission-dialog-missing.png")
        throw "NIRA did not open the expected permission request dialog."
    }
    $permissionHandle = [IntPtr]([int64](Get-Content -Raw -LiteralPath $permissionHandleFile))
    Save-WindowScreenshot $permissionHandle (Join-Path $output "03-permission-request.png")
    Start-Sleep -Seconds 7
    Show-CaptureWindow $windowHandle
    Save-ScreenScreenshot $windowHandle (Join-Path $output "04-permission-denied.png")

    $conversationHandleFile = Join-Path $StateDir "ui-audit-conversations-window.txt"
    $conversationDeadline = (Get-Date).AddSeconds(8)
    do {
        Start-Sleep -Milliseconds 250
    } while (-not (Test-Path -LiteralPath $conversationHandleFile) -and (Get-Date) -lt $conversationDeadline)
    if (-not (Test-Path -LiteralPath $conversationHandleFile)) {
        throw "NIRA did not open the expected conversation manager."
    }
    $conversationHandle = [IntPtr]([int64](Get-Content -Raw -LiteralPath $conversationHandleFile))
    Save-WindowScreenshot $conversationHandle (Join-Path $output "05-conversation-manager.png")
}
finally {
    if ($null -ne $windowProcess -and -not $windowProcess.HasExited) {
        try {
            $windowProcess.CloseMainWindow() | Out-Null
            if (-not $windowProcess.WaitForExit(3000)) {
                $windowProcess.Kill()
            }
        }
        catch [System.InvalidOperationException] {
            # The window can close between the HasExited check and the close request.
        }
    }
    if (-not $process.HasExited) {
        try {
            $process.CloseMainWindow() | Out-Null
            if (-not $process.WaitForExit(3000)) {
                $process.Kill()
            }
        }
        catch [System.InvalidOperationException] {
            # The launcher can exit when the Tk child closes.
        }
    }
}

Write-Output $output
