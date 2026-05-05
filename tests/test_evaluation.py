import unittest

from posture_watch.evaluation import evaluate_synthetic_postures, format_report


class SyntheticEvaluationTest(unittest.TestCase):
    def test_synthetic_precision_recall_hits_target(self) -> None:
        report = evaluate_synthetic_postures()

        self.assertGreaterEqual(report.precision, 0.9)
        self.assertGreaterEqual(report.recall, 0.9)
        self.assertEqual(report.false_positives, 0)
        self.assertEqual(report.false_negatives, 0)

    def test_format_report_is_cli_friendly(self) -> None:
        text = format_report(evaluate_synthetic_postures())

        self.assertIn("precision=", text)
        self.assertIn("recall=", text)
        self.assertIn("front_side/forward-head", text)


if __name__ == "__main__":
    unittest.main()
