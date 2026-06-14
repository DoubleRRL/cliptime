"""
ASS karaoke subtitle generation and FFmpeg burn-in.

Adapted from ClipPro's generate_ass() pattern (\\kf smooth-fill tags + libass).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .font_registry import FONTS_DIR, find_font_path

logger = logging.getLogger(__name__)

WORDS_PER_LINE = 4

ASS_HEADER = """\
[Script Info]
Title: SupoClip Karaoke
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_colour},{secondary_colour},{outline_colour},{back_colour},-1,0,0,0,100,100,0,0,{border_style},{outline},{shadow},2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_burn_available() -> bool:
    """Return True if ffmpeg was built with libass subtitles filter."""
    if not shutil.which("ffmpeg"):
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return " ass " in result.stdout or " subtitles " in result.stdout
    except Exception:
        return False


def seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp H:MM:SS.cc."""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def hex_to_ass_color(hex_color: str, alpha: str = "00") -> str:
    """Convert #RRGGBB or #RRGGBBAA to ASS &HAABBGGRR format."""
    color = (hex_color or "#FFFFFF").lstrip("#")
    if len(color) == 8:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        a = int(color[6:8], 16)
        ass_alpha = 255 - a
        return f"&H{ass_alpha:02X}{b:02X}{g:02X}{r:02X}"
    if len(color) == 6:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return f"&H{alpha}{b:02X}{g:02X}{r:02X}"
    return "&H00FFFFFF"


def _resolve_font_name(font_family: str) -> str:
    path = find_font_path(font_family, allow_all_user_fonts=True)
    if path:
        return path.stem.replace("-", " ").replace("_", " ")
    return font_family.replace("-", " ").replace("_", " ")


def generate_ass_from_words(
    words: List[Dict[str, Any]],
    template: Dict[str, Any],
    play_res_x: int,
    play_res_y: int,
    *,
    font_family: Optional[str] = None,
    font_size: Optional[int] = None,
    font_color: Optional[str] = None,
    clip_start_s: float = 0.0,
) -> str:
    """
    Build ASS with \\kf smooth-fill karaoke tags from word-level timings.

    Word times may be absolute or relative to clip start; pass clip_start_s when needed.
    """
    parsed: List[Dict[str, float | str]] = []
    for entry in words:
        text = str(entry.get("text", "")).strip()
        start = entry.get("start", 0.0)
        end = entry.get("end", start)
        if isinstance(start, (int, float)):
            rel_start = float(start) - clip_start_s
            rel_end = float(end) - clip_start_s if isinstance(end, (int, float)) else rel_start + 0.3
            if rel_start >= -1.0 and text:
                parsed.append(
                    {
                        "text": text,
                        "start": max(0.0, rel_start),
                        "end": max(max(0.0, rel_start) + 0.05, rel_end),
                    }
                )

    if not parsed:
        return ""

    effective_size = int(font_size or template.get("font_size", 40))
    scaled_size = max(24, min(64, int(effective_size * (play_res_x / 720))))
    margin_v = max(60, int(play_res_y * (1.0 - float(template.get("position_y", 0.75)) + 0.05)))
    shadow = 1 if template.get("shadow") else 0
    uppercase = bool(template.get("uppercase"))
    primary = hex_to_ass_color(font_color or template.get("font_color", "#FFFFFF"))
    secondary = hex_to_ass_color(template.get("highlight_color", "#FFFF00"))
    outline_colour = hex_to_ass_color(template.get("stroke_color", "#000000"))

    has_background = bool(template.get("background"))
    bg_hex = template.get("background_color") or "#000000AA"
    if has_background:
        border_style = 3
        back_colour = hex_to_ass_color(bg_hex)
        outline = max(0, min(int(template.get("stroke_width", 0)), round(scaled_size * 0.06)))
    else:
        border_style = 1
        back_colour = "&H00000000"
        outline = max(
            1,
            min(int(template.get("stroke_width", 3)), round(scaled_size * 0.08)),
        )

    font_name = _resolve_font_name(font_family or template.get("font_family", "THEBOLDFONT"))

    lines = [
        ASS_HEADER.format(
            play_res_x=play_res_x,
            play_res_y=play_res_y,
            font_name=font_name,
            font_size=scaled_size,
            primary_colour=primary,
            secondary_colour=secondary,
            outline_colour=outline_colour,
            back_colour=back_colour,
            border_style=border_style,
            outline=outline,
            shadow=shadow,
            margin_v=margin_v,
        )
    ]

    groups: List[List[Dict[str, float | str]]] = []
    idx = 0
    while idx < len(parsed):
        groups.append(parsed[idx : idx + WORDS_PER_LINE])
        idx += WORDS_PER_LINE

    for gi, group in enumerate(groups):
        line_start = float(group[0]["start"])
        if gi + 1 < len(groups):
            line_end = max(float(group[-1]["end"]) + 0.05, line_start + 0.1)
        else:
            line_end = max(line_start + 0.1, float(group[-1]["end"]) + 0.05)

        karaoke_parts: List[str] = []
        for j, word_entry in enumerate(group):
            word = str(word_entry["text"])
            t = float(word_entry["start"])
            if j + 1 < len(group):
                dur_cs = max(5, int((float(group[j + 1]["start"]) - t) * 100))
            else:
                dur_cs = max(5, int((float(group[j]["end"]) - t) * 100))
            display = word.upper() if uppercase else word
            karaoke_parts.append(f"{{\\k{dur_cs}}}{display}")

        text = " ".join(karaoke_parts)
        lines.append(
            f"Dialogue: 0,{seconds_to_ass_time(line_start)},"
            f"{seconds_to_ass_time(line_end)},Default,,0,0,0,,{text}"
        )

    return "\n".join(lines)


def burn_ass_subtitles(
    input_mp4: Path,
    ass_content: str,
    output_mp4: Path,
    *,
    fonts_dir: Optional[Path] = None,
    timeout: int = 600,
) -> bool:
    """Burn ASS subtitles onto a video via ffmpeg libass."""
    work_dir = output_mp4.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    ass_path = work_dir / f"{output_mp4.stem}_captions.ass"
    ass_path.write_text(ass_content, encoding="utf-8")

    fonts = fonts_dir or FONTS_DIR
    ass_filter = f"ass={ass_path.name}"
    if fonts.exists():
        ass_filter = f"ass={ass_path.name}:fontsdir={fonts}"

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(input_mp4),
        "-vf",
        ass_filter,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(work_dir),
    )
    if result.returncode != 0:
        logger.error("ASS burn failed: %s", result.stderr.strip())
        return False
    return True
