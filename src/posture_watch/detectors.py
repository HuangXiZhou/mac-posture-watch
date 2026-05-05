from __future__ import annotations

import time

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


class MediaPipeDetector:
    """CPU-only local detector using MediaPipe Pose and Face Mesh solutions."""

    def __init__(
        self,
        *,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("Missing MediaPipe. Install with: pip install '.[vision]'") from exc

        self.mp = mp
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def detect(self, frame) -> Detection:
        import cv2

        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        pose_result = self.pose.process(rgb)
        face_result = self.face_mesh.process(rgb)

        pose: dict[str, Landmark] = {}
        if pose_result.pose_landmarks:
            for index, name in POSE_LANDMARKS.items():
                lm = pose_result.pose_landmarks.landmark[index]
                pose[name] = _landmark(lm)

        face: list[Landmark] = []
        if face_result.multi_face_landmarks:
            face = [_landmark(lm) for lm in face_result.multi_face_landmarks[0].landmark]

        return Detection(
            timestamp=time.time(),
            image_width=width,
            image_height=height,
            pose=pose,
            face=face,
        )

    def close(self) -> None:
        self.pose.close()
        self.face_mesh.close()

    def __enter__(self) -> "MediaPipeDetector":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _landmark(lm) -> Landmark:
    return Landmark(
        x=float(lm.x),
        y=float(lm.y),
        z=float(getattr(lm, "z", 0.0)),
        visibility=float(getattr(lm, "visibility", 1.0)),
        presence=float(getattr(lm, "presence", 1.0)),
    )

