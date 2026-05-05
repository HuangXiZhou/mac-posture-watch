from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs) -> bool:  # type: ignore[no-redef]
        return False

APP_NAME = "posture-watch"


def default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class Config:
    camera_index: int = 0
    frame_interval_sec: float = 2.0
    calibration_sec: int = 45
    min_calibration_samples: int = 12

    local_window_sec: int = 90
    local_score_trigger: float = 70.0
    llm_verify_score: float = 75.0
    bad_ratio_required: float = 0.65
    local_only_notify_score: float = 84.0

    enable_llm_verify: bool = False
    llm_provider: str = "openai_compatible"
    llm_api_mode: str = "chat"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:4b"
    ollama_keep_alive: str = "30s"
    llm_min_interval_sec: int = 600
    max_llm_calls_per_hour: int = 6
    llm_timeout_sec: int = 30
    llm_json_mode: bool = True
    llm_image_max_side: int = 512
    llm_jpeg_quality: int = 62
    llm_send_overlay: bool = True

    bark_endpoint: str = ""
    mac_notify: bool = True
    notify_cooldown_sec: int = 900
    recovery_sec: int = 120

    data_dir: Path = default_data_dir()
    baseline_path: Path = default_data_dir() / "baseline.json"
    debug_save_frames: bool = False

    @property
    def llm_ready(self) -> bool:
        if not self.enable_llm_verify:
            return False
        provider = self.llm_provider.lower()
        if provider in {"ollama", "local", "gemma"}:
            return bool(self.ollama_base_url and self.ollama_model)
        return bool(self.openai_api_key and self.openai_model)


def load_config(config_path: str | Path | None = None) -> Config:
    if config_path:
        load_dotenv(Path(config_path), override=True)
    else:
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            load_dotenv(cwd_env, override=True)

    data_dir = Path(os.getenv("DATA_DIR") or default_data_dir()).expanduser()
    baseline_path = Path(os.getenv("BASELINE_PATH") or data_dir / "baseline.json").expanduser()

    return Config(
        camera_index=_int(os.getenv("CAMERA_INDEX"), 0),
        frame_interval_sec=_float(os.getenv("FRAME_INTERVAL_SEC"), 2.0),
        calibration_sec=_int(os.getenv("CALIBRATION_SEC"), 45),
        min_calibration_samples=_int(os.getenv("MIN_CALIBRATION_SAMPLES"), 12),
        local_window_sec=_int(os.getenv("LOCAL_WINDOW_SEC"), 90),
        local_score_trigger=_float(os.getenv("LOCAL_SCORE_TRIGGER"), 70.0),
        llm_verify_score=_float(os.getenv("LLM_VERIFY_SCORE"), 75.0),
        bad_ratio_required=_float(os.getenv("BAD_RATIO_REQUIRED"), 0.65),
        local_only_notify_score=_float(os.getenv("LOCAL_ONLY_NOTIFY_SCORE"), 84.0),
        enable_llm_verify=_bool(os.getenv("ENABLE_LLM_VERIFY"), False),
        llm_provider=os.getenv("LLM_PROVIDER") or "openai_compatible",
        llm_api_mode=(os.getenv("LLM_API_MODE") or "chat").lower(),
        openai_base_url=(os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or "",
        openai_model=os.getenv("OPENAI_MODEL") or "",
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL") or "gemma3:4b",
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE") or "30s",
        llm_min_interval_sec=_int(os.getenv("LLM_MIN_INTERVAL_SEC"), 600),
        max_llm_calls_per_hour=_int(os.getenv("MAX_LLM_CALLS_PER_HOUR"), 6),
        llm_timeout_sec=_int(os.getenv("LLM_TIMEOUT_SEC"), 30),
        llm_json_mode=_bool(os.getenv("LLM_JSON_MODE"), True),
        llm_image_max_side=_int(os.getenv("LLM_IMAGE_MAX_SIDE"), 512),
        llm_jpeg_quality=_int(os.getenv("LLM_JPEG_QUALITY"), 62),
        llm_send_overlay=_bool(os.getenv("LLM_SEND_OVERLAY"), True),
        bark_endpoint=os.getenv("BARK_ENDPOINT") or "",
        mac_notify=_bool(os.getenv("MAC_NOTIFY"), True),
        notify_cooldown_sec=_int(os.getenv("NOTIFY_COOLDOWN_SEC"), 900),
        recovery_sec=_int(os.getenv("RECOVERY_SEC"), 120),
        data_dir=data_dir,
        baseline_path=baseline_path,
        debug_save_frames=_bool(os.getenv("DEBUG_SAVE_FRAMES"), False),
    )
