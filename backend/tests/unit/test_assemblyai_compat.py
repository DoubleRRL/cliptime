import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.assemblyai_compat import _apply_speech_models, speech_models_for_mode


class AssemblyAICompatTests(unittest.TestCase):
    def test_speech_models_for_quality_mode(self):
        self.assertEqual(
            speech_models_for_mode("best"),
            ["universal-3-pro", "universal-2"],
        )

    def test_speech_models_for_fast_mode(self):
        self.assertEqual(speech_models_for_mode("nano"), ["universal-2"])

    def test_apply_speech_models_replaces_deprecated_field(self):
        payload = _apply_speech_models(
            {"audio_url": "https://example.com/a.mp3", "speech_model": "best"}
        )
        self.assertNotIn("speech_model", payload)
        self.assertEqual(payload["speech_models"], ["universal-3-pro", "universal-2"])

    def test_apply_speech_models_respects_existing_array(self):
        payload = _apply_speech_models(
            {
                "audio_url": "https://example.com/a.mp3",
                "speech_models": ["universal-2"],
            }
        )
        self.assertEqual(payload["speech_models"], ["universal-2"])


if __name__ == "__main__":
    unittest.main()
