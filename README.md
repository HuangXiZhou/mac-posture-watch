# mac-posture-watch

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
- If `ENABLE_LLM_VERIFY=1`, only compressed JPEGs with longest side up to 640 px are sent, and only after local sustained-anomaly conditions pass.

## Install

MediaPipe wheels may lag behind the newest Python release. If install fails on Python 3.13, use Python 3.11 or 3.12.

```bash
git clone https://github.com/HuangXiZhou/mac-posture-watch.git
cd mac-posture-watch

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[vision]"
cp .env.example .env
```

## First Run

Grant camera permission when macOS asks. Keep your normal sitting posture during calibration.

```bash
posture-watch doctor --camera-check
posture-watch calibrate --force
posture-watch run
```

If you prefer source execution without installing the console script:

```bash
PYTHONPATH=src python -m posture_watch run
```

## Optional LLM Verification

LLM verification is off by default. To enable it, edit `.env`:

```dotenv
ENABLE_LLM_VERIFY=1
LLM_API_MODE=chat
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your-vision-model
LLM_MIN_INTERVAL_SEC=600
MAX_LLM_CALLS_PER_HOUR=6
```

For local or third-party OpenAI-compatible providers, set `OPENAI_BASE_URL` and `OPENAI_MODEL` accordingly. `LLM_API_MODE=chat` is the most compatible option; `responses` is also supported for OpenAI Responses-style image input.

## Notifications

macOS notifications are enabled by default:

```dotenv
MAC_NOTIFY=1
```

Bark is optional:

```dotenv
BARK_ENDPOINT=https://api.day.app/your_key
```

## Autostart

Install a user LaunchAgent after you have verified interactive camera access:

```bash
posture-watch install-launch-agent --start --config "$(pwd)/.env"
```

Remove it:

```bash
posture-watch uninstall-launch-agent --stop
```

Logs are written to `~/Library/Logs/posture-watch/`.

## Tuning Defaults

The initial defaults bias toward fewer interruptions:

```dotenv
FRAME_INTERVAL_SEC=2
LOCAL_WINDOW_SEC=90
LOCAL_SCORE_TRIGGER=70
LLM_VERIFY_SCORE=75
BAD_RATIO_REQUIRED=0.65
NOTIFY_COOLDOWN_SEC=900
RECOVERY_SEC=120
```

Lowering `LOCAL_SCORE_TRIGGER` or `BAD_RATIO_REQUIRED` increases recall but may add false alerts. Raising `LOCAL_ONLY_NOTIFY_SCORE` makes local-only mode more conservative.

## Development

Core tests do not require camera, OpenCV, or MediaPipe:

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests
```

Run runtime checks with vision dependencies:

```bash
python -m pip install -e ".[vision]"
posture-watch doctor --camera-check
```
