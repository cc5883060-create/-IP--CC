import argparse
import os
import subprocess

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Each pair runs from the nasal-alar crease toward its mouth corner.
FOLD_PAIRS = ((98, 61, -1), (327, 291, 1))


def landmark_point(landmark, width, height):
    return np.array((landmark.x * width, landmark.y * height), dtype=np.float32)


def bezier(start, end, outward, width):
    """A gentle facial-fold curve, bowed slightly toward the cheek."""
    offset = np.array((outward * width * 0.018, 0), dtype=np.float32)
    control_1 = start * 0.68 + end * 0.32 + offset
    control_2 = start * 0.28 + end * 0.72 + offset
    t = np.linspace(0.0, 1.0, 17, dtype=np.float32)[:, None]
    return (1 - t) ** 3 * start + 3 * (1 - t) ** 2 * t * control_1 + 3 * (1 - t) * t ** 2 * control_2 + t ** 3 * end


def draw_fold_region(frame, start, end, outward, opacity=1.0):
    """Frame the fold area from outside, keeping all wrinkle texture unobstructed."""
    height, width = frame.shape[:2]
    curve = bezier(start, end, outward, width)
    left, top = curve.min(axis=0)
    right, bottom = curve.max(axis=0)
    pad_x = max(12, round(width * 0.022))
    pad_y = max(10, round(height * 0.012))
    left, right = int(left - pad_x), int(right + pad_x)
    top, bottom = int(top - pad_y), int(bottom + pad_y)
    arm = max(10, round(width * 0.018))
    white = (246, 246, 246)
    thickness = max(1, round(width / 600))

    # Four isolated corner brackets define the region; no mark crosses the
    # nasolabial crease, so its change remains completely visible.
    corners = (
        ((left, top), (left + arm, top), (left, top + arm)),
        ((right, top), (right - arm, top), (right, top + arm)),
        ((left, bottom), (left + arm, bottom), (left, bottom - arm)),
        ((right, bottom), (right - arm, bottom), (right, bottom - arm)),
    )
    layer = frame.copy()
    for elbow, horizontal, vertical in corners:
        cv2.line(layer, elbow, horizontal, white, thickness, cv2.LINE_AA)
        cv2.line(layer, elbow, vertical, white, thickness, cv2.LINE_AA)
    frame[:] = cv2.addWeighted(layer, opacity, frame, 1 - opacity, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ffmpeg", required=True)
    args = parser.parse_args()

    capture = cv2.VideoCapture(args.input)
    if not capture.isOpened():
        raise RuntimeError("Could not open input video")
    fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    temp_output = os.path.splitext(args.output)[0] + ".silent.mp4"
    writer = cv2.VideoWriter(temp_output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not initialize local video renderer")

    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=args.model),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.55,
        min_face_presence_confidence=0.55,
        min_tracking_confidence=0.55,
    )
    smoothed = None
    held_frames = 0
    frame_index = 0
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                round(frame_index * 1000.0 / fps),
            )
            if result.face_landmarks:
                face = result.face_landmarks[0]
                measured = np.array(
                    [[*landmark_point(face[nose], width, height), *landmark_point(face[mouth], width, height), side]
                     for nose, mouth, side in FOLD_PAIRS], dtype=np.float32,
                )
                smoothed = measured if smoothed is None else smoothed * 0.45 + measured * 0.55
                held_frames, opacity = 0, 1.0
            elif smoothed is not None and held_frames < 8:
                held_frames += 1
                opacity = max(0.0, 1.0 - held_frames / 9.0)
            else:
                smoothed, opacity = None, 0.0

            if smoothed is not None:
                for x1, y1, x2, y2, side in smoothed:
                    draw_fold_region(frame, np.array((x1, y1)), np.array((x2, y2)), side, opacity)
            writer.write(frame)
            frame_index += 1

    capture.release()
    writer.release()
    subprocess.run([
        args.ffmpeg, "-y", "-i", temp_output, "-i", args.input, "-map", "0:v:0", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-movflags", "+faststart", args.output,
    ], check=True)
    os.remove(temp_output)
    print(f"Rendered {frame_index}/{frame_count} frames to {args.output}")


if __name__ == "__main__":
    main()
