from __future__ import annotations

import math

from .models import Detection, Features, FrameQuality, Landmark, ViewType
from .scoring import clamp


class MotionEstimator:
    def __init__(self) -> None:
        self.previous_gray = None

    def stillness(self, frame) -> float:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (96, 54))
        if self.previous_gray is None:
            self.previous_gray = gray
            return 1.0
        diff = cv2.absdiff(gray, self.previous_gray).mean() / 255.0
        self.previous_gray = gray
        return clamp(1.0 - diff / 0.055, 0.0, 1.0)


def assess_frame_quality(frame, detection: Detection) -> FrameQuality:
    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    has_face = len(detection.face) >= 100
    has_shoulders = _visible(detection.pose.get("left_shoulder")) and _visible(
        detection.pose.get("right_shoulder")
    )

    if brightness < 28:
        return FrameQuality(False, "too_dark", brightness, blur, has_face, has_shoulders)
    if blur < 12:
        return FrameQuality(False, "too_blurry", brightness, blur, has_face, has_shoulders)
    if not has_face:
        return FrameQuality(False, "no_face", brightness, blur, has_face, has_shoulders)
    return FrameQuality(True, "ok", brightness, blur, has_face, has_shoulders)


def extract_features(
    detection: Detection,
    *,
    quality: FrameQuality,
    stillness: float,
) -> Features:
    face_size, face_center_x, face_center_y = _face_bbox_features(detection.face)
    pitch, yaw, roll = _estimate_head_pose(detection.face, detection.image_width, detection.image_height)
    view_type = classify_view(detection, quality, yaw)

    left_shoulder = detection.pose.get("left_shoulder")
    right_shoulder = detection.pose.get("right_shoulder")
    nose = detection.pose.get("nose")
    shoulder_width = 0.0
    shoulder_center_x = 0.0
    shoulder_center_y = 0.0
    shoulder_slope = 0.0
    nose_shoulder_dy = 0.0

    if _visible(left_shoulder) and _visible(right_shoulder):
        shoulder_width = _distance(left_shoulder, right_shoulder)
        shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2.0
        shoulder_center_y = (left_shoulder.y + right_shoulder.y) / 2.0
        shoulder_slope = right_shoulder.y - left_shoulder.y
        if _visible(nose):
            nose_shoulder_dy = nose.y - shoulder_center_y

    ear_shoulder_dx = _ear_shoulder_dx(detection)
    return Features(
        timestamp=detection.timestamp,
        view_type=view_type,
        pitch_deg=pitch,
        yaw_deg=yaw,
        roll_deg=roll,
        face_size=face_size,
        face_center_x=face_center_x,
        face_center_y=face_center_y,
        shoulder_width=shoulder_width,
        shoulder_center_x=shoulder_center_x,
        shoulder_center_y=shoulder_center_y,
        nose_shoulder_dy=nose_shoulder_dy,
        ear_shoulder_dx=ear_shoulder_dx,
        shoulder_slope=shoulder_slope,
        stillness=stillness,
    )


def classify_view(detection: Detection, quality: FrameQuality, yaw_deg: float) -> ViewType:
    if not quality.has_face:
        return "bad"
    if not quality.has_shoulders:
        return "face_only"

    left_ear = detection.pose.get("left_ear")
    right_ear = detection.pose.get("right_ear")
    left_ok = _visible(left_ear)
    right_ok = _visible(right_ear)
    if left_ok and right_ok and abs(yaw_deg) < 24:
        return "front"
    return "front_side"


def _visible(lm: Landmark | None, threshold: float = 0.45) -> bool:
    return bool(lm and lm.visibility >= threshold and lm.presence >= threshold)


def _distance(a: Landmark, b: Landmark) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _face_bbox_features(face: list[Landmark]) -> tuple[float, float, float]:
    if not face:
        return 0.0, 0.0, 0.0
    xs = [lm.x for lm in face]
    ys = [lm.y for lm in face]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (max_x - min_x) * (max_y - min_y), (min_x + max_x) / 2.0, (min_y + max_y) / 2.0


def _ear_shoulder_dx(detection: Detection) -> float:
    pairs = [
        (detection.pose.get("left_ear"), detection.pose.get("left_shoulder")),
        (detection.pose.get("right_ear"), detection.pose.get("right_shoulder")),
    ]
    values: list[tuple[float, float]] = []
    for ear, shoulder in pairs:
        if _visible(ear, 0.35) and _visible(shoulder, 0.35):
            confidence = min(ear.visibility, shoulder.visibility)
            values.append((confidence, ear.x - shoulder.x))
    if not values:
        return 0.0
    values.sort(reverse=True)
    if len(values) == 1:
        return values[0][1]
    return (values[0][1] + values[1][1]) / 2.0


def _estimate_head_pose(face: list[Landmark], width: int, height: int) -> tuple[float, float, float]:
    if len(face) <= 291:
        return 0.0, 0.0, 0.0
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0.0, 0.0, 0.0

    image_points = np.array(
        [
            _image_point(face[1], width, height),  # nose tip
            _image_point(face[152], width, height),  # chin
            _image_point(face[33], width, height),  # left eye corner
            _image_point(face[263], width, height),  # right eye corner
            _image_point(face[61], width, height),  # left mouth corner
            _image_point(face[291], width, height),  # right mouth corner
        ],
        dtype="double",
    )
    model_points = np.array(
        [
            (0.0, 0.0, 0.0),
            (0.0, -63.6, -12.5),
            (-43.3, 32.7, -26.0),
            (43.3, 32.7, -26.0),
            (-28.9, -28.9, -24.1),
            (28.9, -28.9, -24.1),
        ],
        dtype="double",
    )
    focal_length = float(width)
    camera_matrix = np.array(
        [[focal_length, 0, width / 2], [0, focal_length, height / 2], [0, 0, 1]],
        dtype="double",
    )
    dist_coeffs = np.zeros((4, 1))
    success, rotation_vector, _ = cv2.solvePnP(
        model_points,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        return 0.0, 0.0, 0.0
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    angles = cv2.RQDecomp3x3(rotation_matrix)[0]
    return float(angles[0]), float(angles[1]), float(angles[2])


def _image_point(lm: Landmark, width: int, height: int) -> tuple[float, float]:
    return (lm.x * width, lm.y * height)

