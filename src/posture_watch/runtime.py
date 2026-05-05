from __future__ import annotations

import signal
import time
from dataclasses import replace
from pathlib import Path

from .calibration import build_baseline
from .camera import Camera
from .config import Config
from .detectors import MediaPipeDetector
from .features import MotionEstimator, assess_frame_quality, extract_features
from .llm import OpenAICompatibleVerifier
from .models import Baseline, Features
from .notify import Notifier
from .overlay import draw_overlay, encode_jpeg
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
        print("No baseline found. Starting calibration; sit normally and face your screen.")
        baseline = calibrate(config, overwrite=True, stop_flag=stop_flag)
    else:
        baseline = load_baseline(config.baseline_path)
        print(f"Loaded baseline from {config.baseline_path} ({baseline.samples} samples).")

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
    verifier = OpenAICompatibleVerifier(config)
    notifier = Notifier(config)

    print(
        "Watching posture. "
        f"camera={config.camera_index}, interval={config.frame_interval_sec}s, "
        f"llm={'on' if config.llm_ready else 'off'}."
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
                    result = _verify_with_llm(verifier, frame, detection, score, features)
                    print(
                        f"llm severity={result.severity} confidence={result.confidence:.2f} "
                        f"bad={result.is_bad_posture} reason={result.reason}"
                    )
                    if result.confirmed_bad:
                        notifier.send("坐姿提醒", "检测到持续头前倾或低头，建议调整一下屏幕距离和坐姿。")
                        machine.enter_cooldown(time.time())
                elif quality.ok and not config.llm_ready and machine.should_notify_without_llm(snapshot):
                    notifier.send("坐姿提醒", "本地检测到持续头前倾或低头，建议调整一下坐姿。")
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

    local_stop = stop_flag or StopFlag()
    samples: list[Features] = []
    motion = MotionEstimator()
    deadline = time.time() + config.calibration_sec
    next_print = 0.0

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
                print(f"calibrating... samples={len(samples)} remaining={remaining}s quality={quality.reason}")
                next_print = now + 5
            time.sleep(max(0.1, config.frame_interval_sec))

    if len(samples) < config.min_calibration_samples:
        raise RuntimeError(
            f"Only collected {len(samples)} usable samples; need at least "
            f"{config.min_calibration_samples}. Improve lighting/camera angle and retry."
        )

    baseline = build_baseline(samples)
    save_baseline(config.baseline_path, baseline)
    print(f"Saved baseline to {config.baseline_path} ({baseline.samples} samples).")
    return baseline


def doctor(config: Config, *, camera_check: bool = False) -> int:
    import platform
    import sys

    print(f"Python: {sys.version.split()[0]} ({platform.platform()})")
    print(f"Data dir: {config.data_dir}")
    print(f"Baseline: {config.baseline_path} exists={config.baseline_path.exists()}")
    print(f"LLM enabled={config.enable_llm_verify} ready={config.llm_ready}")
    print(f"Bark configured={bool(config.bark_endpoint)} mac_notify={config.mac_notify}")
    for package in ("cv2", "mediapipe", "numpy", "requests", "dotenv"):
        try:
            __import__(package)
            print(f"{package}: ok")
        except ImportError:
            print(f"{package}: missing")

    if sys.version_info >= (3, 13):
        print("note: if MediaPipe installation fails on Python 3.13, use Python 3.11 or 3.12.")

    if camera_check:
        with Camera(config.camera_index) as camera:
            frame = camera.read()
            print(f"camera: ok frame={frame.shape[1]}x{frame.shape[0]}")
    return 0


def _verify_with_llm(
    verifier: OpenAICompatibleVerifier,
    frame,
    detection,
    score,
    features,
):
    overlay = draw_overlay(
        frame,
        detection,
        score=score.total,
        view_type=features.view_type,
        reasons=score.reasons,
    )
    return verifier.verify(
        frame_jpeg=encode_jpeg(frame),
        overlay_jpeg=encode_jpeg(overlay),
        local_score=score.total,
        view_type=features.view_type,
        score_reasons=score.reasons,
    )

