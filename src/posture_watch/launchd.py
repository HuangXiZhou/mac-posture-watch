from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .config import APP_NAME, Config
from .storage import ensure_private_dir

LABEL = "com.huangxizhou.posture-watch"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def install_launch_agent(config: Config, *, config_path: str | None, start: bool) -> Path:
    path = plist_path()
    ensure_private_dir(path.parent)
    log_dir = Path.home() / "Library" / "Logs" / APP_NAME
    ensure_private_dir(log_dir)

    args = [sys.executable, "-m", "posture_watch", "run"]
    if config_path:
        args.extend(["--config", str(Path(config_path).expanduser())])

    plist = {
        "Label": LABEL,
        "ProgramArguments": args,
        "RunAtLoad": True,
        "KeepAlive": {"Crashed": True},
        "ThrottleInterval": 30,
        "WorkingDirectory": str(Path.cwd()),
        "StandardOutPath": str(log_dir / "launchd.out.log"),
        "StandardErrorPath": str(log_dir / "launchd.err.log"),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
        },
    }
    with path.open("wb") as handle:
        plistlib.dump(plist, handle)

    if start:
        _launchctl(["bootout", f"gui/{os.getuid()}", str(path)], check=False)
        _launchctl(["bootstrap", f"gui/{os.getuid()}", str(path)], check=True)
        _launchctl(["enable", f"gui/{os.getuid()}/{LABEL}"], check=False)
    return path


def uninstall_launch_agent(*, stop: bool) -> Path:
    path = plist_path()
    if stop:
        _launchctl(["bootout", f"gui/{os.getuid()}", str(path)], check=False)
    if path.exists():
        path.unlink()
    return path


def _launchctl(args: list[str], *, check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", *args],
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

