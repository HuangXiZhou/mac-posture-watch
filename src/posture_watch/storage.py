from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import Baseline


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def save_baseline(path: Path, baseline: Baseline) -> None:
    ensure_private_dir(path.parent)
    payload = json.dumps(baseline.to_json(), indent=2, sort_keys=True)
    with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp.write(payload)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_baseline(path: Path) -> Baseline:
    with path.open("r", encoding="utf-8") as handle:
        return Baseline.from_json(json.load(handle))

