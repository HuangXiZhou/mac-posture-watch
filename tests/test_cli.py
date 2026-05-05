import unittest

from posture_watch.cli import main
from posture_watch.cli import _safe_config
from posture_watch.config import Config


class SafeConfigTest(unittest.TestCase):
    def test_redacts_secret_fields(self) -> None:
        data = _safe_config(
            Config(openai_api_key="secret", bark_endpoint="https://api.day.app/key")
        )
        self.assertEqual(data["openai_api_key"], "***")
        self.assertEqual(data["bark_endpoint"], "***")


class CliAliasTest(unittest.TestCase):
    def test_check_alias_does_not_require_camera(self) -> None:
        self.assertEqual(main(["check"]), 0)


class ConfigTest(unittest.TestCase):
    def test_ollama_ready_without_api_key(self) -> None:
        config = Config(enable_llm_verify=True, llm_provider="ollama", ollama_model="gemma3:4b")
        self.assertTrue(config.llm_ready)

    def test_openai_compatible_requires_key_and_model(self) -> None:
        self.assertFalse(Config(enable_llm_verify=True).llm_ready)
        self.assertTrue(
            Config(
                enable_llm_verify=True,
                openai_api_key="key",
                openai_model="vision-model",
            ).llm_ready
        )


if __name__ == "__main__":
    unittest.main()
