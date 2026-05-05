# Evaluation

`mac-posture-watch` should avoid one-frame posture judgments. Accuracy work starts with
repeatable scoring tests, then moves to camera sessions on real hardware.

## Synthetic Precision/Recall

Run the built-in deterministic evaluation without camera dependencies:

```bash
posture-watch eval
```

The synthetic suite covers:

- normal front view;
- normal low laptop angle;
- normal front-side yaw;
- normal minor distance changes;
- normal face-only crop;
- severe low head;
- severe close-to-screen posture;
- severe front-side forward head;
- severe rounded shoulders;
- severe face-only low-and-close posture.

The default target is precision `>= 0.90` and recall `>= 0.90` at score threshold `70`.
The command exits non-zero if the target is missed, so it is safe to run in CI.

## Manual Camera Protocol

Use Python 3.11 or 3.12 for camera validation because MediaPipe wheels can lag behind
new Python releases.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[vision]"
posture-watch doctor --camera
posture-watch start
```

Validate these Mac placements after calibration:

- screen roughly eye-level and centered;
- laptop lower on desk, camera looking upward;
- laptop slightly left or right, producing a front-side view;
- close crop where shoulders sometimes disappear.

For each placement, spend at least two rolling windows in normal posture and two rolling
windows in intentionally bad posture. A good run has no alerts during normal posture,
detects sustained severe posture, and recovers after cooldown plus recovery time.

## Research Notes

The implementation intentionally uses established local vision primitives:

- MediaPipe Pose landmarks for shoulder, ear, nose, and torso geometry:
  https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
- MediaPipe Face Mesh landmarks for face box and head-pose points:
  https://mediapipe.readthedocs.io/en/latest/solutions/face_mesh.html
- OpenCV `solvePnP` for model-to-image head pose:
  https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html

The practical constraint from OpenCV's PnP documentation is that pose estimates depend
on camera intrinsics and landmark quality. This project therefore treats head pose as
one signal among several baseline-relative signals instead of making it the only trigger.
