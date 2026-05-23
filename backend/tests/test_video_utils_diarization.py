import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import video_utils


class VideoUtilsDiarizationTests(unittest.TestCase):
    def test_format_transcript_for_analysis_uses_diarized_utterances(self):
        transcript = SimpleNamespace(
            utterances=[
                SimpleNamespace(
                    start=0,
                    end=2200,
                    speaker="A",
                    text="Hello there.",
                ),
                SimpleNamespace(
                    start=2200,
                    end=4600,
                    speaker="B",
                    text="General Kenobi.",
                ),
            ],
            words=[],
        )

        formatted = video_utils.format_transcript_for_analysis(transcript)

        self.assertEqual(
            formatted,
            [
                "[00:00 - 00:02] Speaker A: Hello there.",
                "[00:02 - 00:04] Speaker B: General Kenobi.",
            ],
        )

    def test_cache_transcript_data_stores_speakers_and_utterances(self):
        transcript = SimpleNamespace(
            text="Hello there.",
            words=[
                SimpleNamespace(
                    text="Hello",
                    start=0,
                    end=400,
                    confidence=0.98,
                    speaker="A",
                ),
                SimpleNamespace(
                    text="there.",
                    start=401,
                    end=900,
                    confidence=0.97,
                    speaker="A",
                ),
            ],
            utterances=[
                SimpleNamespace(
                    text="Hello there.",
                    start=0,
                    end=900,
                    speaker="A",
                    words=[
                        SimpleNamespace(
                            text="Hello",
                            start=0,
                            end=400,
                            confidence=0.98,
                            speaker="A",
                        ),
                        SimpleNamespace(
                            text="there.",
                            start=401,
                            end=900,
                            confidence=0.97,
                            speaker="A",
                        ),
                    ],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "sample.mp4"
            video_path.touch()

            video_utils.cache_transcript_data(video_path, transcript)

            cache_path = video_path.with_suffix(".transcript_cache.json")
            payload = json.loads(cache_path.read_text())

        self.assertEqual(payload["version"], video_utils.TRANSCRIPT_CACHE_SCHEMA_VERSION)
        self.assertEqual(payload["words"][0]["speaker"], "A")
        self.assertEqual(payload["utterances"][0]["speaker"], "A")
        self.assertEqual(payload["utterances"][0]["words"][0]["speaker"], "A")

    @patch("src.video_utils.aai.Transcriber")
    @patch("src.video_utils.build_transcription_config")
    def test_get_video_transcript_enables_speaker_labels(
        self, mock_build_config, mock_transcriber
    ):
        mock_build_config.return_value = object()
        transcript = SimpleNamespace(
            status=video_utils.aai.TranscriptStatus.completed,
            error=None,
            text="Hello there.",
            words=[
                SimpleNamespace(
                    text="Hello",
                    start=0,
                    end=400,
                    confidence=0.98,
                    speaker="A",
                )
            ],
            utterances=[
                SimpleNamespace(
                    start=0,
                    end=2200,
                    speaker="A",
                    text="Hello there.",
                    words=[],
                )
            ],
        )
        mock_transcriber.return_value.transcribe.return_value = transcript

        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "sample.mp4"
            video_path.touch()
            result = video_utils.get_video_transcript(video_path)

        self.assertIn("Speaker A: Hello there.", result)
        mock_build_config.assert_called_once_with("best")

    def test_build_transcription_config_enables_speaker_labels(self):
        config_obj = video_utils.build_transcription_config("best")
        self.assertTrue(config_obj.speaker_labels)
        has_models = getattr(config_obj, "speech_models", None)
        has_legacy = getattr(config_obj, "speech_model", None)
        self.assertTrue(has_models or has_legacy)

    def test_build_speaker_turns_debounces_short_backchannels(self):
        transcript_data = {
            "words": [
                {"text": "So", "start": 0, "end": 400, "speaker": "A"},
                {"text": "yeah", "start": 400, "end": 700, "speaker": "B"},
                {"text": "exactly", "start": 700, "end": 5000, "speaker": "A"},
            ]
        }

        turns = video_utils.build_speaker_turns(
            transcript_data, clip_start_ms=0, clip_end_ms=6000, min_turn_duration=1.2
        )

        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["speaker"], "A")
        self.assertEqual(turns[0]["end_ms"], 700)
        self.assertEqual(turns[1]["speaker"], "A")
        self.assertEqual(turns[1]["start_ms"], 700)

    def test_build_speaker_turns_keeps_distinct_long_speaker_blocks(self):
        transcript_data = {
            "words": [
                {"text": "Hello", "start": 0, "end": 2000, "speaker": "A"},
                {"text": "Hi", "start": 2000, "end": 4500, "speaker": "B"},
                {"text": "Again", "start": 4500, "end": 7000, "speaker": "A"},
            ]
        }

        turns = video_utils.build_speaker_turns(
            transcript_data, clip_start_ms=0, clip_end_ms=8000, min_turn_duration=1.2
        )

        self.assertEqual(len(turns), 3)
        self.assertEqual(turns[0]["speaker"], "A")
        self.assertEqual(turns[1]["speaker"], "B")
        self.assertEqual(turns[2]["speaker"], "A")

    def test_load_cached_transcript_data_supports_legacy_word_only_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "sample.mp4"
            video_path.touch()
            cache_path = video_path.with_suffix(".transcript_cache.json")
            cache_path.write_text(
                json.dumps(
                    {
                        "words": [
                            {"text": "legacy", "start": 0, "end": 300, "confidence": 1.0}
                        ],
                        "text": "legacy",
                    }
                )
            )

            payload = video_utils.load_cached_transcript_data(video_path)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["words"][0]["text"], "legacy")


if __name__ == "__main__":
    unittest.main()
