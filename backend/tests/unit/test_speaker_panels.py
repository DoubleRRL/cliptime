import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.speaker_panels import panel_to_vertical_crop, round_to_even


class SpeakerPanelTests(unittest.TestCase):
    def test_panel_to_vertical_crop_9_16(self):
        panel = {"x": 0, "y": 0, "w": 640, "h": 720}
        x1, y1, x2, y2 = panel_to_vertical_crop(panel, 1280, 720)
        width = x2 - x1
        height = y2 - y1
        self.assertEqual(width, round_to_even(int(height * 9 / 16)))
        self.assertLessEqual(x2, 640)

    def test_calibrate_requires_multiple_speakers(self):
        from src.speaker_panels import calibrate_speaker_panels

        video = MagicMock()
        video.size = (1280, 720)
        video.duration = 60
        transcript = {
            "utterances": [
                {"speaker": "A", "start": 0, "end": 2000, "text": "hello"},
            ]
        }
        self.assertEqual(calibrate_speaker_panels(video, transcript), {})


if __name__ == "__main__":
    unittest.main()
