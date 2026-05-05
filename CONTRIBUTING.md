# Contributing

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[vision]"
```

For tests that do not need the camera:

```bash
python -m pip install -e ".[dev]"
PYTHONPATH=src python -m unittest discover -s tests
posture-watch eval
ruff check .
```

## Guidelines

- Keep posture decisions baseline-relative.
- Keep synthetic precision/recall green when changing scoring thresholds.
- Keep raw frames in memory unless a user explicitly enables local debug output.
- Do not add default network calls to the detection loop.
- Keep provider secrets in environment variables or local `.env`, never in committed files.
- Add pure unit tests for scoring, state-machine, and parsing changes.

Before opening a pull request, check that `git status --short` contains only intended
source, docs, and GitHub configuration changes.
