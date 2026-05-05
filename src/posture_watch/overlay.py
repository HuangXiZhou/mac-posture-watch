from __future__ import annotations

from .models import Detection


def encode_jpeg(frame, *, max_side: int = 640, quality: int = 65) -> bytes:
    import cv2

    height, width = frame.shape[:2]
    scale = min(1.0, max_side / max(height, width))
    if scale < 1.0:
        frame = cv2.resize(frame, (int(width * scale), int(height * scale)))
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("Could not encode JPEG frame.")
    return encoded.tobytes()


def draw_overlay(frame, detection: Detection, *, score: float, view_type: str, reasons: tuple[str, ...]):
    import cv2

    output = frame.copy()
    height, width = output.shape[:2]
    _draw_pose(output, detection, width, height)
    _draw_face_box(output, detection, width, height)
    label = f"score={score:.0f} view={view_type} {'/'.join(reasons)}"
    cv2.putText(
        output,
        label[:96],
        (14, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 220, 255),
        2,
        cv2.LINE_AA,
    )
    return output


def _draw_pose(output, detection: Detection, width: int, height: int) -> None:
    import cv2

    points = {
        name: (int(lm.x * width), int(lm.y * height))
        for name, lm in detection.pose.items()
        if lm.visibility >= 0.35
    }
    for a, b in [
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_ear"),
        ("right_shoulder", "right_ear"),
        ("nose", "left_ear"),
        ("nose", "right_ear"),
    ]:
        if a in points and b in points:
            cv2.line(output, points[a], points[b], (60, 200, 60), 2)
    for point in points.values():
        cv2.circle(output, point, 4, (0, 255, 0), -1)


def _draw_face_box(output, detection: Detection, width: int, height: int) -> None:
    import cv2

    if not detection.face:
        return
    xs = [int(lm.x * width) for lm in detection.face]
    ys = [int(lm.y * height) for lm in detection.face]
    cv2.rectangle(output, (min(xs), min(ys)), (max(xs), max(ys)), (255, 180, 0), 2)

