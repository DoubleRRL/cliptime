import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.caption_templates import get_template
from src.subtitle_compositor import active_word_scale, is_premium_template, spring_scale


class SubtitleCompositorTests(unittest.TestCase):
    def test_spring_scale_peaks_then_settles(self):
        peak = spring_scale(0.05, pop_duration=0.15, peak_scale=1.25)
        settled = spring_scale(0.2, pop_duration=0.15, peak_scale=1.25)
        self.assertGreater(peak, 1.0)
        self.assertAlmostEqual(settled, 1.0, places=2)

    def test_opusclip_template_is_premium(self):
        template = get_template("opusclip")
        self.assertTrue(is_premium_template(template))
        scale = active_word_scale(template, elapsed=0.05, word_duration=0.4)
        self.assertGreater(scale, 1.0)


if __name__ == "__main__":
    unittest.main()
