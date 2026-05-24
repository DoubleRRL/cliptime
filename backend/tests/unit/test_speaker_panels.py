import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.speaker_panels import (
    fit_portrait_crop,
    is_portrait_source,
    is_riverside_dual_feed,
    panel_to_vertical_crop,
    riverside_slot_crop,
    round_to_even,
)


class SpeakerPanelTests(unittest.TestCase):
    def test_panel_to_vertical_crop_9_16(self):
        panel = {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 320, "face_cy": 270}
        x1, y1, x2, y2 = panel_to_vertical_crop(panel, 1280, 720)
        width = x2 - x1
        height = y2 - y1
        self.assertEqual(width, round_to_even(int(height * 9 / 16)))
        self.assertLessEqual(x2, 1280)

    def test_landscape_two_speaker_slot_crop(self):
        """1920x1080 Riverside split: left slot crop ~608x992 with headroom."""
        panel = {
            "x": 0,
            "y": 0,
            "w": 960,
            "h": 1080,
            "face_cx": 480,
            "face_cy": 400,
        }
        x1, y1, x2, y2 = fit_portrait_crop(panel, 1920, 1080)
        width = x2 - x1
        height = y2 - y1
        self.assertGreaterEqual(width, round_to_even(int(960 * 0.55)))
        self.assertAlmostEqual(width / height, 9 / 16, places=2)
        self.assertGreaterEqual(x1, 0)
        self.assertLessEqual(x2, 960)

    def test_crop_respects_max_zoom_cap(self):
        panel = {"x": 100, "y": 0, "w": 960, "h": 1080, "face_cx": 500, "face_cy": 380}
        x1, _, x2, _ = fit_portrait_crop(panel, 1920, 1080)
        self.assertGreaterEqual(x2 - x1, round_to_even(int(960 * 0.55)))

    def test_portrait_source_passthrough(self):
        self.assertTrue(is_portrait_source(1080, 1920))
        panel = {"x": 0, "y": 0, "w": 1080, "h": 1920, "face_cx": 540, "face_cy": 500}
        x1, y1, x2, y2 = fit_portrait_crop(panel, 1080, 1920)
        self.assertEqual(x2 - x1, 1080)
        self.assertGreaterEqual(y1, 0)
        self.assertLessEqual(y2, 1920)

    def test_calibrate_requires_multiple_speakers(self):
        from src.speaker_panels import calibrate_speaker_panels
        from unittest.mock import MagicMock

        video = MagicMock()
        video.size = (1280, 720)
        video.duration = 60
        transcript = {
            "utterances": [
                {"speaker": "A", "start": 0, "end": 2000, "text": "hello"},
            ]
        }
        self.assertEqual(calibrate_speaker_panels(video, transcript), {})

    def test_riverside_dual_feed_detects_1280x720(self):
        panels = {
            "A": {"x": 0, "y": 0, "w": 640, "h": 720},
            "B": {"x": 640, "y": 0, "w": 640, "h": 720},
        }
        self.assertTrue(is_riverside_dual_feed(1280, 720, panels))
        self.assertFalse(is_riverside_dual_feed(1920, 1080, {"A": panels["A"]}))

    def test_riverside_slot_uses_full_column_height(self):
        panel = {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 520, "face_cy": 300}
        x1, y1, x2, y2 = riverside_slot_crop(panel, 1280, 720)
        self.assertEqual(y1, 0)
        self.assertEqual(y2 - y1, 720)
        self.assertAlmostEqual((x2 - x1) / (y2 - y1), 9 / 16, places=2)
        self.assertGreater(x1, 0)


if __name__ == "__main__":
    unittest.main()
