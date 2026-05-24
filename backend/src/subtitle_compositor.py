"""
PIL-based subtitle rendering helpers for premium / Riverside-style captions.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


def spring_scale(elapsed: float, pop_duration: float = 0.06, peak_scale: float = 1.15) -> float:
    """Snappy pop curve for active word (quick rise, minimal settle)."""
    if elapsed <= 0:
        return 1.0
    if elapsed >= pop_duration:
        return 1.0
    t = elapsed / pop_duration
    if t < 0.5:
        return 1.0 + (peak_scale - 1.0) * (t / 0.5)
    return peak_scale - (peak_scale - 1.0) * ((t - 0.5) / 0.5)


def is_premium_template(template: Dict) -> bool:
    """Whether template should use PIL premium compositor."""
    if template.get("premium") or template.get("pill_style"):
        return True
    return template.get("name") == "Riverside"


def active_word_scale(template: Dict, elapsed: float, word_duration: float) -> float:
    if not template.get("active_word_bounce", is_premium_template(template)):
        return 1.0
    peak = float(template.get("active_word_scale", 1.15))
    pop_duration = min(float(template.get("bounce_duration", 0.06)), word_duration)
    return spring_scale(elapsed, pop_duration=pop_duration, peak_scale=peak)


def format_word_text(word: str, template: Dict) -> str:
    if template.get("uppercase"):
        return word.upper()
    return word


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(font_path, size=size)
    except Exception:
        return ImageFont.load_default()


def _parse_color(color: str, default: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    if not color:
        return default
    c = color.lstrip("#")
    if len(c) == 6:
        r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
        return r, g, b, 255
    if len(c) == 8:
        r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
        a = int(c[6:8], 16)
        return r, g, b, a
    return default


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    r, g, b, _ = _parse_color(color, (255, 255, 255, 255))
    return r, g, b


def _split_phrase_lines(words: List[str], max_per_line: int = 4) -> List[List[str]]:
    if len(words) <= max_per_line:
        return [words]
    mid = (len(words) + 1) // 2
    return [words[:mid], words[mid:]]


def _measure_line(
    line_words: List[str],
    active_global_idx: int,
    line_start_idx: int,
    template: Dict,
    font_path: str,
    base_size: int,
) -> Tuple[int, int, int, List[Tuple[str, int, ImageFont.FreeTypeFont | ImageFont.ImageFont, bool]]]:
    """Return line width, height, max ascent, and word layout entries."""
    spacing = int(base_size * 0.22)
    font = _load_font(font_path, base_size)
    active_font = _load_font(font_path, int(base_size * 1.08))

    entries: List[Tuple[str, int, ImageFont.FreeTypeFont | ImageFont.ImageFont, bool]] = []
    total_w = 0
    max_ascent = 0
    max_descent = 0

    for i, word in enumerate(line_words):
        global_idx = line_start_idx + i
        is_active = global_idx == active_global_idx
        text = format_word_text(word, template)
        fnt = active_font if is_active else font
        ascent, descent = fnt.getmetrics()
        max_ascent = max(max_ascent, ascent)
        max_descent = max(max_descent, descent)
        bbox = fnt.getbbox(text, anchor="ls")
        w = bbox[2] - bbox[0]
        entries.append((text, w, fnt, is_active))
        total_w += w + (spacing if i < len(line_words) - 1 else 0)

    line_h = max_ascent + max_descent
    return total_w, line_h, max_ascent, entries


def render_pill_phrase_image(
    words: List[str],
    active_idx: int,
    template: Dict,
    font_path: str,
    video_width: int,
    max_width: int,
) -> Image.Image:
    """Riverside-style: dark rounded pill, active word highlight fill."""
    base_size = int(template.get("font_size", 28))
    pill_rgba = _parse_color(
        template.get("background_color") or "#1A1A1ACC",
        (26, 26, 26, 204),
    )
    highlight_rgba = _parse_color(
        template.get("highlight_color") or "#8B5CF6",
        (139, 92, 246, 255),
    )
    text_rgb = _hex_to_rgb(template.get("font_color", "#FFFFFF"))

    lines = _split_phrase_lines(words, max_per_line=4)
    line_layouts: List[Tuple[int, int, int, List]] = []
    line_start = 0
    for line in lines:
        lw, lh, max_ascent, entries = _measure_line(
            line, active_idx, line_start, template, font_path, base_size
        )
        if lw > max_width and base_size > 20:
            return render_pill_phrase_image(
                words,
                active_idx,
                {**template, "font_size": int(base_size * 0.88)},
                font_path,
                video_width,
                max_width,
            )
        line_layouts.append((lw, lh, max_ascent, entries))
        line_start += len(line)

    line_gap = int(base_size * 0.35)
    pad_x = int(base_size * 0.55)
    pad_y = int(base_size * 0.35)
    content_w = max(lw for lw, _, _, _ in line_layouts)
    content_h = sum(lh for _, lh, _, _ in line_layouts) + line_gap * (len(line_layouts) - 1)

    img_w = min(video_width, content_w + pad_x * 2)
    img_h = content_h + pad_y * 2
    image = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    radius = max(8, int(base_size * 0.45))
    draw.rounded_rectangle(
        [(0, 0), (img_w - 1, img_h - 1)],
        radius=radius,
        fill=pill_rgba,
    )

    font = _load_font(font_path, base_size)
    spacing = int(base_size * 0.22)
    hl_pad_x = max(4, int(base_size * 0.12))
    hl_pad_y = max(2, int(base_size * 0.08))

    y = pad_y
    for _, (lw, lh, max_ascent, entries) in zip(lines, line_layouts):
        baseline_y = y + max_ascent
        x = (img_w - lw) // 2
        for text, w, fnt, is_active in entries:
            if is_active:
                bbox = draw.textbbox((x, baseline_y), text, font=fnt, anchor="ls")
                hl_x1 = bbox[0] - hl_pad_x
                hl_y1 = bbox[1] - hl_pad_y
                hl_x2 = bbox[2] + hl_pad_x
                hl_y2 = bbox[3] + hl_pad_y
                draw.rounded_rectangle(
                    [(hl_x1, hl_y1), (hl_x2, hl_y2)],
                    radius=max(4, int(base_size * 0.2)),
                    fill=highlight_rgba,
                )
            draw.text((x, baseline_y), text, font=fnt, fill=text_rgb, anchor="ls")
            x += w + spacing
        y += lh + line_gap

    return image


def render_phrase_image(
    words: List[str],
    active_idx: int,
    template: Dict,
    font_path: str,
    video_width: int,
    max_width: int,
) -> Image.Image:
    """Render phrase — pill style for premium templates, legacy stroke otherwise."""
    if template.get("pill_style") or is_premium_template(template):
        return render_pill_phrase_image(
            words, active_idx, template, font_path, video_width, max_width
        )

    base_size = int(template.get("font_size", 40))
    font = _load_font(font_path, base_size)
    normal_rgb = _hex_to_rgb(template.get("font_color", "#FFFFFF"))
    highlight_rgb = _hex_to_rgb(template.get("highlight_color", "#FFFF00"))
    stroke = int(template.get("stroke_width", 3))
    stroke_rgb = _hex_to_rgb(template.get("stroke_color", "#000000"))
    spacing = int(base_size * 0.28)

    visible = words[: active_idx + 1]
    total_w = 0
    max_h = base_size
    for idx, word in enumerate(visible):
        text = format_word_text(word, template)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_h = max(max_h, h)
        total_w += w + (spacing if idx < len(visible) - 1 else 0)

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

    for idx, word in enumerate(visible):
        text = format_word_text(word, template)
        is_active = idx == active_idx
        color = highlight_rgb if is_active else normal_rgb
        draw.text(
            (x, y),
            text,
            font=font,
            fill=color,
            stroke_width=stroke,
            stroke_fill=stroke_rgb,
        )
        bbox = font.getbbox(text)
        x += (bbox[2] - bbox[0]) + spacing

    return image


def create_premium_karaoke_clips(
    relevant_words: List[Dict],
    video_width: int,
    video_height: int,
    template: Dict,
    font_path: str,
    position_y: float = 0.82,
    layout_timeline: Optional[List] = None,
) -> List:
    """Render premium/Riverside karaoke as PIL ImageClips with tight word timing."""
    from moviepy import ImageClip

    from .layout_director import caption_position_y_at_time

    clips = []
    words_per_group = 6
    max_width = int(video_width * 0.88)
    phrase_end_pad = 0.05

    for group_idx in range(0, len(relevant_words), words_per_group):
        group = relevant_words[group_idx : group_idx + words_per_group]
        if not group:
            continue

        raw_words = [w["text"] for w in group]
        phrase_end = float(group[-1]["end"]) + phrase_end_pad

        for word_idx, current in enumerate(group):
            word_start = float(current["start"])
            word_end = float(current["end"])
            if word_idx + 1 < len(group):
                duration = float(group[word_idx + 1]["start"]) - word_start
            else:
                duration = phrase_end - word_start
            duration = max(0.05, duration)
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
            word_position_y = (
                caption_position_y_at_time(word_start, layout_timeline)
                if layout_timeline
                else position_y
            )
            y_pos = int(video_height * word_position_y - phrase_img.height // 2)
            x_pos = (video_width - phrase_img.width) // 2
            clips.append(clip.with_position((x_pos, y_pos)))

    return clips
