"""Tests for Riverside spatial speaker binding and crop helpers."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.layout_director import (
    build_layout_timeline,
    caption_position_y_at_time,
    detect_visual_dual_moments,
    LayoutSegment,
)
from src.speaker_panels import (
    PANEL_CACHE_VERSION,
    bind_speakers_to_columns,
    default_riverside_panels,
    resolve_speaker_panel,
    riverside_dual_half_crop,
    riverside_slot_crop,
)


class SpatialBindingTests(unittest.TestCase):
    def test_speaker_b_on_left_column_by_face_x(self):
        seating = {"A": 980, "B": 420}
        panels = bind_speakers_to_columns(seating, 1280, 720)
        self.assertEqual(panels["B"]["x"], 0)
        self.assertEqual(panels["A"]["x"], 640)
        self.assertEqual(panels["B"]["face_cx"], 420)

    def test_default_panels_use_inner_edge_heuristic(self):
        panels = default_riverside_panels(1280, 720)
        self.assertGreater(panels["A"]["face_cx"], 320)
        self.assertLess(panels["A"]["face_cx"], 640)
        self.assertGreater(panels["B"]["face_cx"], 640)

    def test_resolve_speaker_panel_uses_seating_map(self):
        panels = default_riverside_panels(1280, 720)
        resolved = resolve_speaker_panel("X", panels, seating_map={"X": 450}, src_w=1280, src_h=720)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["x"], 0)

    def test_panel_cache_version_bumped(self):
        self.assertEqual(PANEL_CACHE_VERSION, 4)


class RiversideCropTests(unittest.TestCase):
    def test_off_center_face_shifts_crop_right(self):
        panel = {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 320, "face_cy": 300}
        center_crop = riverside_slot_crop(panel, 1280, 720)
        off_center = riverside_slot_crop(panel, 1280, 720, face_cx=520)
        self.assertGreater(off_center[0], center_crop[0])

    def test_full_column_crop_uses_entire_slot(self):
        panel = {"x": 640, "y": 0, "w": 640, "h": 720}
        x1, y1, x2, y2 = riverside_slot_crop(panel, 1280, 720, use_full_column=True)
        self.assertEqual(x1, 640)
        self.assertEqual(x2 - x1, 640)
        self.assertEqual(y2 - y1, 720)

    def test_dual_half_crop_matches_target_aspect(self):
        panel = {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 500, "face_cy": 280}
        out_w, out_h = 1080, 960
        x1, y1, x2, y2 = riverside_dual_half_crop(
            panel, 1280, 720, out_w, out_h, face_cx=500, face_cy=280
        )
        crop_w = x2 - x1
        crop_h = y2 - y1
        self.assertAlmostEqual(crop_w / crop_h, out_w / out_h, places=2)
        self.assertGreaterEqual(crop_w, 600)

    def test_dual_half_crop_wider_than_solo_strip(self):
        panel = {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 500, "face_cy": 280}
        solo = riverside_slot_crop(panel, 1280, 720, face_cx=500)
        dual = riverside_dual_half_crop(panel, 1280, 720, 1080, 960, face_cx=500)
        self.assertGreater(dual[2] - dual[0], solo[2] - solo[0])


class CaptionPositionTests(unittest.TestCase):
    def test_dual_segment_uses_seam_position(self):
        timeline = [
            LayoutSegment(0, 4000, "dual"),
            LayoutSegment(4000, 12000, "solo"),
        ]
        self.assertEqual(caption_position_y_at_time(1.0, timeline), 0.50)
        self.assertEqual(caption_position_y_at_time(5.0, timeline), 0.77)


class VisualDualTimelineTests(unittest.TestCase):
    def test_monologue_gets_visual_dual_segment(self):
        transcript = {
            "words": [
                {"speaker": "B", "start": 0, "end": 12000, "text": "story"},
            ],
            "utterances": [
                {"speaker": "B", "start": 0, "end": 12000, "text": "long story"},
            ],
        }
        panels = {
            "A": {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 500, "face_cy": 300},
            "B": {"x": 640, "y": 0, "w": 640, "h": 720, "face_cx": 960, "face_cy": 300},
        }
        mock_video = MagicMock()

        with patch(
            "src.layout_director.detect_visual_dual_moments",
            return_value=[(0, 3000)],
        ), patch("src.layout_director.validate_dual_frame", return_value=True):
            timeline = build_layout_timeline(
                transcript,
                0,
                12000,
                src_w=1280,
                src_h=720,
                full_video=mock_video,
                panels=panels,
            )

        dual_segments = [s for s in timeline if s.mode == "dual"]
        self.assertTrue(dual_segments)

    def test_visual_dual_requires_consecutive_samples(self):
        panels = {
            "A": {"x": 0, "y": 0, "w": 640, "h": 720},
            "B": {"x": 640, "y": 0, "w": 640, "h": 720},
        }
        mock_video = MagicMock()
        call_count = {"n": 0}

        def alternating_dual(_video, t_s, _panels):
            call_count["n"] += 1
            return call_count["n"] % 2 == 0

        with patch(
            "src.layout_director.validate_dual_frame",
            side_effect=alternating_dual,
        ):
            windows = detect_visual_dual_moments(mock_video, 0, 5000, panels)

        self.assertEqual(windows, [])


if __name__ == "__main__":
    unittest.main()
