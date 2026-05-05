from __future__ import annotations

import time
from types import ModuleType

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
        pose_module, face_mesh_module = load_mediapipe_solution_modules()
        try:
            self.pose = pose_module.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                enable_segmentation=False,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self.face_mesh = face_mesh_module.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        except Exception as exc:
            raise RuntimeError(
                "MediaPipe legacy Pose/Face Mesh failed to initialize. "
                "Run `posture-watch doctor` for dependency details."
            ) from exc

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


def load_mediapipe_solution_modules() -> tuple[ModuleType, ModuleType]:
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise RuntimeError("Missing MediaPipe. Install with: pip install '.[vision]'") from exc

    solutions = getattr(mp, "solutions", None)
    if solutions is not None:
        pose = getattr(solutions, "pose", None)
        face_mesh = getattr(solutions, "face_mesh", None)
        if pose is not None and face_mesh is not None:
            return pose, face_mesh

    try:
        from mediapipe.python.solutions import face_mesh, pose
    except (ImportError, AttributeError) as exc:
        version = getattr(mp, "__version__", "unknown")
        raise RuntimeError(
            "Installed MediaPipe does not expose the legacy Pose/Face Mesh API "
            f"(mediapipe={version}). Install a legacy-compatible wheel, for example: "
            "pipx inject --force mac-posture-watch 'mediapipe<0.10.31'"
        ) from exc
    return pose, face_mesh


def mediapipe_legacy_status() -> tuple[bool, str]:
    try:
        load_mediapipe_solution_modules()
    except RuntimeError as exc:
        return False, str(exc)
    return True, "legacy Pose/Face Mesh available"
