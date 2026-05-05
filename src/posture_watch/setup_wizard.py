from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path
from typing import Callable

from .storage import ensure_private_dir

InputFunc = Callable[[str], str]
PrintFunc = Callable[[str], None]
SecretFunc = Callable[[str], str]


def default_config_path() -> Path:
    return Path.cwd() / ".env"


def run_setup_wizard(
    *,
    output_path: str | Path | None = None,
    input_func: InputFunc = input,
    secret_func: SecretFunc = getpass.getpass,
    print_func: PrintFunc = print,
) -> Path:
    path = Path(output_path or default_config_path()).expanduser()
    print_func("Posture Watch setup")
    print_func("Press Enter to accept defaults. You can edit the generated .env later.")

    _section(print_func, "Verification")
    mode = _choice(
        input_func,
        print_func,
        "Verification mode",
        {
            "1": ("local", "Local CV only, lowest CPU and no network"),
            "2": ("ollama", "Local Gemma via Ollama, private but heavier"),
            "3": ("openai_compatible", "Cloud/OpenAI-compatible vision API"),
        },
        default="1",
    )

    _section(print_func, "Performance")
    profile = _choice(
        input_func,
        print_func,
        "Performance profile",
        {
            "1": ("cool", "Cool and quiet for weaker Macs"),
            "2": ("balanced", "Balanced accuracy and load"),
            "3": ("sensitive", "More sensitive, higher resource use"),
        },
        default="1",
    )

    values = _profile_values(profile)
    _section(print_func, "Camera")
    camera_index = _ask_int(input_func, print_func, "Camera index", 0, minimum=0)
    calibration_sec = _ask_int(
        input_func,
        print_func,
        "Calibration seconds",
        45,
        minimum=15,
        maximum=180,
    )

    _section(print_func, "Notifications")
    mac_notify = _yes_no(input_func, print_func, "Enable macOS notifications", True)
    bark_endpoint = _ask(input_func, "Bark endpoint, optional", "")

    values.update(
        {
            "PLACEMENT_PROFILE": "default",
            "CAMERA_INDEX": str(camera_index),
            "CALIBRATION_SEC": str(calibration_sec),
            "ENABLE_LLM_VERIFY": "0" if mode == "local" else "1",
            "LLM_PROVIDER": "openai_compatible" if mode == "openai_compatible" else mode,
            "MAC_NOTIFY": "1" if mac_notify else "0",
            "BARK_ENDPOINT": bark_endpoint,
            "DATA_DIR": "",
            "BASELINE_PATH": "",
            "DEBUG_SAVE_FRAMES": "0",
        }
    )

    if mode == "ollama":
        _section(print_func, "Ollama")
        values.update(
            {
                "OLLAMA_BASE_URL": _ask(input_func, "Ollama URL", "http://127.0.0.1:11434"),
                "OLLAMA_MODEL": _ask(input_func, "Ollama vision model", "gemma3:4b"),
                "OLLAMA_KEEP_ALIVE": _ask(input_func, "Ollama keep_alive", "30s"),
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
                "OPENAI_API_KEY": "",
                "OPENAI_MODEL": "",
                "LLM_API_MODE": "chat",
            }
        )
    elif mode == "openai_compatible":
        _section(print_func, "OpenAI-compatible")
        values.update(
            {
                "OPENAI_BASE_URL": _ask(
                    input_func,
                    "OpenAI-compatible base URL",
                    "https://api.openai.com/v1",
                ),
                "OPENAI_MODEL": _ask(input_func, "Vision model name", ""),
                "OPENAI_API_KEY": secret_func("API key (input hidden, optional now): ").strip(),
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_MODEL": "gemma3:4b",
                "OLLAMA_KEEP_ALIVE": "30s",
                "LLM_API_MODE": _choice(
                    input_func,
                    print_func,
                    "API mode",
                    {
                        "1": ("chat", "Chat Completions compatible"),
                        "2": ("responses", "OpenAI Responses API"),
                    },
                    default="1",
                ),
            }
        )
    else:
        values.update(
            {
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
                "OPENAI_API_KEY": "",
                "OPENAI_MODEL": "",
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_MODEL": "gemma3:4b",
                "OLLAMA_KEEP_ALIVE": "30s",
                "LLM_API_MODE": "chat",
            }
        )

    _write_env(path, values)
    print_func(f"Wrote {path}")
    _print_summary(print_func, path, mode, profile, values)
    print_func("Next:")
    print_func(f"  posture-watch start --config {path}")
    print_func(f"  posture-watch adapt --config {path}  # after moving screen/camera")
    return path


