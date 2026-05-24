"""Tests for Riverside layout director (solo/dual timeline)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.layout_director import (
    DUAL_MIN_MS,
    LayoutSegment,
    build_layout_timeline,
    classify_portrait_frame,
    detect_dual_moments,
    dual_stack_half_height,
    ordered_speakers_from_panels,
)


class DetectDualMomentsTests(unittest.TestCase):
    def test_overlapping_words_create_dual_window(self):
        transcript = {
            "words": [
                {"speaker": "A", "start": 1000, "end": 2000, "text": "hello"},
                {"speaker": "B", "start": 1200, "end": 2500, "text": "yeah"},
            ],
            "utterances": [],
        }
        windows = detect_dual_moments(transcript, 0, 5000)
        self.assertTrue(windows)
        start, end = windows[0]
        self.assertLessEqual(start, 1200)
        self.assertGreaterEqual(end, 2000)
        self.assertGreaterEqual(end - start, DUAL_MIN_MS)

    def test_laughter_utterance_creates_dual_window(self):
        transcript = {
            "words": [
                {"speaker": "A", "start": 0, "end": 500, "text": "funny"},
                {"speaker": "B", "start": 600, "end": 1200, "text": "haha"},
            ],
            "utterances": [
                {"speaker": "B", "start": 600, "end": 1200, "text": "haha that's hilarious"},
            ],
        }
        windows = detect_dual_moments(transcript, 0, 5000)
        self.assertTrue(windows)

    def test_single_speaker_no_dual_windows(self):
        transcript = {
            "words": [
                {"speaker": "A", "start": 0, "end": 1000, "text": "solo"},
                {"speaker": "A", "start": 1100, "end": 2000, "text": "talk"},
            ],
            "utterances": [
                {"speaker": "A", "start": 0, "end": 2000, "text": "solo talk"},
            ],
        }
        windows = detect_dual_moments(transcript, 0, 5000)
        self.assertEqual(windows, [])


class BuildLayoutTimelineTests(unittest.TestCase):
    def test_solo_turn_without_overlap(self):
        transcript = {
            "words": [
                {"speaker": "A", "start": 0, "end": 800, "text": "hello"},
                {"speaker": "A", "start": 900, "end": 2000, "text": "world"},
                {"speaker": "B", "start": 2500, "end": 4000, "text": "reply"},
            ],
            "utterances": [],
        }
        timeline = build_layout_timeline(
            transcript, 0, 5000, src_w=1280, src_h=720
        )
        modes = {seg.mode for seg in timeline}
        self.assertIn("solo", modes)
        solo_segments = [s for s in timeline if s.mode == "solo"]
        self.assertTrue(solo_segments)
        for seg in solo_segments:
            self.assertIn(seg.speaker, ("A", "B", None))

    def test_overlap_produces_dual_segment(self):
        transcript = {
            "words": [
                {"speaker": "A", "start": 1000, "end": 1800, "text": "long"},
                {"speaker": "B", "start": 1200, "end": 2000, "text": "overlap"},
            ],
            "utterances": [],
        }
        panels = {
            "A": {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 320, "face_cy": 300},
            "B": {"x": 640, "y": 0, "w": 640, "h": 720, "face_cx": 960, "face_cy": 300},
        }
        mock_video = MagicMock()
        with patch("src.layout_director.validate_dual_frame", return_value=True):
            timeline = build_layout_timeline(
                transcript,
                0,
                5000,
                src_w=1280,
                src_h=720,
                full_video=mock_video,
                panels=panels,
            )
        dual_segments = [s for s in timeline if s.mode == "dual"]
        self.assertTrue(dual_segments)

    def test_long_monologue_dual_within_overlap_window(self):
        transcript = {
            "words": [
                {"speaker": "A", "start": 0, "end": 8000, "text": "monologue"},
                {"speaker": "B", "start": 200, "end": 1500, "text": "yeah"},
            ],
            "utterances": [],
        }
        panels = {
            "A": {"x": 0, "y": 0, "w": 640, "h": 720},
            "B": {"x": 640, "y": 0, "w": 640, "h": 720},
        }
        mock_video = MagicMock()
        with patch("src.layout_director.validate_dual_frame", return_value=True), patch(
            "src.layout_director.detect_visual_dual_moments", return_value=[]
        ):
            timeline = build_layout_timeline(
                transcript,
                0,
                10000,
                src_w=1280,
                src_h=720,
                full_video=mock_video,
                panels=panels,
            )
        dual_segments = [s for s in timeline if s.mode == "dual"]
        self.assertTrue(dual_segments)
        long_solo = [s for s in timeline if s.mode == "solo" and s.end_ms - s.start_ms >= 2000]
        self.assertTrue(long_solo)


class PortraitClassifierTests(unittest.TestCase):
    def test_single_face_frame_is_solo(self):
        frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        with patch("src.layout_director._detect_faces_in_frame") as mock_faces:
            mock_faces.return_value = [(400, 200, 280, 280)]
            self.assertEqual(classify_portrait_frame(frame), "solo")

    def test_top_bottom_faces_are_dual(self):
        frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        with patch("src.layout_director._detect_faces_in_frame") as mock_faces:
            mock_faces.return_value = [
                (400, 100, 200, 200),
                (400, 1100, 200, 200),
            ]
            self.assertEqual(classify_portrait_frame(frame), "dual")


class DualStackHelperTests(unittest.TestCase):
    def test_dual_stack_half_height(self):
        self.assertEqual(dual_stack_half_height(1920), 960)

    def test_ordered_speakers_left_to_right(self):
        panels = {
            "B": {"x": 640, "y": 0, "w": 640, "h": 720},
            "A": {"x": 0, "y": 0, "w": 640, "h": 720},
        }
        self.assertEqual(ordered_speakers_from_panels(panels), ["A", "B"])


class RenderDualStackTests(unittest.TestCase):
    def test_dual_stack_output_dimensions(self):
        from src.layout_director import render_dual_stack_segment

        out_w, out_h = 1080, 1920
        panels = {
            "A": {"x": 0, "y": 0, "w": 640, "h": 720, "face_cx": 320, "face_cy": 260},
            "B": {"x": 640, "y": 0, "w": 640, "h": 720, "face_cx": 960, "face_cy": 260},
        }

        mock_video = MagicMock()
        mock_sub = MagicMock()
        mock_video.subclipped.return_value = mock_sub
        mock_sub.cropped.return_value = mock_sub
        mock_sub.resized.return_value = mock_sub
        mock_sub.duration = 2.0
        mock_sub.with_position.return_value = mock_sub

        with patch("src.layout_director.CompositeVideoClip") as mock_composite:
            mock_instance = MagicMock()
            mock_instance.with_duration.return_value = mock_instance
            mock_instance.size = (out_w, out_h)
            mock_composite.return_value = mock_instance

            result = render_dual_stack_segment(
                mock_video, 0.0, 2.0, panels, 1280, 720, out_w, out_h
            )
            self.assertIsNotNone(result)
            mock_composite.assert_called_once()
            size_arg = mock_composite.call_args.kwargs.get("size")
            self.assertEqual(size_arg, (out_w, out_h))

            resize_calls = mock_sub.resized.call_args_list
            self.assertEqual(len(resize_calls), 2)
            for call in resize_calls:
                size = call[0][0]
                self.assertEqual(size[0], out_w)
                self.assertEqual(size[1], dual_stack_half_height(out_h))


if __name__ == "__main__":
    unittest.main()
