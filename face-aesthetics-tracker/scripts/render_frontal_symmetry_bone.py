import argparse
import math
import os
import subprocess

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


FACE_OVAL = (10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
             397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10)
LEFT_ORBIT = (33, 160, 158, 133, 153, 144, 145, 163, 7, 33)
RIGHT_ORBIT = (263, 387, 385, 362, 380, 373, 374, 390, 249, 263)
JAW = (234, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378,
       379, 365, 397, 288, 361, 323, 454)
NOSE = (168, 6, 197, 195, 5, 4, 1, 19, 94, 2)
MIDLINE = (10, 168, 6, 1, 2, 13, 0, 17, 152)
LEFT_CHEEK = (33, 127, 234, 132, 58, 98, 133)
RIGHT_CHEEK = (263, 356, 454, 323, 288, 327, 362)
LEFT_MAXILLA = (98, 61, 13, 133)
RIGHT_MAXILLA = (327, 291, 13, 362)
PAIRS = ((33, 263), (234, 454), (98, 327), (172, 397))
REQUIRED = tuple(sorted(set(FACE_OVAL + LEFT_ORBIT + RIGHT_ORBIT + JAW + NOSE + MIDLINE +
                            LEFT_CHEEK + RIGHT_CHEEK + LEFT_MAXILLA + RIGHT_MAXILLA +
                            tuple(item for pair in PAIRS for item in pair))))


def as_points(face, ids, width, height):
    return np.array([[face[index].x * width, face[index].y * height] for index in ids], dtype=np.float32)


def track_points(result, width, height):
    if not result.face_landmarks:
        return None
    face = result.face_landmarks[0]
    return {index: np.array([face[index].x * width, face[index].y * height], dtype=np.float32)
            for index in REQUIRED}


def route(points, ids):
    return np.array([points[index] for index in ids], dtype=np.int32)


def draw_polyline(canvas, points, ids, color, thickness, closed=False):
    cv2.polylines(canvas, [route(points, ids)], closed, color, thickness, cv2.LINE_AA)


def expanded_orbit(points, ids, horizontal=1.48, vertical=2.05):
    contour = np.array([points[index] for index in ids[:-1]], dtype=np.float32)
    centre = contour.mean(axis=0)
    expanded = contour - centre
    expanded[:, 0] *= horizontal
    expanded[:, 1] *= vertical
    return np.round(expanded + centre).astype(np.int32)


def frontality(points):
    nose = points[1]
    left = np.linalg.norm(points[33] - nose)
    right = np.linalg.norm(points[263] - nose)
    imbalance = abs(left - right) / max((left + right) / 2.0, 1.0)
    return float(np.clip(1.0 - imbalance * 2.3, 0.42, 1.0))


def blend(frame, layer, alpha):
    weight = np.clip(alpha, 0.0, 1.0)
    return cv2.addWeighted(layer, weight, frame, 1.0 - weight, 0.0)


def paint_perspective(frame, points, seconds):
    height, width = frame.shape[:2]
    line_layer = np.zeros_like(frame)
    fill_mask = np.zeros((height, width), dtype=np.uint8)

    # Feathered anatomical planes: they read as a transparent projection, not face paint.
    left_orbit = expanded_orbit(points, LEFT_ORBIT)
    right_orbit = expanded_orbit(points, RIGHT_ORBIT)
    cv2.fillPoly(fill_mask, [route(points, LEFT_CHEEK)], 255, cv2.LINE_AA)
    cv2.fillPoly(fill_mask, [route(points, RIGHT_CHEEK)], 255, cv2.LINE_AA)
    cv2.fillPoly(fill_mask, [route(points, LEFT_MAXILLA)], 180, cv2.LINE_AA)
    cv2.fillPoly(fill_mask, [route(points, RIGHT_MAXILLA)], 180, cv2.LINE_AA)
    cv2.fillPoly(fill_mask, [left_orbit], 95, cv2.LINE_AA)
    cv2.fillPoly(fill_mask, [right_orbit], 95, cv2.LINE_AA)
    cv2.GaussianBlur(fill_mask, (31, 31), 0, dst=fill_mask)
    fill_color = np.full_like(frame, (184, 179, 204))  # muted bone rose, BGR

    # Primary anatomy, restrained and symmetrical.
    bone = (203, 211, 228)
    accent = (166, 181, 206)
    fine = (226, 228, 237)
    cv2.polylines(line_layer, [left_orbit], True, bone, 2, cv2.LINE_AA)
    cv2.polylines(line_layer, [right_orbit], True, bone, 2, cv2.LINE_AA)
    draw_polyline(line_layer, points, NOSE, bone, 2, False)
    draw_polyline(line_layer, points, JAW, accent, 2, False)
    draw_polyline(line_layer, points, LEFT_CHEEK, accent, 2, False)
    draw_polyline(line_layer, points, RIGHT_CHEEK, accent, 2, False)
    draw_polyline(line_layer, points, MIDLINE, fine, 1, False)

    # Fine outer contour is intentionally broken by the low opacity, so it feels projected.
    draw_polyline(line_layer, points, FACE_OVAL, (181, 194, 217), 1, True)

    # Paired key points make the symmetry legible without numbers or a measurement grid.
    for left, right in PAIRS:
        for index in (left, right):
            x, y = np.round(points[index]).astype(int)
            cv2.circle(line_layer, (x, y), 3, (230, 226, 240), -1, cv2.LINE_AA)
            cv2.circle(line_layer, (x, y), 5, (175, 185, 215), 1, cv2.LINE_AA)
    for index in (10, 168, 1, 13, 17, 152):
        x, y = np.round(points[index]).astype(int)
        cv2.circle(line_layer, (x, y), 3, (234, 232, 244), -1, cv2.LINE_AA)

    # A low-frequency breathing reveal gives the requested intermittent X-ray perspective.
    entrance = np.clip(seconds / 0.48, 0.0, 1.0)
    pulse = 0.52 + 0.48 * (0.5 + 0.5 * math.sin(seconds * math.tau / 1.8 - 0.7))
    facing = frontality(points)
    fill_alpha = 0.12 * entrance * pulse * facing
    line_alpha = 0.57 * entrance * pulse * facing
    # Per-pixel blend keeps the projection soft around the anatomy planes.
    fill_weight = (fill_mask.astype(np.float32) / 255.0 * fill_alpha)[..., None]
    frame = np.clip(frame.astype(np.float32) * (1.0 - fill_weight) + fill_color.astype(np.float32) * fill_weight,
                    0, 255).astype(np.uint8)
    return blend(frame, line_layer, line_alpha)


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
    silent = os.path.splitext(args.output)[0] + '.silent.mp4'
    writer = cv2.VideoWriter(silent, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

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
            detected = track_points(detector.detect_for_video(image, timestamp), width, height)
            if detected:
                if smoothed is None:
                    smoothed = detected
                else:
                    smoothed = {key: smoothed[key] * 0.70 + detected[key] * 0.30 for key in REQUIRED}
                frame = paint_perspective(frame, smoothed, frame_index / fps)
            writer.write(frame)
            frame_index += 1

    cap.release()
    writer.release()
    subprocess.run([
        args.ffmpeg, '-y', '-i', silent, '-i', args.input,
        '-map', '0:v:0', '-map', '1:a?', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
        '-c:a', 'aac', '-movflags', '+faststart', args.output,
    ], check=True)
    os.remove(silent)


if __name__ == '__main__':
    main()
