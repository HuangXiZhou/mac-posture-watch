from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True)
class NotificationResult:
    mac_sent: bool = False
    bark_sent: bool = False


class Notifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def send(self, title: str, body: str) -> NotificationResult:
        mac_sent = False
        bark_sent = False
        if self.config.mac_notify:
            mac_sent = _mac_notify(title, body)
        if self.config.bark_endpoint:
            bark_sent = _bark_notify(self.config.bark_endpoint, title, body)
        return NotificationResult(mac_sent=mac_sent, bark_sent=bark_sent)


def _mac_notify(title: str, body: str) -> bool:
    script = f"display notification {json.dumps(body)} with title {json.dumps(title)}"
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _bark_notify(endpoint: str, title: str, body: str) -> bool:
    import requests

    payload = {"title": title, "body": body}
    try:
        response = requests.post(endpoint, json=payload, timeout=8)
        if 200 <= response.status_code < 300:
            return True
        response = requests.get(endpoint, params=payload, timeout=8)
        return 200 <= response.status_code < 300
    except requests.RequestException:
        return False
