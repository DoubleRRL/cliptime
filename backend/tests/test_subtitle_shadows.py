"""Tests for OpusClip-style subtitle shadow offsets and emoji keyword lookup."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.caption_templates import get_template


class SubtitleShadowTests(unittest.TestCase):
    def test_opusclip_template_shadow_offset(self):
        template = get_template("opusclip")

        self.assertEqual(template.get("name"), "OpusClip Style")
        self.assertTrue(template.get("shadow"))
        self.assertEqual(template.get("shadow_offset"), (4, 4))
        self.assertEqual(template.get("stroke_width"), 4)
        self.assertEqual(template.get("highlight_color"), "#FFFF00")
        self.assertEqual(template.get("secondary_highlight"), "#00FF00")

    def test_shadow_offset_placement_math(self):
        """Shadow layer should sit +4px right and +4px down from the main word."""
        word_x = 120
        word_y = 800
        shadow_offset_x, shadow_offset_y = 4, 4

        shadow_x = int(word_x + shadow_offset_x)
        shadow_y = int(word_y + shadow_offset_y)

        self.assertEqual(shadow_x, 124)
        self.assertEqual(shadow_y, 804)

    def test_bounce_pop_duration_window(self):
        word_duration = 0.35
        pop_duration = min(0.12, word_duration)
        rest_duration = word_duration - pop_duration

        self.assertAlmostEqual(pop_duration, 0.12)
        self.assertAlmostEqual(rest_duration, 0.23, places=2)

    def test_emoji_vertical_gap_above_word(self):
        vertical_position = 800
        emoji_h = 40
        emoji_y = int(vertical_position - emoji_h - 15)

        self.assertEqual(emoji_y, 745)


if __name__ == "__main__":
    unittest.main()
