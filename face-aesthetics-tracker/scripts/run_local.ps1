param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('upper-eyelid-space', 'nasolabial-region', 'nasal-base-support', 'frontal-symmetry-bone')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$InputVideo,

    [Parameter(Mandatory = $true)]
    [string]$OutputVideo
)

$skillRoot = Split-Path -Parent $PSScriptRoot
$modelPath = Join-Path $skillRoot 'assets\models\face_landmarker.task'
$runtimePython = Join-Path $skillRoot '.runtime\python'
$runtimeFfmpeg = Join-Path $skillRoot '.runtime\bin\ffmpeg.exe'
$validatedPython = 'C:\Users\Administrator\Documents\Codex\2026-09-18\new-chat\work\face_tracking_deps'
$validatedFfmpeg = 'C:\Users\Administrator\Documents\Codex\2026-09-15\new-chat\work\ffmpeg_bin\ffmpeg.exe'

$renderers = @{
    'upper-eyelid-space' = 'render_upper_eyelid_tracking.py'
    'nasolabial-region' = 'render_nasolabial_tracking.py'
    'nasal-base-support' = 'render_nasal_base_support.py'
    'frontal-symmetry-bone' = 'render_frontal_symmetry_bone.py'
}

if (-not (Test-Path -LiteralPath $InputVideo)) {
    throw "Input video does not exist: $InputVideo"
}
if (-not (Test-Path -LiteralPath $modelPath)) {
    throw "Face landmark model is missing: $modelPath"
}

if (Test-Path -LiteralPath $runtimePython) {
    $pythonPackages = $runtimePython
} elseif (Test-Path -LiteralPath $validatedPython) {
    $pythonPackages = $validatedPython
} else {
    throw 'Local Python packages are missing. Run scripts\setup_local.ps1 first.'
}

if (Test-Path -LiteralPath $runtimeFfmpeg) {
    $ffmpegPath = $runtimeFfmpeg
} else {
    $ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpegCommand) {
        $ffmpegPath = $ffmpegCommand.Source
    } elseif (Test-Path -LiteralPath $validatedFfmpeg) {
        $ffmpegPath = $validatedFfmpeg
    } else {
        throw 'FFmpeg is missing. Run scripts\setup_local.ps1 with -FfmpegSource.'
    }
}

$outputParent = Split-Path -Parent $OutputVideo
if ($outputParent -and -not (Test-Path -LiteralPath $outputParent)) {
    New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
}

$renderer = Join-Path $PSScriptRoot $renderers[$Mode]
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pythonPackages
    python $renderer --input $InputVideo --output $OutputVideo --model $modelPath --ffmpeg $ffmpegPath
    if ($LASTEXITCODE -ne 0) {
        throw "Renderer exited with code $LASTEXITCODE"
    }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Output $OutputVideo
