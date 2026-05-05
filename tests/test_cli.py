import unittest

from posture_watch.cli import _safe_config
from posture_watch.config import Config


class SafeConfigTest(unittest.TestCase):
    def test_redacts_secret_fields(self) -> None:
        data = _safe_config(
            Config(openai_api_key="secret", bark_endpoint="https://api.day.app/key")
        )
        self.assertEqual(data["openai_api_key"], "***")
        self.assertEqual(data["bark_endpoint"], "***")


if __name__ == "__main__":
    unittest.main()

