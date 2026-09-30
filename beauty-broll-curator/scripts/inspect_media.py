#!/usr/bin/env python3
"""Inspect local video files with ffprobe and flag B-roll delivery issues."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def probe(path: Path, ffprobe: str) -> dict:
    command = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=codec_name,width,height,avg_frame_rate,pix_fmt", "-show_entries",
               "format=duration,size", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise ValueError("no video stream")
    return {"stream": data["streams"][0], "format": data.get("format", {})}


def rate(value: str) -> float:
    try:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    except (AttributeError, ValueError, ZeroDivisionError):
        return 0.0


def assess(path: Path, data: dict) -> dict:
    stream, fmt = data["stream"], data["format"]
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    issues: list[str] = []
    if min(width, height) < 1080:
        issues.append("short edge below 1080")
    if height <= width:
        issues.append("not vertical")
    if stream.get("codec_name") != "h264":
        issues.append("codec is not H.264")
    if stream.get("pix_fmt") != "yuv420p":
        issues.append("pixel format is not yuv420p")
    return {"file": path.name, "width": width, "height": height,
            "fps": round(rate(stream.get("avg_frame_rate", "0/1")), 3),
            "duration_seconds": round(float(fmt.get("duration", 0)), 3),
            "size_mb": round(int(fmt.get("size", 0)) / 1024 / 1024, 2),
            "codec": stream.get("codec_name", ""), "pixel_format": stream.get("pix_fmt", ""),
            "status": "PASS" if not issues else "CHECK", "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Video file or directory")
    parser.add_argument("--ffprobe", default="ffprobe", help="ffprobe executable")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()
    ffprobe = shutil.which(args.ffprobe) or (args.ffprobe if Path(args.ffprobe).is_file() else None)
    if not ffprobe:
        print("ffprobe was not found. Install FFmpeg or pass --ffprobe PATH.", file=sys.stderr)
        return 2
    target = args.path.expanduser().resolve()
    files = [target] if target.is_file() else sorted(
        item for item in target.rglob("*") if item.suffix.lower() in VIDEO_EXTENSIONS)
    rows = []
    for path in files:
        try:
            rows.append(assess(path, probe(path, ffprobe)))
        except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
            rows.append({"file": path.name, "status": "ERROR", "issues": [str(exc)]})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            resolution = f"{row.get('width', '?')}x{row.get('height', '?')}"
            issues = "; ".join(row.get("issues", [])) or "ready"
            print(f"{row['status']:5}  {resolution:10}  {row['file']}  ({issues})")
    return 1 if any(row["status"] == "ERROR" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
