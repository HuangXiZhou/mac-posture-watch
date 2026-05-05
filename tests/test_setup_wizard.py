import tempfile
import unittest
from pathlib import Path

from posture_watch.setup_wizard import run_setup_wizard


class SetupWizardTest(unittest.TestCase):
    def test_local_defaults_write_private_env(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / ".env"
            answers = iter(["", "", "", "", "", ""])
            run_setup_wizard(
                output_path=output,
                input_func=lambda prompt: next(answers),
                secret_func=lambda prompt: "",
                print_func=lambda message: None,
            )

            content = output.read_text(encoding="utf-8")
            self.assertIn("ENABLE_LLM_VERIFY=0", content)
            self.assertIn("PLACEMENT_PROFILE=default", content)
            self.assertIn("LLM_PROVIDER=local", content)
            self.assertIn("FRAME_INTERVAL_SEC=3", content)
            self.assertIn("MAC_NOTIFY=1", content)

    def test_ollama_mode_writes_model_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / ".env"
            answers = iter(["2", "", "", "", "", "", "", "gemma3:4b", ""])
            run_setup_wizard(
                output_path=output,
                input_func=lambda prompt: next(answers),
                secret_func=lambda prompt: "should-not-be-used",
                print_func=lambda message: None,
            )

            content = output.read_text(encoding="utf-8")
            self.assertIn("ENABLE_LLM_VERIFY=1", content)
            self.assertIn("LLM_PROVIDER=ollama", content)
            self.assertIn("OLLAMA_MODEL=gemma3:4b", content)
            self.assertIn("OPENAI_API_KEY=", content)


if __name__ == "__main__":
    unittest.main()
