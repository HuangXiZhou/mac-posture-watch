from __future__ import annotations


class Camera:
    def __init__(self, index: int) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("Missing camera dependency. Install with: pip install '.[vision]'") from exc

        self.cv2 = cv2
        backend = cv2.CAP_AVFOUNDATION if hasattr(cv2, "CAP_AVFOUNDATION") else 0
        self.capture = cv2.VideoCapture(index, backend)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = cv2.VideoCapture(index)
        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open camera index {index}. Check macOS camera permission and index."
            )
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self):
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise RuntimeError("Camera returned no frame.")
        return frame

    def close(self) -> None:
        self.capture.release()

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

