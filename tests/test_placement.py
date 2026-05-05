import unittest

from posture_watch.models import Baseline
from posture_watch.placement import infer_placement_profile, normalize_placement_profile


class PlacementTest(unittest.TestCase):
    def test_normalizes_profile_names_for_paths(self) -> None:
        self.assertEqual(normalize_placement_profile("External Center"), "external-center")
        self.assertEqual(normalize_placement_profile("../desk/main"), "desk-main")

    def test_infers_centered_front_profile(self) -> None:
        baseline = Baseline(
            version=1,
            created_at="",
            samples=12,
            view_type="front",
            features={"face_center_x": 0.5},
        )

        self.assertEqual(infer_placement_profile(baseline), "auto-front-center")

    def test_infers_side_profile_from_face_position(self) -> None:
        baseline = Baseline(
            version=1,
            created_at="",
            samples=12,
            view_type="front_side",
            features={"face_center_x": 0.33},
        )

        self.assertEqual(infer_placement_profile(baseline), "auto-side-left")


if __name__ == "__main__":
    unittest.main()
