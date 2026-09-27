param(
    [string]$PythonCommand = 'python',
    [string]$FfmpegSource = ''
)

$skillRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $skillRoot '.runtime'
$pythonTarget = Join-Path $runtimeRoot 'python'
$binTarget = Join-Path $runtimeRoot 'bin'
$ffmpegTarget = Join-Path $binTarget 'ffmpeg.exe'
$validatedPython = 'C:\Users\Administrator\Documents\Codex\2026-09-18\new-chat\work\face_tracking_deps'
$validatedFfmpeg = 'C:\Users\Administrator\Documents\Codex\2026-09-15\new-chat\work\ffmpeg_bin\ffmpeg.exe'

New-Item -ItemType Directory -Force -Path $pythonTarget, $binTarget | Out-Null

if (Test-Path -LiteralPath $validatedPython) {
    Copy-Item -Path (Join-Path $validatedPython '*') -Destination $pythonTarget -Recurse -Force
} else {
    & $PythonCommand -m pip install --target $pythonTarget 'mediapipe==1.0.1' 'opencv-python==5.0.0' 'numpy==2.5.3'
    if ($LASTEXITCODE -ne 0) {
        throw 'Python dependency installation failed.'
    }
}

if ($FfmpegSource) {
    $selectedFfmpeg = $FfmpegSource
} elseif (Test-Path -LiteralPath $validatedFfmpeg) {
    $selectedFfmpeg = $validatedFfmpeg
} else {
    $ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpegCommand) {
        $selectedFfmpeg = $ffmpegCommand.Source
    } else {
        throw 'FFmpeg was not found. Pass -FfmpegSource with the absolute path to ffmpeg.exe.'
    }
}

if (-not (Test-Path -LiteralPath $selectedFfmpeg)) {
    throw "FFmpeg source does not exist: $selectedFfmpeg"
}
Copy-Item -LiteralPath $selectedFfmpeg -Destination $ffmpegTarget -Force

Write-Output "Local runtime ready: $runtimeRoot"
