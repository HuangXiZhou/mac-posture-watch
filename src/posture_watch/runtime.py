from __future__ import annotations

import signal
import time
from dataclasses import replace

from .calibration import build_baseline
from .camera import Camera
from .config import Config
from .detectors import MediaPipeDetector, mediapipe_legacy_status
from .features import MotionEstimator, assess_frame_quality, extract_features
from .llm import create_verifier
from .models import Baseline, Features
from .notify import Notifier
from .overlay import draw_overlay, encode_jpeg
from .placement import (
    calibration_guidance,
    format_detected_placement,
    infer_placement_profile,
    with_placement,
)
from .scoring import score_posture
from .state import LlmRateLimiter, PostureStateMachine
from .storage import load_baseline, save_baseline


class StopFlag:
    def __init__(self) -> None:
        self.stop = False

    def install(self) -> None:
        def handler(signum, frame) -> None:
            self.stop = True

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)


def run_watcher(config: Config, *, recalibrate: bool = False) -> int:
    stop_flag = StopFlag()
    stop_flag.install()

    if recalibrate or not config.baseline_path.exists():
        print("No baseline found. Starting calibration.")
        baseline = calibrate(config, overwrite=True, stop_flag=stop_flag)
    else:
        baseline = load_baseline(config.baseline_path)
        print(
            f"Loaded baseline placement={config.placement_profile} "
            f"path={config.baseline_path} samples={baseline.samples}."
        )

    machine = PostureStateMachine(
        local_window_sec=config.local_window_sec,
        local_score_trigger=config.local_score_trigger,
        llm_verify_score=config.llm_verify_score,
        bad_ratio_required=config.bad_ratio_required,
        notify_cooldown_sec=config.notify_cooldown_sec,
        recovery_sec=config.recovery_sec,
        local_only_notify_score=config.local_only_notify_score,
    )
    limiter = LlmRateLimiter(config.llm_min_interval_sec, config.max_llm_calls_per_hour)
    verifier = create_verifier(config) if config.llm_ready else None
    notifier = Notifier(config)

    print(
        "Watching posture. "
        f"camera={config.camera_index}, interval={config.frame_interval_sec}s, "
        f"llm={'on' if config.llm_ready else 'off'}, "
        f"notify={_notification_summary(config)}."
    )
    last_status_at = 0.0
    motion = MotionEstimator()

    with Camera(config.camera_index) as camera, MediaPipeDetector() as detector:
        while not stop_flag.stop:
            started = time.time()
            try:
                frame = camera.read()
                detection = detector.detect(frame)
                quality = assess_frame_quality(frame, detection)
                stillness = motion.stillness(frame)
                features = extract_features(detection, quality=quality, stillness=stillness)
                score = score_posture(features, baseline)
                snapshot = machine.update(score.total, quality.ok, time.time())

                if started - last_status_at >= 10:
                    last_status_at = started
                    print(
                        f"state={snapshot.state.value} score={snapshot.latest_score:.0f} "
                        f"bad_ratio={snapshot.bad_ratio:.2f} view={features.view_type} "
                        f"quality={quality.reason}"
                    )

                if quality.ok and config.llm_ready and machine.should_verify_with_llm(
                    snapshot, time.time(), limiter
                ):
                    limiter.record(time.time())
                    if verifier is None:
                        continue
                    result = _verify_with_llm(config, verifier, frame, detection, score, features)
                    print(
                        f"llm severity={result.severity} confidence={result.confidence:.2f} "
                        f"bad={result.is_bad_posture} reason={result.reason}"
                    )
                    if result.confirmed_bad:
                        _send_notification(
                            notifier,
                            "坐姿提醒",
                            "检测到持续头前倾或低头，"
                            "建议调整一下屏幕距离和坐姿。",
                        )
                        machine.enter_cooldown(time.time())
                elif (
                    quality.ok
                    and not config.llm_ready
                    and machine.should_notify_without_llm(snapshot)
                ):
                    _send_notification(
                        notifier,
                        "坐姿提醒",
                        "本地检测到持续头前倾或低头，建议调整一下坐姿。",
                    )
                    machine.enter_cooldown(time.time())
            except Exception as exc:
                print(f"warning: {exc}")

            elapsed = time.time() - started
            time.sleep(max(0.1, config.frame_interval_sec - elapsed))

    print("Stopped.")
    return 0


def calibrate(
    config: Config,
    *,
    overwrite: bool = False,
    stop_flag: StopFlag | None = None,
) -> Baseline:
    if config.baseline_path.exists() and not overwrite:
        raise RuntimeError(f"Baseline already exists: {config.baseline_path}")

    samples = _collect_calibration_samples(config, stop_flag=stop_flag)
    baseline = build_baseline(samples)
    save_baseline(config.baseline_path, baseline)
    print(f"Saved baseline to {config.baseline_path} ({baseline.samples} samples).")
    return baseline


def adapt_placement(
    config: Config,
    *,
    infer_profile: bool = True,
    stop_flag: StopFlag | None = None,
) -> tuple[Config, Baseline]:
    samples = _collect_calibration_samples(config, stop_flag=stop_flag)
    baseline = build_baseline(samples)
    adapted_config = (
        with_placement(config, infer_placement_profile(baseline)) if infer_profile else config
    )
    save_baseline(adapted_config.baseline_path, baseline)
    print(format_detected_placement(baseline, adapted_config.placement_profile))
    print(f"Saved baseline to {adapted_config.baseline_path} ({baseline.samples} samples).")
    return adapted_config, baseline


