from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import median

from .models import Baseline, Features


def build_baseline(samples: list[Features]) -> Baseline:
    if not samples:
        raise ValueError("No calibration samples were collected.")
    keys = samples[0].numeric().keys()
    features = {key: float(median(sample.numeric()[key] for sample in samples)) for key in keys}
    view_type = Counter(sample.view_type for sample in samples).most_common(1)[0][0]
    return Baseline(
        version=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        samples=len(samples),
        view_type=view_type,
        features=features,
    )

