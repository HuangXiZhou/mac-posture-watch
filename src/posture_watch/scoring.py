from __future__ import annotations

from .models import Baseline, Features, ScoreBreakdown


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def ramp(value: float, start: float, full: float) -> float:
    if full <= start:
        return 0.0
    if value <= start:
        return 0.0
    return clamp((value - start) / (full - start) * 100.0)


def _ratio_increase(current: float, baseline: float, start: float, full: float) -> float:
    if baseline <= 0:
        return 0.0
    return ramp((current / baseline) - 1.0, start, full)


def _ratio_decrease(current: float, baseline: float, start: float, full: float) -> float:
    if baseline <= 0:
        return 0.0
    return ramp(1.0 - (current / baseline), start, full)


def score_posture(features: Features, baseline: Baseline) -> ScoreBreakdown:
    if features.view_type == "bad":
        return ScoreBreakdown(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ("bad_view",))

    pitch_score = _head_pitch_score(features, baseline)
    face_distance = _face_distance_score(features, baseline)
    forward_head = _forward_head_score(features, baseline, face_distance)
    shoulder_rounding = _shoulder_rounding_score(features, baseline)
    stillness = clamp(features.stillness * 100.0)

    if features.view_type == "face_only":
        weighted = 0.56 * pitch_score + 0.34 * face_distance + 0.10 * stillness
        total = _evidence_supported_total(weighted, (pitch_score, face_distance), stillness)
        total = min(total, 76.0)
    elif features.view_type == "front":
        weighted = (
            0.38 * pitch_score
            + 0.18 * forward_head
            + 0.24 * face_distance
            + 0.10 * shoulder_rounding
            + 0.10 * stillness
        )
        total = _evidence_supported_total(
            weighted,
            (pitch_score, forward_head, face_distance, shoulder_rounding),
            stillness,
        )
    else:
        weighted = (
            0.30 * pitch_score
            + 0.32 * forward_head
            + 0.18 * face_distance
            + 0.10 * shoulder_rounding
            + 0.10 * stillness
        )
        total = _evidence_supported_total(
            weighted,
            (pitch_score, forward_head, face_distance, shoulder_rounding),
            stillness,
        )

    reasons: list[str] = []
    if pitch_score >= 55:
        reasons.append("head_pitch")
    if forward_head >= 55:
        reasons.append("forward_head")
    if face_distance >= 55:
        reasons.append("too_close")
    if shoulder_rounding >= 55:
        reasons.append("shoulder_rounding")
    if features.view_type == "face_only":
        reasons.append("face_only_cap")

    return ScoreBreakdown(
        total=clamp(total),
        head_pitch=clamp(pitch_score),
        forward_head=clamp(forward_head),
        face_distance=clamp(face_distance),
        shoulder_rounding=clamp(shoulder_rounding),
        stillness=stillness,
        reasons=tuple(reasons),
    )


def _head_pitch_score(features: Features, baseline: Baseline) -> float:
    pitch_delta = abs(features.pitch_deg - baseline.value("pitch_deg"))
    head_drop_delta = features.face_center_y - baseline.value("face_center_y")
    nose_drop_delta = features.nose_shoulder_dy - baseline.value("nose_shoulder_dy")
    return max(
        ramp(pitch_delta, 6.0, 22.0),
        ramp(head_drop_delta, 0.025, 0.12) * 0.75,
        ramp(nose_drop_delta, 0.025, 0.12) * 0.65,
    )


def _face_distance_score(features: Features, baseline: Baseline) -> float:
    return _ratio_increase(features.face_size, baseline.value("face_size"), 0.08, 0.38)


def _forward_head_score(features: Features, baseline: Baseline, face_distance: float) -> float:
    ear_forward_delta = abs(features.ear_shoulder_dx - baseline.value("ear_shoulder_dx"))
    shoulder_center_drop = features.shoulder_center_y - baseline.value("shoulder_center_y")
    return max(
        ramp(ear_forward_delta, 0.025, 0.10),
        face_distance * 0.70,
        ramp(shoulder_center_drop, 0.02, 0.10) * 0.35,
    )


def _shoulder_rounding_score(features: Features, baseline: Baseline) -> float:
    return max(
        _ratio_decrease(features.shoulder_width, baseline.value("shoulder_width"), 0.05, 0.22),
        ramp(abs(features.shoulder_slope - baseline.value("shoulder_slope")), 0.025, 0.09),
    )


def _evidence_supported_total(
    weighted: float,
    components: tuple[float, ...],
    stillness: float,
) -> float:
    strongest = sorted(components, reverse=True)[:2]
    top = strongest[0] if strongest else 0.0
    second = strongest[1] if len(strongest) > 1 else 0.0
    supported = 0.72 * top + 0.18 * second + 0.10 * stillness
    return max(weighted, supported)
