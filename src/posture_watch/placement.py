from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Baseline
    from .config import Config


def normalize_placement_profile(value: str | None) -> str:
    text = (value or "default").strip().lower()
    chars: list[str] = []
    last_dash = False
    for char in text:
        if char.isalnum() or char == "_":
            chars.append(char)
            last_dash = False
        elif char == "-":
            if not last_dash:
                chars.append(char)
                last_dash = True
        elif not last_dash:
            chars.append("-")
            last_dash = True
    return "".join(chars).strip("-_.") or "default"


def baseline_path_for_placement(data_dir: Path, placement_profile: str) -> Path:
    profile = normalize_placement_profile(placement_profile)
    if profile == "default":
        return data_dir / "baseline.json"
    return data_dir / "baselines" / f"{profile}.json"


def with_placement(config: Config, placement_profile: str) -> Config:
    from dataclasses import replace

    profile = normalize_placement_profile(placement_profile)
    return replace(
        config,
        placement_profile=profile,
        baseline_path=baseline_path_for_placement(config.data_dir, profile),
    )


def infer_placement_profile(baseline: Baseline) -> str:
    view = baseline.view_type
    face_x = baseline.value("face_center_x", 0.5)
    if view == "face_only":
        return "auto-face-only"
    if face_x < 0.42:
        side = "left"
    elif face_x > 0.58:
        side = "right"
    else:
        side = "center"
    if view == "front_side":
        return f"auto-side-{side}"
    if view == "bad":
        return "auto-bad-view"
    return f"auto-front-{side}"


def format_detected_placement(baseline: Baseline, placement_profile: str) -> str:
    return (
        f"Detected placement={placement_profile} "
        f"view={baseline.view_type} "
        f"face_x={baseline.value('face_center_x', 0.0):.2f} "
        f"yaw={baseline.value('yaw_deg', 0.0):.0f}"
    )


def calibration_guidance(config: Config) -> list[str]:
    return [
        f"placement={config.placement_profile} baseline={config.baseline_path}",
        "Look at the screen you normally use while sitting upright.",
        "Keep the camera, screen, chair height, and desk distance in their normal positions.",
        "Use a new --placement name and recalibrate after moving the main screen or camera.",
    ]


def format_placement_guide(config: Config) -> str:
    lines = [
        f"Current placement: {config.placement_profile}",
        f"Baseline: {config.baseline_path}",
        "",
        "Rule: calibrate once per stable camera + screen + chair layout.",
        "Recalibrate after moving the main screen, camera, chair height, or desk distance.",
        "No recalibration is needed for moving app windows or small sitting shifts.",
        "",
        "Useful profiles:",
        "  laptop           Mac screen and camera together",
        "  external-center  external screen, camera near the screen center",
        "  external-left    main screen is left of the Mac camera",
        "  external-right   main screen is right of the Mac camera",
        "  webcam-main      external webcam mounted on the main screen",
        "",
        "Commands:",
        "  posture-watch adapt",
        "  posture-watch start",
    ]
    return "\n".join(lines)
