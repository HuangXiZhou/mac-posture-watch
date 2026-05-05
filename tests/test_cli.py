import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from posture_watch.cli import main
from posture_watch.cli import _safe_config
from posture_watch.config import Config, load_config


class SafeConfigTest(unittest.TestCase):
    def test_redacts_secret_fields(self) -> None:
        data = _safe_config(
            Config(openai_api_key="test-key", bark_endpoint="https://example.invalid/bark")
        )
        self.assertEqual(data["openai_api_key"], "***")
        self.assertEqual(data["bark_endpoint"], "***")


class CliAliasTest(unittest.TestCase):
    def test_public_help_only_shows_essential_commands(self) -> None:
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        text = output.getvalue()
        for command in ("setup", "start", "adapt", "doctor"):
            self.assertIn(command, text)
        for command in ("calibrate", "placements", "eval", "autostart-on", "run", "watch"):
            self.assertNotIn(f"    {command}", text)

    def test_check_alias_does_not_require_camera(self) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(main(["check"]), 0)

    def test_eval_runs_without_camera_dependencies(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["eval"])
        self.assertEqual(code, 0)
        self.assertIn("precision=1.00", output.getvalue())

    def test_camera_check_failure_returns_nonzero_without_traceback(self) -> None:
        output = StringIO()
        with patch("posture_watch.runtime.Camera", side_effect=RuntimeError("permission denied")):
            with redirect_stdout(output):
                code = main(["check", "--camera-check"])
        self.assertEqual(code, 1)
        self.assertIn("camera: failed permission denied", output.getvalue())

    def test_start_runtime_error_returns_message_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / ".env"
            env_path.write_text(
                f"DATA_DIR={tempdir}\nPLACEMENT_PROFILE=default\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            with patch.dict(os.environ, {}, clear=True):
                with patch(
                    "posture_watch.cli.adapt_placement",
                    side_effect=RuntimeError("mediapipe unavailable"),
                ):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = main(["start", "--config", str(env_path)])

        self.assertEqual(code, 1)
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertIn("error: mediapipe unavailable", combined)
        self.assertNotIn("Traceback", combined)

    def test_doctor_notify_sends_test_notification(self) -> None:
        output = StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with patch("posture_watch.runtime.Notifier") as notifier:
                notifier.return_value.send.return_value = SimpleNamespace(
                    mac_sent=True,
                    bark_sent=False,
                )
                with redirect_stdout(output):
                    code = main(["doctor", "--notify"])

        self.assertEqual(code, 0)
        self.assertIn("notification: mac=sent", output.getvalue())

    def test_calibrate_accepts_placement_profile(self) -> None:
        with patch("posture_watch.cli.calibrate") as calibrate:
            code = main(["cal", "--placement", "External Center", "--force"])

        self.assertEqual(code, 0)
        config = calibrate.call_args.args[0]
        self.assertEqual(config.placement_profile, "external-center")
        self.assertEqual(config.baseline_path.name, "external-center.json")

    def test_placement_guide_is_concise(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["placements", "--placement", "external-left"])

        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("Current placement: external-left", text)
        self.assertIn("calibrate once per stable camera + screen + chair layout", text)

    def test_adapt_updates_config_with_detected_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / ".env"
            env_path.write_text("PLACEMENT_PROFILE=default\nBASELINE_PATH=\n", encoding="utf-8")
            adapted = Config(
                placement_profile="auto-front-center",
                data_dir=Path(tempdir),
                baseline_path=Path(tempdir) / "baselines" / "auto-front-center.json",
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch("posture_watch.cli.adapt_placement", return_value=(adapted, None)):
                    with redirect_stdout(StringIO()):
                        code = main(["adapt", "--config", str(env_path)])

            content = env_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("PLACEMENT_PROFILE=auto-front-center", content)
        self.assertIn("BASELINE_PATH=", content)

    def test_start_auto_adapts_when_baseline_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / ".env"
            env_path.write_text(
                f"DATA_DIR={tempdir}\nPLACEMENT_PROFILE=default\n",
                encoding="utf-8",
            )
            adapted = Config(
                placement_profile="auto-front-center",
                data_dir=Path(tempdir),
                baseline_path=Path(tempdir) / "baselines" / "auto-front-center.json",
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch("posture_watch.cli.adapt_placement", return_value=(adapted, None)):
                    with patch("posture_watch.cli.run_watcher", return_value=0) as run_watcher:
                        with redirect_stdout(StringIO()):
                            code = main(["start", "--config", str(env_path)])

            content = env_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(run_watcher.call_args.args[0].placement_profile, "auto-front-center")
        self.assertIn("PLACEMENT_PROFILE=auto-front-center", content)


class ConfigTest(unittest.TestCase):
    def test_load_config_uses_placement_baseline_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / ".env"
            env_path.write_text(
                f"DATA_DIR={tempdir}\nPLACEMENT_PROFILE=External Center\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(env_path)

        self.assertEqual(config.placement_profile, "external-center")
        self.assertEqual(config.baseline_path, Path(tempdir) / "baselines" / "external-center.json")

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
