import argparse
import os
import subprocess

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Central points on the visible lower brow edge and the corresponding upper
# lash root. The pairs are mirrored so that each bracket remains local to one eye.
EYE_PAIRS = ((66, 159), (293, 386))


def point(landmark, width, height):
    return np.array((landmark.x * width, landmark.y * height), dtype=np.float32)


def overlay_bracket(frame, top, bottom, alpha=1.0):
    """Draw a delicate vertical upper-lid-space marker without any text."""
    height, width = frame.shape[:2]
    layer = frame.copy()
    cream = (218, 232, 247)  # BGR: warm ivory
    white = (248, 248, 248)
    red = (74, 92, 190)      # BGR: muted red

    vector = bottom - top
    length = max(float(np.linalg.norm(vector)), 1.0)
    unit = vector / length
    perpendicular = np.array((-unit[1], unit[0]), dtype=np.float32)
    band_half_width = max(5.0, min(width * 0.011, length * 0.30))

    quad = np.array([
        top + perpendicular * band_half_width,
        bottom + perpendicular * band_half_width,
        bottom - perpendicular * band_half_width,
        top - perpendicular * band_half_width,
    ], dtype=np.int32)
    cv2.fillConvexPoly(layer, quad, cream)
    frame[:] = cv2.addWeighted(layer, 0.18 * alpha, frame, 1.0 - 0.18 * alpha, 0)

    top_i, bottom_i = tuple(np.rint(top).astype(int)), tuple(np.rint(bottom).astype(int))
    tick = int(max(6, min(13, width * 0.012)))
    thickness = max(1, round(width / 600))
    cv2.line(frame, top_i, bottom_i, white, thickness, cv2.LINE_AA)
    cv2.line(frame, tuple(np.rint(top - perpendicular * tick).astype(int)),
             tuple(np.rint(top + perpendicular * tick).astype(int)), white, thickness, cv2.LINE_AA)
    cv2.line(frame, tuple(np.rint(bottom - perpendicular * tick).astype(int)),
             tuple(np.rint(bottom + perpendicular * tick).astype(int)), white, thickness, cv2.LINE_AA)

    radius = int(max(4, min(8, width * 0.007)))
    for target in (top_i, bottom_i):
        cv2.circle(frame, target, radius + 1, white, -1, cv2.LINE_AA)
        cv2.circle(frame, target, radius, red, -1, cv2.LINE_AA)


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

    base_options = python.BaseOptions(model_asset_path=args.model)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
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
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = round(frame_index * 1000.0 / fps)
            result = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms
            )

            if result.face_landmarks:
                landmarks = result.face_landmarks[0]
                measured_pairs = []
                for brow_index, lash_index in EYE_PAIRS:
                    brow = point(landmarks[brow_index], width, height)
                    lash = point(landmarks[lash_index], width, height)
                    # The design communicates a vertical distance, so its two
                    # anchors share one x-axis while retaining true brow/lash height.
                    center_x = (brow[0] + lash[0]) / 2.0
                    measured_pairs.append((center_x, brow[1], center_x, lash[1]))
                measured = np.array(measured_pairs, dtype=np.float32)
                smoothed = measured if smoothed is None else smoothed * 0.45 + measured * 0.55
                held_frames = 0
                draw_alpha = 1.0
            elif smoothed is not None and held_frames < 8:
                held_frames += 1
                draw_alpha = max(0.0, 1.0 - held_frames / 9.0)
            else:
                smoothed = None
                draw_alpha = 0.0

            if smoothed is not None:
                for x1, y1, x2, y2 in smoothed:
                    overlay_bracket(frame, np.array((x1, y1)), np.array((x2, y2)), draw_alpha)
            writer.write(frame)
            frame_index += 1

    capture.release()
    writer.release()
    command = [
        args.ffmpeg, "-y", "-i", temp_output, "-i", args.input,
        "-map", "0:v:0", "-map", "1:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-movflags", "+faststart", args.output,
    ]
    subprocess.run(command, check=True)
    os.remove(temp_output)
    print(f"Rendered {frame_index}/{frame_count} frames to {args.output}")


if __name__ == "__main__":
    main()
