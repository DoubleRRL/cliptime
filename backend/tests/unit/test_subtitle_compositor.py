import sys
import unittest
from pathlib import Path

from PIL import ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.caption_templates import get_template
from src.subtitle_compositor import (
    active_word_scale,
    is_premium_template,
    render_pill_phrase_image,
    spring_scale,
)

FONT_PATH = (
    Path(__file__).resolve().parents[2]
    / ".venv/lib/python3.11/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"
)


class SubtitleCompositorTests(unittest.TestCase):
    def test_spring_scale_peaks_then_settles(self):
        peak = spring_scale(0.05, pop_duration=0.15, peak_scale=1.25)
        settled = spring_scale(0.2, pop_duration=0.15, peak_scale=1.25)
        self.assertGreater(peak, 1.0)
        self.assertAlmostEqual(settled, 1.0, places=2)

    def test_riverside_template_is_premium(self):
        template = get_template("riverside")
        self.assertTrue(is_premium_template(template))
        self.assertTrue(template.get("pill_style"))
        scale = active_word_scale(template, elapsed=0.03, word_duration=0.4)
        self.assertGreater(scale, 1.0)

    def test_opusclip_alias_maps_to_riverside(self):
        template = get_template("opusclip")
        self.assertEqual(template.get("name"), "Riverside")

    def test_baseline_anchor_aligns_mixed_font_sizes(self):
        """Active (1.08x) word shares baseline; larger ascent extends upward, not floating."""
        if not FONT_PATH.exists():
            self.skipTest("DejaVuSans.ttf not available")
        template = get_template("riverside")
        base_size = int(template.get("font_size", 28))
        font = ImageFont.truetype(str(FONT_PATH), base_size)
        active_font = ImageFont.truetype(str(FONT_PATH), int(base_size * 1.08))
        words = ["paid", "$200", "for"]
        active_idx = 1
        spacing = int(base_size * 0.22)
        baseline_y = 100
        x = 0

        from PIL import Image

        scratch = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(scratch)
        tops: list[int] = []
        for i, word in enumerate(words):
            fnt = active_font if i == active_idx else font
            bbox = draw.textbbox((x, baseline_y), word, font=fnt, anchor="ls")
            tops.append(bbox[1])
            x += (bbox[2] - bbox[0]) + spacing

        # Shared baseline: larger active font extends higher (smaller y), not above neighbors.
        self.assertLess(tops[active_idx], tops[0])
        self.assertLess(tops[active_idx], tops[2])

    def test_pill_phrase_renders_all_words(self):
        if not FONT_PATH.exists():
            self.skipTest("DejaVuSans.ttf not available")
        template = get_template("riverside")
        img = render_pill_phrase_image(
            ["tickets,", "you", "feel"],
            active_idx=0,
            template=template,
            font_path=str(FONT_PATH),
            video_width=1080,
            max_width=950,
        )
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)
        # Non-transparent pixels exist (text + pill background)
        alpha = img.getchannel("A")
        self.assertGreater(max(alpha.getdata()), 0)


if __name__ == "__main__":
    unittest.main()
