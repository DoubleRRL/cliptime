"""
PIL-based subtitle rendering helpers for premium caption templates.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


def spring_scale(elapsed: float, pop_duration: float = 0.15, peak_scale: float = 1.25) -> float:
    """Ease-out spring curve for active-word bounce (0 → peak → 1.0)."""
    if elapsed <= 0:
        return 1.0
    if elapsed >= pop_duration:
        return 1.0
    t = elapsed / pop_duration
    if t < 0.45:
        return 1.0 + (peak_scale - 1.0) * (t / 0.45)
    settle = (t - 0.45) / 0.55
    return 1.0 + (peak_scale - 1.0) * (1.0 - settle) * math.cos(settle * math.pi) * 0.35


def is_premium_template(template: Dict) -> bool:
    """Whether template should use OpusClip-style premium effects."""
    if template.get("premium"):
        return True
    return template.get("name") == "OpusClip Style"


def active_word_scale(template: Dict, elapsed: float, word_duration: float) -> float:
    """Return scale multiplier for the active word at time `elapsed`."""
    if not template.get("active_word_bounce", is_premium_template(template)):
        return 1.0
    peak = float(template.get("active_word_scale", 1.25))
    pop_duration = min(float(template.get("bounce_duration", 0.15)), word_duration)
    return spring_scale(elapsed, pop_duration=pop_duration, peak_scale=peak)


def format_word_text(word: str, template: Dict) -> str:
    if template.get("uppercase") or is_premium_template(template):
        return word.upper()
    return word


def shadow_offset(template: Dict) -> Tuple[int, int]:
    raw = template.get("shadow_offset", (4, 4))
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return int(raw[0]), int(raw[1])
    return 4, 4


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(font_path, size=size)
    except Exception:
        return ImageFont.load_default()


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = (color or "#FFFFFF").lstrip("#")
    if len(color) == 6:
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
    return 255, 255, 255


def render_phrase_image(
    words: List[str],
    active_idx: int,
    template: Dict,
    font_path: str,
    video_width: int,
    max_width: int,
) -> Image.Image:
    """Render a phrase window with one active highlighted word."""
    base_size = int(template.get("font_size", 40))
    active_size = int(base_size * active_word_scale(template, 0.05, 0.4))
    font = _load_font(font_path, base_size)
    active_font = _load_font(font_path, active_size)

    stroke = int(template.get("stroke_width", 3))
    normal_rgb = _hex_to_rgb(template.get("font_color", "#FFFFFF"))
    highlight_rgb = _hex_to_rgb(template.get("highlight_color", "#FFFF00"))
    stroke_rgb = _hex_to_rgb(template.get("stroke_color", "#000000"))

    spacing = int(base_size * 0.28)
    word_boxes: List[Tuple[str, int, int, bool]] = []
    total_w = 0
    max_h = base_size

    for idx, word in enumerate(words):
        text = format_word_text(word, template)
        fnt = active_font if idx == active_idx else font
        bbox = fnt.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_h = max(max_h, h)
        word_boxes.append((text, w, h, idx == active_idx))
        total_w += w + (spacing if idx < len(words) - 1 else 0)

    if total_w > max_width and base_size > 24:
        return render_phrase_image(
            words,
            active_idx,
            {**template, "font_size": int(base_size * 0.85)},
            font_path,
            video_width,
            max_width,
        )

    img_h = max_h + stroke * 4 + 16
    img_w = min(video_width, total_w + stroke * 4 + 32)
    image = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    x = (img_w - total_w) // 2
    y = (img_h - max_h) // 2
    sx, sy = shadow_offset(template)

    for idx, (text, w, h, is_active) in enumerate(word_boxes):
        fnt = active_font if is_active else font
        color = highlight_rgb if is_active else normal_rgb
        # Drop shadow
        draw.text(
            (x + sx, y + sy),
            text,
            font=fnt,
            fill=stroke_rgb,
            stroke_width=stroke + 1,
            stroke_fill=stroke_rgb,
        )
        draw.text(
            (x, y),
            text,
            font=fnt,
            fill=color,
            stroke_width=stroke,
            stroke_fill=stroke_rgb,
        )
        x += w + spacing

    return image


def create_premium_karaoke_clips(
    relevant_words: List[Dict],
    video_width: int,
    video_height: int,
    template: Dict,
    font_path: str,
    position_y: float = 0.65,
) -> List:
    """Render premium karaoke subtitles as PIL ImageClips (fewer layers, better look)."""
    from moviepy import ImageClip

    clips = []
    words_per_group = 4
    max_width = int(video_width * 0.88)

    for group_idx in range(0, len(relevant_words), words_per_group):
        group = relevant_words[group_idx : group_idx + words_per_group]
        if not group:
            continue

        raw_words = [w["text"] for w in group]
        group_start = group[0]["start"]
        group_end = group[-1]["end"]

        for word_idx, current in enumerate(group):
            word_start = current["start"]
            word_end = current["end"]
            duration = word_end - word_start
            if duration < 0.05:
                continue

            phrase_img = render_phrase_image(
                raw_words, word_idx, template, font_path, video_width, max_width
            )
            arr = __import__("numpy").array(phrase_img)
            clip = (
                ImageClip(arr, transparent=True)
                .with_duration(duration)
                .with_start(word_start)
            )
            y_pos = int(video_height * position_y - phrase_img.height // 2)
            x_pos = (video_width - phrase_img.width) // 2
            clips.append(clip.with_position((x_pos, y_pos)))

    return clips
