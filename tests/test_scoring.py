import unittest

from posture_watch.models import Baseline, Features
from posture_watch.scoring import score_posture


def baseline() -> Baseline:
    return Baseline(
        version=1,
        created_at="2026-01-01T00:00:00Z",
        samples=30,
        view_type="front_side",
        features={
            "pitch_deg": 0.0,
            "yaw_deg": 0.0,
            "roll_deg": 0.0,
            "face_size": 0.05,
            "face_center_x": 0.5,
            "face_center_y": 0.35,
            "shoulder_width": 0.35,
            "shoulder_center_x": 0.5,
            "shoulder_center_y": 0.62,
            "nose_shoulder_dy": -0.25,
            "ear_shoulder_dx": 0.02,
            "shoulder_slope": 0.0,
            "stillness": 1.0,
        },
    )


class ScorePostureTest(unittest.TestCase):
    def test_front_side_forward_head_scores_high(self) -> None:
        features = Features(
            timestamp=0,
            view_type="front_side",
            pitch_deg=20.0,
            face_size=0.08,
            face_center_x=0.5,
            face_center_y=0.43,
            shoulder_width=0.32,
            shoulder_center_x=0.5,
            shoulder_center_y=0.64,
            nose_shoulder_dy=-0.16,
            ear_shoulder_dx=0.13,
            shoulder_slope=0.01,
            stillness=1.0,
        )
        score = score_posture(features, baseline())
        self.assertGreaterEqual(score.total, 75)
        self.assertIn("forward_head", score.reasons)

    def test_face_only_is_capped(self) -> None:
        features = Features(
            timestamp=0,
            view_type="face_only",
            pitch_deg=35.0,
            face_size=0.12,
            face_center_y=0.48,
            stillness=1.0,
        )
        score = score_posture(features, baseline())
        self.assertLessEqual(score.total, 68)
        self.assertIn("face_only_cap", score.reasons)

    def test_bad_view_scores_zero(self) -> None:
        score = score_posture(Features(timestamp=0, view_type="bad"), baseline())
        self.assertEqual(score.total, 0)


if __name__ == "__main__":
    unittest.main()

