import argparse
import os
import subprocess

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


LANDMARKS = (49, 97, 98, 115, 129, 209, 235, 281, 294, 326, 327, 344, 371)


def cubic(p0, p1, p2, p3, count=24):
    t = np.linspace(0.0, 1.0, count, dtype=np.float32)[:, None]
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 +
            3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3)


def points_from(result, width, height):
    if not result.face_landmarks:
        return None
    face = result.face_landmarks[0]
    return {
        index: np.array([face[index].x * width, face[index].y * height], dtype=np.float32)
        for index in LANDMARKS
    }


def blend_color(frame, mask, bgr, opacity):
    alpha = (mask.astype(np.float32) / 255.0 * opacity)[..., None]
    tint = np.asarray(bgr, dtype=np.float32)
    return np.clip(frame.astype(np.float32) * (1.0 - alpha) + tint * alpha, 0, 255).astype(np.uint8)


def crescent_polygon(p, side):
    # Compact bilateral alar-base crescent.  All points remain in the nasal-wing
    # neighborhood: no mouth-corner or central-columella points are used.
    if side < 0:
        top, outer_top, outer_bottom, lower_inner, inner = (
            p[209], p[129], p[98], p[97], p[115]
        )
    else:
        top, outer_top, outer_bottom, lower_inner, inner = (
            p[281], p[371], p[294], p[326], p[344]
        )
    outer = cubic(top, outer_top, outer_bottom, lower_inner)
    return_curve = cubic(
        lower_inner,
        inner,
        inner,
        top,
    )
    return np.vstack((outer, return_curve)).round().astype(np.int32)


def overlay_design(frame, p):
    height, width = frame.shape[:2]
    support = np.zeros((height, width), dtype=np.uint8)
    base = np.zeros((height, width), dtype=np.uint8)

    for side in (-1, 1):
        if side < 0:
            top, outer_top, outer_bottom = p[209], p[129], p[98]
        else:
            top, outer_top, outer_bottom = p[281], p[371], p[294]
        polygon = crescent_polygon(p, side)
        cv2.fillPoly(base, [polygon], 255)

        # A larger, low-opacity halo suggests the supporting mid-face plane without
        # drawing an edge through the facial features.
        anchor = (outer_top + outer_bottom) / 2.0
        center = anchor + np.array([side * width * 0.045, height * 0.010], dtype=np.float32)
        angle = float(np.degrees(np.arctan2((outer_bottom - outer_top)[1],
                                            (outer_bottom - outer_top)[0])))
        short_axis = int(np.clip(np.linalg.norm(outer_top - top) * 2.4, width * 0.040, width * 0.065))
        long_axis = int(np.clip(np.linalg.norm(outer_bottom - outer_top) * 2.0, height * 0.050, height * 0.090))
        cv2.ellipse(
            support,
            tuple(np.round(center).astype(int)),
            (short_axis, long_axis),
            angle,
            0,
            360,
            255,
            -1,
            cv2.LINE_AA,
        )

    halo_blur = max(61, int(width * 0.10) | 1)
    base_blur = max(13, int(width * 0.014) | 1)
    support = cv2.GaussianBlur(support, (halo_blur, halo_blur), 0)
    base = cv2.GaussianBlur(base, (base_blur, base_blur), 0)
    # Preserve a readable centre after the intentionally large feathering pass.
    cv2.normalize(support, support, 0, 255, cv2.NORM_MINMAX)
    frame = blend_color(frame, support, (160, 190, 246), 0.15)  # soft rose-champagne support glow
    return blend_color(frame, base, (115, 165, 242), 0.24)      # compact apricot nasal-base selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--ffmpeg', required=True)
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        raise RuntimeError('Unable to open input video')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    silent_path = os.path.splitext(args.output)[0] + '.silent.mp4'
    writer = cv2.VideoWriter(silent_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=args.model),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.55,
        min_face_presence_confidence=0.55,
        min_tracking_confidence=0.55,
    )
    smoothed = None
    frame_index = 0
    with vision.FaceLandmarker.create_from_options(options) as detector:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            timestamp = int(round(frame_index * 1000.0 / fps))
            image = mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            detected = points_from(detector.detect_for_video(image, timestamp), width, height)
            if detected:
                if smoothed is None:
                    smoothed = detected
                else:
                    smoothed = {key: smoothed[key] * 0.70 + detected[key] * 0.30 for key in LANDMARKS}
                frame = overlay_design(frame, smoothed)
            writer.write(frame)
            frame_index += 1

    cap.release()
    writer.release()
    subprocess.run([
        args.ffmpeg, '-y', '-i', silent_path, '-i', args.input,
        '-map', '0:v:0', '-map', '1:a?', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
        '-c:a', 'aac', '-movflags', '+faststart', args.output,
    ], check=True)
    os.remove(silent_path)


if __name__ == '__main__':
    main()
