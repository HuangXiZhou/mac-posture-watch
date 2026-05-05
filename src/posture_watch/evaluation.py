from __future__ import annotations

from dataclasses import dataclass

from .models import Baseline, Features, ViewType
from .scoring import score_posture

DEFAULT_TRIGGER = 70.0


@dataclass(frozen=True)
class EvalCase:
    name: str
    expected_bad: bool
    features: Features


@dataclass(frozen=True)
class EvalResult:
    case: EvalCase
    score: float
    predicted_bad: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvalReport:
    threshold: float
    results: tuple[EvalResult, ...]

    @property
    def true_positives(self) -> int:
        return sum(result.predicted_bad and result.case.expected_bad for result in self.results)

    @property
    def false_positives(self) -> int:
        return sum(result.predicted_bad and not result.case.expected_bad for result in self.results)

    @property
    def false_negatives(self) -> int:
        return sum(not result.predicted_bad and result.case.expected_bad for result in self.results)

    @property
    def precision(self) -> float:
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else 1.0

    @property
    def recall(self) -> float:
        positives = self.true_positives + self.false_negatives
        return self.true_positives / positives if positives else 1.0


def synthetic_baseline() -> Baseline:
    return Baseline(
        version=1,
        created_at="2026-01-01T00:00:00Z",
        samples=30,
        view_type="front_side",
        features={
            "pitch_deg": 0.0,
            "yaw_deg": 0.0,
            "roll_deg": 0.0,
            "face_size": 0.05,
            "face_center_x": 0.5,
            "face_center_y": 0.35,
            "shoulder_width": 0.35,
            "shoulder_center_x": 0.5,
            "shoulder_center_y": 0.62,
            "nose_shoulder_dy": -0.25,
            "ear_shoulder_dx": 0.02,
            "shoulder_slope": 0.0,
            "stillness": 1.0,
        },
    )


def synthetic_cases() -> tuple[EvalCase, ...]:
    return (
        EvalCase("front/upright", False, _features("front")),
        EvalCase(
            "front/laptop-low-angle-normal",
            False,
            _features("front", pitch_deg=5.0, face_center_y=0.37, nose_shoulder_dy=-0.23),
        ),
        EvalCase(
            "front_side/normal-yaw",
            False,
            _features("front_side", yaw_deg=28.0, ear_shoulder_dx=0.04, face_center_y=0.36),
        ),
        EvalCase(
            "front/normal-minor-close",
            False,
            _features("front", face_size=0.055, face_center_y=0.36),
        ),
        EvalCase(
            "face_only/normal-cropped",
            False,
            _features("face_only", pitch_deg=4.0, face_size=0.052, face_center_y=0.36),
        ),
        EvalCase(
            "front/low-head",
            True,
            _features("front", pitch_deg=25.0, face_center_y=0.46, nose_shoulder_dy=-0.13),
        ),
        EvalCase(
            "front/too-close",
            True,
            _features("front", face_size=0.085, face_center_y=0.41),
        ),
        EvalCase(
            "front_side/forward-head",
            True,
            _features("front_side", ear_shoulder_dx=0.13, face_size=0.075, shoulder_center_y=0.65),
        ),
        EvalCase(
            "front/rounded-shoulders",
            True,
            _features("front", shoulder_width=0.26, shoulder_slope=0.08),
        ),
        EvalCase(
            "face_only/severe-low-close",
            True,
            _features("face_only", pitch_deg=35.0, face_size=0.12, face_center_y=0.48),
        ),
    )


def evaluate_synthetic_postures(threshold: float = DEFAULT_TRIGGER) -> EvalReport:
    baseline = synthetic_baseline()
    results = []
    for case in synthetic_cases():
        score = score_posture(case.features, baseline)
        results.append(
            EvalResult(
                case=case,
                score=score.total,
                predicted_bad=score.total >= threshold,
                reasons=score.reasons,
            )
        )
    return EvalReport(threshold=threshold, results=tuple(results))


def format_report(report: EvalReport) -> str:
    lines = [
        f"threshold={report.threshold:.1f}",
        f"precision={report.precision:.2f}",
        f"recall={report.recall:.2f}",
        "",
        "case,expected,predicted,score,reasons",
    ]
    for result in report.results:
        lines.append(
            f"{result.case.name},"
            f"{int(result.case.expected_bad)},"
            f"{int(result.predicted_bad)},"
            f"{result.score:.1f},"
            f"{'|'.join(result.reasons) or '-'}"
        )
    return "\n".join(lines)


def _features(view_type: ViewType, **overrides: float) -> Features:
    data = {
        "timestamp": 0.0,
        "view_type": view_type,
        "pitch_deg": 0.0,
        "yaw_deg": 0.0,
        "roll_deg": 0.0,
        "face_size": 0.05,
        "face_center_x": 0.5,
        "face_center_y": 0.35,
        "shoulder_width": 0.35,
        "shoulder_center_x": 0.5,
        "shoulder_center_y": 0.62,
        "nose_shoulder_dy": -0.25,
        "ear_shoulder_dx": 0.02,
        "shoulder_slope": 0.0,
        "stillness": 1.0,
    }
    data.update(overrides)
    return Features(**data)
