from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ViewType = Literal["front", "front_side", "face_only", "bad"]


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0
    presence: float = 1.0


@dataclass(frozen=True)
class Detection:
    timestamp: float
    image_width: int
    image_height: int
    pose: dict[str, Landmark] = field(default_factory=dict)
    face: list[Landmark] = field(default_factory=list)


@dataclass(frozen=True)
class FrameQuality:
    ok: bool
    reason: str = "ok"
    brightness: float = 0.0
    blur: float = 0.0
    has_face: bool = False
    has_shoulders: bool = False


@dataclass(frozen=True)
class Features:
    timestamp: float
    view_type: ViewType
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    roll_deg: float = 0.0
    face_size: float = 0.0
    face_center_x: float = 0.0
    face_center_y: float = 0.0
    shoulder_width: float = 0.0
    shoulder_center_x: float = 0.0
    shoulder_center_y: float = 0.0
    nose_shoulder_dy: float = 0.0
    ear_shoulder_dx: float = 0.0
    shoulder_slope: float = 0.0
    stillness: float = 1.0

    def numeric(self) -> dict[str, float]:
        return {
            "pitch_deg": self.pitch_deg,
            "yaw_deg": self.yaw_deg,
            "roll_deg": self.roll_deg,
            "face_size": self.face_size,
            "face_center_x": self.face_center_x,
            "face_center_y": self.face_center_y,
            "shoulder_width": self.shoulder_width,
            "shoulder_center_x": self.shoulder_center_x,
            "shoulder_center_y": self.shoulder_center_y,
            "nose_shoulder_dy": self.nose_shoulder_dy,
            "ear_shoulder_dx": self.ear_shoulder_dx,
            "shoulder_slope": self.shoulder_slope,
            "stillness": self.stillness,
        }


@dataclass(frozen=True)
class Baseline:
    version: int
    created_at: str
    samples: int
    view_type: ViewType
    features: dict[str, float]

    def value(self, name: str, default: float = 0.0) -> float:
        return float(self.features.get(name, default))

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "samples": self.samples,
            "view_type": self.view_type,
            "features": self.features,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Baseline":
        return cls(
            version=int(data.get("version", 1)),
            created_at=str(data.get("created_at", "")),
            samples=int(data.get("samples", 0)),
            view_type=data.get("view_type", "front"),
            features={str(k): float(v) for k, v in data.get("features", {}).items()},
        )


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    head_pitch: float
    forward_head: float
    face_distance: float
    shoulder_rounding: float
    stillness: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    is_bad_posture: bool
    severity: str
    confidence: float
    visible_evidence: tuple[str, ...] = ()
    reason: str = ""
    raw_text: str = ""

    @property
    def confirmed_bad(self) -> bool:
        return (
            self.is_bad_posture
            and self.confidence >= 0.75
            and self.severity in {"moderate", "severe"}
        )

