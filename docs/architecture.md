# Architecture

## Data Flow

```text
Mac camera
  -> OpenCV frame read
  -> MediaPipe Pose + Face Mesh landmarks
  -> local feature extraction
  -> baseline-relative posture scoring
  -> rolling-window state machine
  -> optional low-frequency LLM verification
  -> macOS notification / Bark
```

## Local Judgment First

The runtime does not ask an LLM to classify every frame. It first checks:

- frame quality: brightness, blur, face visibility, shoulder visibility;
- camera view: front, front-side, face-only, or bad view;
- head pose: relative pitch/yaw/roll from the personal baseline;
- face distance: face bounding box area relative to baseline;
- shoulder and neck relation: shoulder width, shoulder slope, nose-to-shoulder, ear-to-shoulder;
- stillness: downscaled frame-difference signal to avoid alerting on movement.

The score is continuous from `0` to `100`. Bad or low-quality frames do not count toward the abnormal window.

## Baseline

Calibration stores median feature values from normal sitting posture. Runtime scoring compares current values with this personal baseline instead of fixed global thresholds. This makes different Mac camera positions more tolerable.

Baseline data is local JSON and may reveal approximate face/shoulder geometry, so it is stored outside the repository by default.

## State Machine

The watcher uses a rolling window rather than one-frame decisions:

```text
NORMAL
  -> WATCHING when the rolling local score is persistently suspicious
  -> VERIFYING when score and bad-ratio pass the LLM/local-notify threshold
  -> COOLDOWN after notification
  -> NORMAL only after cooldown plus sustained recovery
```

Default behavior:

- sample every 2 seconds;
- evaluate a 90-second window;
- require 65% bad frames in that window;
- require 15 minutes cooldown after notification;
- require 2 minutes recovery before the next alert cycle.

## LLM Verification

When enabled and configured, the LLM verifier sends:

- one compressed current JPEG;
- one compressed overlay JPEG with local landmarks and score text.

The verifier is rate-limited by minimum interval and hourly call count. If the provider returns invalid JSON, low confidence, `mild`, or `unknown`, notification is suppressed.

