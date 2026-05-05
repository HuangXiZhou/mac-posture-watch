import unittest

from posture_watch.config import Config
from posture_watch.llm import OllamaVerifier, create_verifier, parse_verification_text


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


class OllamaVerifierTest(unittest.TestCase):
    def test_ollama_payload_uses_raw_base64_images(self) -> None:
        config = Config(enable_llm_verify=True, llm_provider="ollama", ollama_model="gemma3:4b")
        verifier = OllamaVerifier(config)
        payload = verifier._payload("prompt", b"image-bytes", b"overlay-bytes")

        self.assertEqual(payload["model"], "gemma3:4b")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["format"], "json")
        images = payload["messages"][0]["images"]
        self.assertEqual(len(images), 2)
        self.assertFalse(images[0].startswith("data:image"))

    def test_create_verifier_selects_ollama_aliases(self) -> None:
        for provider in ("ollama", "local", "gemma"):
            verifier = create_verifier(Config(enable_llm_verify=True, llm_provider=provider))
            self.assertIsInstance(verifier, OllamaVerifier)

    def test_create_verifier_rejects_unknown_provider(self) -> None:
        with self.assertRaises(ValueError):
            create_verifier(Config(enable_llm_verify=True, llm_provider="unknown"))


if __name__ == "__main__":
    unittest.main()