def edit_config(path: str | Path | None = None) -> int:
    config_path = Path(path or default_config_path()).expanduser()
    if not config_path.exists():
        _write_env(config_path, _default_local_values())
    editor = os.environ.get("EDITOR") or "nano"
    return subprocess.run([editor, str(config_path)], check=False).returncode


def update_config_values(path: str | Path | None, values: dict[str, str]) -> Path:
    config_path = Path(path or default_config_path()).expanduser()
    if not config_path.exists():
        _write_env(config_path, _default_local_values())

    lines = config_path.read_text(encoding="utf-8").splitlines()
    remaining = dict(values)
    updated: list[str] = []
    for line in lines:
        stripped = line.strip()
        if "=" in line and not stripped.startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                updated.append(f"{key}={remaining.pop(key)}")
                continue
        updated.append(line)

    if remaining:
        if updated and updated[-1]:
            updated.append("")
        updated.append("# Updated by posture-watch adapt.")
        for key, value in remaining.items():
            updated.append(f"{key}={value}")

    _write_text_private(config_path, "\n".join(updated) + "\n")
    return config_path


def _default_local_values() -> dict[str, str]:
    values = _profile_values("cool")
    values.update(
        {
            "PLACEMENT_PROFILE": "default",
            "CAMERA_INDEX": "0",
            "CALIBRATION_SEC": "45",
            "ENABLE_LLM_VERIFY": "0",
            "LLM_PROVIDER": "local",
            "LLM_API_MODE": "chat",
            "OPENAI_BASE_URL": "https://api.openai.com/v1",
            "OPENAI_API_KEY": "",
            "OPENAI_MODEL": "",
            "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "OLLAMA_MODEL": "gemma3:4b",
            "OLLAMA_KEEP_ALIVE": "30s",
            "BARK_ENDPOINT": "",
            "MAC_NOTIFY": "1",
            "DATA_DIR": "",
            "BASELINE_PATH": "",
            "DEBUG_SAVE_FRAMES": "0",
        }
    )
    return values


def _profile_values(profile: str) -> dict[str, str]:
    common = {
        "MIN_CALIBRATION_SAMPLES": "12",
        "LOCAL_SCORE_TRIGGER": "70",
        "LLM_VERIFY_SCORE": "75",
        "LLM_JSON_MODE": "1",
        "LLM_SEND_OVERLAY": "1",
        "NOTIFY_COOLDOWN_SEC": "900",
        "RECOVERY_SEC": "120",
    }
    if profile == "sensitive":
        common.update(
            {
                "FRAME_INTERVAL_SEC": "2",
                "LOCAL_WINDOW_SEC": "90",
                "BAD_RATIO_REQUIRED": "0.62",
                "LLM_MIN_INTERVAL_SEC": "600",
                "MAX_LLM_CALLS_PER_HOUR": "6",
                "LLM_TIMEOUT_SEC": "30",
                "LLM_IMAGE_MAX_SIDE": "640",
                "LLM_JPEG_QUALITY": "65",
                "LOCAL_ONLY_NOTIFY_SCORE": "75",
            }
        )
    elif profile == "balanced":
        common.update(
            {
                "FRAME_INTERVAL_SEC": "2.5",
                "LOCAL_WINDOW_SEC": "100",
                "BAD_RATIO_REQUIRED": "0.65",
                "LLM_MIN_INTERVAL_SEC": "900",
                "MAX_LLM_CALLS_PER_HOUR": "4",
                "LLM_TIMEOUT_SEC": "25",
                "LLM_IMAGE_MAX_SIDE": "512",
                "LLM_JPEG_QUALITY": "62",
                "LOCAL_ONLY_NOTIFY_SCORE": "78",
            }
        )
    else:
        common.update(
            {
                "FRAME_INTERVAL_SEC": "3",
                "LOCAL_WINDOW_SEC": "120",
                "BAD_RATIO_REQUIRED": "0.70",
                "LLM_MIN_INTERVAL_SEC": "1200",
                "MAX_LLM_CALLS_PER_HOUR": "2",
                "LLM_TIMEOUT_SEC": "20",
                "LLM_IMAGE_MAX_SIDE": "448",
                "LLM_JPEG_QUALITY": "58",
                "LOCAL_ONLY_NOTIFY_SCORE": "82",
            }
        )
    return common


