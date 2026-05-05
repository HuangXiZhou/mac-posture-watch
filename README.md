# mac-posture-watch

[![CI](https://github.com/HuangXiZhou/mac-posture-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/HuangXiZhou/mac-posture-watch/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10--3.12-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Privacy](https://img.shields.io/badge/privacy-local--first-0b6)

Local-first macOS CLI posture watcher. It uses the Mac camera, OpenCV, and MediaPipe to monitor sustained forward-head or head-down posture. LLM verification is optional and rate-limited; by default all frame analysis stays local.

## What It Does

- Reads one local camera frame every few seconds.
- Extracts local face and upper-body landmarks with MediaPipe.
- Builds a personal baseline from 30-60 seconds of normal sitting posture.
- Scores posture with a rolling time window instead of per-frame alerts.
- Sends a macOS notification or Bark push only after sustained abnormal posture.
- Optionally calls an OpenAI-compatible vision API only when local CV is already near the notification threshold.

This is a reminder tool, not a medical device or diagnostic system.

## Privacy Model

- Default mode uploads nothing.
- Raw camera frames are processed in memory.
- Baseline data is stored locally under `~/Library/Application Support/posture-watch/`.
- `.env`, local baseline files, logs, images, captures, and debug frames are ignored by Git.
- If `ENABLE_LLM_VERIFY=1`, only compressed JPEGs are sent, and only after local sustained-anomaly conditions pass.

## Install

MediaPipe wheels may lag behind the newest Python release. If install fails on Python 3.13, use Python 3.11 or 3.12.

```bash
git clone https://github.com/HuangXiZhou/mac-posture-watch.git
cd mac-posture-watch

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[vision]"
```

## Setup

Most users only need two commands:

```bash
posture-watch setup
posture-watch start
```

`start` automatically runs camera placement adaptation when no baseline exists. To do config and
camera adaptation in one setup step:

```bash
posture-watch setup --adapt
```

It asks for:

- local-only, local Gemma/Ollama, or cloud OpenAI-compatible verification;
- cool/balanced/sensitive performance profile;
- camera index and calibration time;
- macOS notification and optional Bark endpoint.

After moving your main screen, camera, chair height, or desk distance, run:

```bash
posture-watch adapt
```

For troubleshooting:

```bash
posture-watch doctor --camera
posture-watch doctor --notify
```

## First Run

Grant camera permission when macOS asks. During calibration, look at the screen you normally use
while sitting upright.

```bash
posture-watch setup
posture-watch start
```

`posture-watch start` opens the camera, samples your upright posture if needed, infers the current
screen/camera placement, saves the baseline, and then starts monitoring.

Moving app windows or making small sitting shifts does not need recalibration.

If you prefer source execution without installing the console script:

```bash
PYTHONPATH=src python -m posture_watch start
```

## Optional LLM Verification

LLM verification is off by default. To enable it, edit `.env`:

```dotenv
ENABLE_LLM_VERIFY=1
LLM_API_MODE=chat
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_MODEL=your-vision-model
LLM_MIN_INTERVAL_SEC=600
MAX_LLM_CALLS_PER_HOUR=6
```

Set your real API key only in local `.env`. For local or third-party OpenAI-compatible providers, set `OPENAI_BASE_URL` and `OPENAI_MODEL` accordingly. `LLM_API_MODE=chat` is the most compatible option; `responses` is also supported for OpenAI Responses-style image input.

### Local Gemma Through Ollama

For fully local verification, install Ollama and pull a vision-capable Gemma model:

```bash
ollama pull gemma3:4b
```

Then configure:

```dotenv
ENABLE_LLM_VERIFY=1
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_KEEP_ALIVE=30s
LLM_MIN_INTERVAL_SEC=900
MAX_LLM_CALLS_PER_HOUR=2
LLM_IMAGE_MAX_SIDE=512
LLM_JPEG_QUALITY=62
```

For weaker Macs, keep `ENABLE_LLM_VERIFY=0` first. The local MediaPipe scoring path is much lighter than any local vision LLM.

## Notifications

macOS notifications are enabled by default:

```dotenv
MAC_NOTIFY=1
```

Bark is optional:

```dotenv
BARK_ENDPOINT=
```

Use your own Bark endpoint locally in `.env`; do not commit it.

## Tuning Defaults

The initial defaults bias toward fewer interruptions:

```dotenv
FRAME_INTERVAL_SEC=2
LOCAL_WINDOW_SEC=90
LOCAL_SCORE_TRIGGER=70
LLM_VERIFY_SCORE=75
BAD_RATIO_REQUIRED=0.65
LOCAL_ONLY_NOTIFY_SCORE=82
NOTIFY_COOLDOWN_SEC=900
RECOVERY_SEC=120
```

Lowering `LOCAL_SCORE_TRIGGER` or `BAD_RATIO_REQUIRED` increases recall but may add false
alerts. Raising `LOCAL_ONLY_NOTIFY_SCORE` makes local-only mode more conservative. In setup, the
sensitive profile lowers `LOCAL_ONLY_NOTIFY_SCORE` so local-only mode can notify without an LLM.

## Development

Core tests do not require camera, OpenCV, or MediaPipe:

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests
```

Run runtime checks with vision dependencies:

```bash
python -m pip install -e ".[vision]"
posture-watch doctor --camera
```

Lint:

```bash
python -m pip install -e ".[dev]"
ruff check .
```

Run deterministic scoring evaluation without camera, OpenCV, or MediaPipe:

```bash
posture-watch eval
```

Project docs:

- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Privacy](docs/privacy.md)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
