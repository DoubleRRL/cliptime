"""Tests for Riverside-style subtitle template settings."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.caption_templates import get_template


class SubtitleShadowTests(unittest.TestCase):
    def test_riverside_template_defaults(self):
        template = get_template("riverside")

        self.assertEqual(template.get("name"), "Riverside")
        self.assertTrue(template.get("pill_style"))
        self.assertEqual(template.get("highlight_color"), "#8B5CF6")
        self.assertEqual(template.get("background_color"), "#1A1A1ACC")
        self.assertEqual(template.get("bounce_duration"), 0.06)

    def test_opusclip_alias_resolves_to_riverside(self):
        template = get_template("opusclip")
        self.assertEqual(template.get("name"), "Riverside")


if __name__ == "__main__":
    unittest.main()