def _write_env(path: Path, values: dict[str, str]) -> None:
    ensure_private_dir(path.parent)
    lines = [
        "# Generated by posture-watch setup. This file is ignored by Git.",
        "# Re-run `posture-watch setup` to change it.",
    ]
    sections = [
        ("Placement", ["PLACEMENT_PROFILE"]),
        ("Camera", ["CAMERA_INDEX", "FRAME_INTERVAL_SEC"]),
        ("Calibration", ["CALIBRATION_SEC", "MIN_CALIBRATION_SAMPLES"]),
        (
            "Local scoring",
            [
                "LOCAL_WINDOW_SEC",
                "LOCAL_SCORE_TRIGGER",
                "LLM_VERIFY_SCORE",
                "BAD_RATIO_REQUIRED",
                "LOCAL_ONLY_NOTIFY_SCORE",
            ],
        ),
        (
            "LLM verification",
            [
                "ENABLE_LLM_VERIFY",
                "LLM_PROVIDER",
                "LLM_API_MODE",
                "LLM_MIN_INTERVAL_SEC",
                "MAX_LLM_CALLS_PER_HOUR",
                "LLM_TIMEOUT_SEC",
                "LLM_JSON_MODE",
                "LLM_IMAGE_MAX_SIDE",
                "LLM_JPEG_QUALITY",
                "LLM_SEND_OVERLAY",
            ],
        ),
        ("OpenAI-compatible provider", ["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"]),
        ("Ollama provider", ["OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_KEEP_ALIVE"]),
        ("Notification", ["BARK_ENDPOINT", "MAC_NOTIFY", "NOTIFY_COOLDOWN_SEC", "RECOVERY_SEC"]),
        ("Runtime paths", ["DATA_DIR", "BASELINE_PATH"]),
        ("Debug", ["DEBUG_SAVE_FRAMES"]),
    ]
    written: set[str] = set()
    for title, keys in sections:
        present = [key for key in keys if key in values]
        if not present:
            continue
        lines.extend(["", f"# {title}"])
        for key in present:
            lines.append(f"{key}={values[key]}")
            written.add(key)
    extra = sorted(key for key in values if key not in written)
    if extra:
        lines.extend(["", "# Extra"])
        for key in extra:
            lines.append(f"{key}={values[key]}")
    _write_text_private(path, "\n".join(lines) + "\n")


def _write_text_private(path: Path, text: str) -> None:
    ensure_private_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _section(print_func: PrintFunc, title: str) -> None:
    print_func("")
    print_func(f"{title}:")


def _ask(input_func: InputFunc, prompt: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    answer = input_func(f"{prompt}{suffix}: ").strip()
    return answer or default


def _ask_int(
    input_func: InputFunc,
    print_func: PrintFunc,
    prompt: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    while True:
        answer = input_func(f"{prompt} [{default}]: ").strip()
        if not answer:
            return default
        try:
            value = int(answer)
        except ValueError:
            print_func("Enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print_func(f"Enter a number >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print_func(f"Enter a number <= {maximum}.")
            continue
        return value


def _yes_no(
    input_func: InputFunc,
    print_func: PrintFunc,
    prompt: str,
    default: bool,
) -> bool:
    marker = "Y/n" if default else "y/N"
    while True:
        answer = input_func(f"{prompt} [{marker}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes", "1", "true", "on"}:
            return True
        if answer in {"n", "no", "0", "false", "off"}:
            return False
        print_func("Enter y or n.")


def _choice(
    input_func: InputFunc,
    print_func: PrintFunc,
    prompt: str,
    options: dict[str, tuple[str, str]],
    *,
    default: str,
) -> str:
    print_func(prompt + ":")
    for key, (value, label) in options.items():
        marker = " (default)" if key == default else ""
        print_func(f"  {key}. {label}{marker}")
    while True:
        answer = input_func(f"Select {prompt.lower()} [{default}]: ").strip() or default
        if answer in options:
            return options[answer][0]
        for value, _ in options.values():
            if answer.lower() == value.lower():
                return value
        print_func(f"Enter one of: {', '.join(options)}.")


def _print_summary(
    print_func: PrintFunc,
    path: Path,
    mode: str,
    profile: str,
    values: dict[str, str],
) -> None:
    print_func("")
    print_func("Summary:")
    print_func(f"  config: {path}")
    print_func(f"  verification: {mode}")
    print_func(f"  performance: {profile}")
    print_func(
        "  camera: "
        f"index={values['CAMERA_INDEX']} calibration={values['CALIBRATION_SEC']}s "
        f"interval={values['FRAME_INTERVAL_SEC']}s"
    )
    print_func(
        "  notifications: "
        f"mac={'on' if values['MAC_NOTIFY'] == '1' else 'off'} "
        f"bark={'on' if values['BARK_ENDPOINT'] else 'off'} "
        f"local_score>={values['LOCAL_ONLY_NOTIFY_SCORE']}"
    )
