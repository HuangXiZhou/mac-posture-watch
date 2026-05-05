from __future__ import annotations

import time
from importlib.resources import files
from pathlib import Path

from .models import Detection, Landmark

POSE_LANDMARKS = {
    0: "nose",
    2: "left_eye",
    5: "right_eye",
    7: "left_ear",
    8: "right_ear",
    11: "left_shoulder",
    12: "right_shoulder",
    23: "left_hip",
    24: "right_hip",
}

POSE_MODEL_FILE = "pose_landmarker_lite.task"
FACE_MODEL_FILE = "face_landmarker.task"


def _asset_path(name: str) -> str:
    return str(files("posture_watch.assets").joinpath(name))


def assets_status() -> tuple[bool, str]:
    """Report whether bundled MediaPipe Tasks model files are present."""
    missing = [
        name
        for name in (POSE_MODEL_FILE, FACE_MODEL_FILE)
        if not Path(_asset_path(name)).is_file()
    ]
    if missing:
        return False, f"missing model assets: {', '.join(missing)}"
    return True, "model assets present"


class MediaPipeDetector:
    """Local CPU detector using MediaPipe Tasks PoseLandmarker + FaceLandmarker (VIDEO mode)."""

    def __init__(
        self,
        *,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            FaceLandmarker,
            FaceLandmarkerOptions,
            PoseLandmarker,
            PoseLandmarkerOptions,
            RunningMode,
        )

        self.pose = PoseLandmarker.create_from_options(
            PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_asset_path(POSE_MODEL_FILE)),
                running_mode=RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=min_detection_confidence,
                min_pose_presence_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        )
        self.face = FaceLandmarker.create_from_options(
            FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_asset_path(FACE_MODEL_FILE)),
                running_mode=RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=min_detection_confidence,
                min_face_presence_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        )
        self._t0 = time.monotonic()

    def detect(self, frame) -> Detection:
        import cv2
        import mediapipe as mp

        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires strictly increasing millisecond timestamps.
        ts_ms = int((time.monotonic() - self._t0) * 1000)

        pose_result = self.pose.detect_for_video(image, ts_ms)
        face_result = self.face.detect_for_video(image, ts_ms)

        pose: dict[str, Landmark] = {}
        if pose_result.pose_landmarks:
            landmarks = pose_result.pose_landmarks[0]
            for index, name in POSE_LANDMARKS.items():
                pose[name] = _landmark(landmarks[index])

        face: list[Landmark] = []
        if face_result.face_landmarks:
            face = [_landmark(lm) for lm in face_result.face_landmarks[0]]

        return Detection(
            timestamp=time.time(),
            image_width=width,
            image_height=height,
            pose=pose,
            face=face,
        )

    def close(self) -> None:
        self.pose.close()
        self.face.close()

    def __enter__(self) -> "MediaPipeDetector":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _landmark(lm) -> Landmark:
    return Landmark(
        x=float(lm.x),
        y=float(lm.y),
        z=_float_attr(lm, "z", 0.0),
        visibility=_float_attr(lm, "visibility", 1.0),
        presence=_float_attr(lm, "presence", 1.0),
    )


def _float_attr(obj, name: str, default: float) -> float:
    value = getattr(obj, name, default)
    if value is None:
        return default
    return float(value)
