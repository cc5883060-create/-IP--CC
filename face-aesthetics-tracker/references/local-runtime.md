# Local runtime

The renderers use Python, MediaPipe Face Landmarker, OpenCV, NumPy, and FFmpeg. All face analysis and compositing run locally; no input media is uploaded.

## One-time setup

Run:

```powershell
& .\scripts\setup_local.ps1
```

On the original workstation, setup reuses the already-validated package directory and FFmpeg binary when available, copying them into `.runtime/` under the skill. On another Windows machine, it installs pinned Python packages and requires either FFmpeg on `PATH` or `-FfmpegSource` pointing to `ffmpeg.exe`.

The bundled `assets/models/face_landmarker.task` is the local face-landmark model. Do not replace it unless model compatibility is verified against all four renderers.

## Runtime layout

```text
face-aesthetics-tracker/
├── assets/models/face_landmarker.task
├── scripts/
└── .runtime/
    ├── python/
    └── bin/ffmpeg.exe
```

## Repair

If imports fail, remove only the skill's `.runtime/python` directory after resolving its absolute path, then rerun setup. If encoding fails, pass a known FFmpeg executable with `-FfmpegSource` and rerun setup. Do not delete or modify the user's source media.