def _collect_calibration_samples(
    config: Config,
    *,
    stop_flag: StopFlag | None = None,
) -> list[Features]:
    local_stop = stop_flag or StopFlag()
    samples: list[Features] = []
    motion = MotionEstimator()
    deadline = time.time() + config.calibration_sec
    next_print = 0.0
    print("Calibration guide:")
    for line in calibration_guidance(config):
        print(f"  - {line}")

    with Camera(config.camera_index) as camera, MediaPipeDetector() as detector:
        while time.time() < deadline and not local_stop.stop:
            frame = camera.read()
            detection = detector.detect(frame)
            quality = assess_frame_quality(frame, detection)
            stillness = motion.stillness(frame)
            features = extract_features(detection, quality=quality, stillness=stillness)
            if quality.ok and features.view_type != "bad":
                samples.append(replace(features, stillness=1.0))
            now = time.time()
            if now >= next_print:
                remaining = max(0, int(deadline - now))
                print(
                    f"calibrating... samples={len(samples)} "
                    f"remaining={remaining}s quality={quality.reason}"
                )
                next_print = now + 5
            time.sleep(max(0.1, config.frame_interval_sec))

    if len(samples) < config.min_calibration_samples:
        raise RuntimeError(
            f"Only collected {len(samples)} usable samples; need at least "
            f"{config.min_calibration_samples}. Improve lighting/camera angle and retry."
        )
    return samples


def doctor(config: Config, *, camera_check: bool = False, notify_check: bool = False) -> int:
    import platform
    import sys

    print(f"Python: {sys.version.split()[0]} ({platform.platform()})")
    print(f"Data dir: {config.data_dir}")
    print(f"Placement: {config.placement_profile}")
    print(f"Baseline: {config.baseline_path} exists={config.baseline_path.exists()}")
    print(
        f"LLM enabled={config.enable_llm_verify} ready={config.llm_ready} "
        f"provider={config.llm_provider}"
    )
    print(f"Bark configured={bool(config.bark_endpoint)} mac_notify={config.mac_notify}")
    for package in ("cv2", "numpy", "requests", "dotenv"):
        try:
            __import__(package)
            print(f"{package}: ok")
        except ImportError:
            print(f"{package}: missing")
    mediapipe_ok, mediapipe_message = mediapipe_legacy_status()
    print(f"mediapipe: {'ok' if mediapipe_ok else 'failed'} ({mediapipe_message})")

    if sys.version_info >= (3, 13):
        print("note: if MediaPipe installation fails on Python 3.13, use Python 3.11 or 3.12.")

    exit_code = 0
    if camera_check:
        try:
            with Camera(config.camera_index) as camera:
                frame = camera.read()
                print(f"camera: ok frame={frame.shape[1]}x{frame.shape[0]}")
        except RuntimeError as exc:
            print(f"camera: failed {exc}")
            exit_code = 1

    if notify_check:
        result = Notifier(config).send(
            "Posture Watch test",
            "If this appears, macOS notifications are working.",
        )
        print(f"notification: {_notification_result_summary(config, result)}")
        if (config.mac_notify and not result.mac_sent) or (
            bool(config.bark_endpoint) and not result.bark_sent
        ):
            exit_code = 1
        if config.mac_notify and result.mac_sent:
            print(
                "If no banner appeared, check System Settings > Notifications for "
                "Terminal, your shell app, or Script Editor, and check Focus mode."
            )
    return exit_code


def _verify_with_llm(
    config: Config,
    verifier,
    frame,
    detection,
    score,
    features,
):
    overlay = None
    if config.llm_send_overlay:
        overlay = draw_overlay(
            frame,
            detection,
            score=score.total,
            view_type=features.view_type,
            reasons=score.reasons,
        )
    return verifier.verify(
        frame_jpeg=encode_jpeg(
            frame,
            max_side=config.llm_image_max_side,
            quality=config.llm_jpeg_quality,
        ),
        overlay_jpeg=(
            encode_jpeg(
                overlay,
                max_side=config.llm_image_max_side,
                quality=config.llm_jpeg_quality,
            )
            if overlay is not None
            else None
        ),
        local_score=score.total,
        view_type=features.view_type,
        score_reasons=score.reasons,
    )


def _notification_summary(config: Config) -> str:
    destinations: list[str] = []
    if config.mac_notify:
        destinations.append("mac")
    if config.bark_endpoint:
        destinations.append("bark")
    destination_text = "+".join(destinations) if destinations else "off"
    if not config.llm_ready:
        return f"{destination_text}, local_score>={config.local_only_notify_score:.0f}"
    return destination_text


def _send_notification(notifier: Notifier, title: str, body: str) -> None:
    result = notifier.send(title, body)
    print(f"notification: {_notification_result_summary(notifier.config, result)}")


def _notification_result_summary(config: Config, result) -> str:
    parts: list[str] = []
    if config.mac_notify:
        parts.append(f"mac={'sent' if result.mac_sent else 'failed'}")
    if config.bark_endpoint:
        parts.append(f"bark={'sent' if result.bark_sent else 'failed'}")
    return " ".join(parts) if parts else "disabled"
