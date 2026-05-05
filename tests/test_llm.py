import unittest

from posture_watch.llm import parse_verification_text


class ParseVerificationTextTest(unittest.TestCase):
    def test_parses_plain_json(self) -> None:
        result = parse_verification_text(
            '{"is_bad_posture": true, "severity": "moderate", '
            '"confidence": 0.82, "visible_evidence": ["低头"], "reason": "持续低头"}'
        )
        self.assertTrue(result.confirmed_bad)
        self.assertEqual(result.visible_evidence, ("低头",))

    def test_uncertain_is_not_confirmed(self) -> None:
        result = parse_verification_text(
            "```json\n"
            '{"is_bad_posture": false, "severity": "unknown", "confidence": 0.45}'
            "\n```"
        )
        self.assertFalse(result.confirmed_bad)

    def test_invalid_json_fails_closed(self) -> None:
        result = parse_verification_text("not json")
        self.assertFalse(result.confirmed_bad)
        self.assertEqual(result.severity, "unknown")


if __name__ == "__main__":
    unittest.main()

