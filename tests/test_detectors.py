import unittest
from types import SimpleNamespace

from posture_watch.detectors import _landmark


class LandmarkConversionTest(unittest.TestCase):
    def test_none_optional_fields_use_defaults(self) -> None:
        lm = SimpleNamespace(x=0.1, y=0.2, z=None, visibility=None, presence=None)

        converted = _landmark(lm)

        self.assertEqual(converted.z, 0.0)
        self.assertEqual(converted.visibility, 1.0)
        self.assertEqual(converted.presence, 1.0)

    def test_existing_optional_fields_are_converted_to_float(self) -> None:
        lm = SimpleNamespace(x=0.1, y=0.2, z="0.3", visibility="0.4", presence="0.5")

        converted = _landmark(lm)

        self.assertEqual(converted.z, 0.3)
        self.assertEqual(converted.visibility, 0.4)
        self.assertEqual(converted.presence, 0.5)


if __name__ == "__main__":
    unittest.main()
