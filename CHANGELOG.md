# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Warn when `OPENAI_BASE_URL` uses plain `http://` with a non-local host so the API
  key is not silently sent in cleartext (setup, runtime, and `doctor`).
- Route warnings and errors to stderr so launchd log split and shell pipelines work
  correctly; `Ctrl+C` now exits cleanly with code 130 instead of a traceback.
- Add capped exponential backoff on repeated frame errors in the watch loop to avoid
  CPU spin and log spam if the camera or detector keeps failing.
- Drop unreachable branches in the COOLDOWN state handler and the rate-limit guard
  in the runtime loop.

## 0.1.0

- Initial local-first posture watcher CLI.
- Local MediaPipe/OpenCV scoring with personal baseline calibration.
- Optional OpenAI-compatible or Ollama vision verification.
- macOS notification, optional Bark push, and LaunchAgent support.
