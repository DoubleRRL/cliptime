#!/usr/bin/env python3
"""
Measure Riverside export caption geometry and render overlay QA frames.

Usage:
  uv run python scripts/measure_riverside_captions.py
  uv run python scripts/measure_riverside_captions.py --video path/to/ref.mp4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEO = (
    ROOT
    / "backend/fixtures/riverside-framing/invisible_bookcase_troupe_jeans_stud.mp4"
)
DEFAULT_OUT = ROOT / "backend/fixtures/riverside-framing/caption-measurements"
SAMPLE_TIMES = (3.0, 8.0)


def extract_frame(video: Path, timestamp: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(output),
        ],
        check=True,
        capture_output=True,
    )


def measure_caption_block(frame_path: Path) -> dict | None:
    rgb = np.array(Image.open(frame_path).convert("RGB"))
    height, width = rgb.shape[:2]
    row_scores: list[tuple[int, float]] = []

    for y in range(int(height * 0.55), int(height * 0.92)):
        row = rgb[y]
        gray = row.mean(axis=1)
        dark = gray < 85
        bright = gray > 215
        if dark.mean() > 0.06 and bright.mean() > 0.015:
            row_scores.append((y, float(dark.mean() * bright.mean())))

    if not row_scores:
        return None

    groups: list[tuple[int, int]] = []
    start = row_scores[0][0]
    prev = row_scores[0][0]
    for y, _ in row_scores[1:]:
        if y - prev > 12:
            groups.append((start, prev))
            start = y
        prev = y
    groups.append((start, prev))

    line_groups = [(a, b) for a, b in groups if b - a + 1 >= 12]
    if not line_groups:
        return None

    top = line_groups[0][0]
    bottom = line_groups[-1][1]
    block_h = bottom - top + 1
    return {
        "width": width,
        "height": height,
        "top": top,
        "bottom": bottom,
        "block_h_px": block_h,
        "block_h_frac": round(block_h / height, 4),
        "center_y": round((top + bottom) / 2 / height, 4),
        "bottom_margin": round((height - bottom) / height, 4),
        "line_count": len(line_groups),
    }


def scaled_font_size(base: int, video_width: int = 1080) -> int:
    return max(24, min(72, int(base * (video_width / 720))))


def render_overlays(frame_path: Path, output_dir: Path, position_y: float) -> list[dict]:
    sys.path.insert(0, str(ROOT / "backend"))
    from src.caption_templates import get_template
    from src.font_registry import find_font_path
    from src.subtitle_compositor import render_pill_phrase_image

    frame = Image.open(frame_path).convert("RGBA")
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = frame.size
    font_path = str(find_font_path("TikTokSans-Regular"))
    template = get_template("riverside")
    words = ["Alright,", "I'll", "just", "go", "into", "the"]
    overlays: list[dict] = []

    for base in (30, 32, 34, 36, 40, 48):
        styled = {**template, "font_size": base, "position_y": position_y}
        pill = render_pill_phrase_image(
            words,
            2,
            styled,
            font_path,
            width,
            int(width * 0.88),
        )
        y_pos = int(height * position_y - pill.size[1] // 2)
        x_pos = (width - pill.size[0]) // 2
        overlay = frame.copy()
        overlay.paste(pill, (x_pos, y_pos), pill)
        out_path = output_dir / f"{frame_path.stem}_base{base}.png"
        overlay.convert("RGB").save(out_path)
        overlays.append(
            {
                "base": base,
                "scaled_font_px": scaled_font_size(base, width),
                "pill_h_px": pill.size[1],
                "output": str(out_path.relative_to(ROOT)),
            }
        )
    return overlays


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Riverside caption geometry")
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--position-y",
        type=float,
        default=0.77,
        help="Center Y fraction for overlay QA renders",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.video.is_file():
        print(f"Reference video not found: {args.video}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = args.out_dir / "frames"
    overlays_dir = args.out_dir / "overlays"

    report: dict = {
        "video": str(args.video.relative_to(ROOT)),
        "position_y_for_overlays": args.position_y,
        "recommended_defaults": {"font_size_base": 32, "position_y": 0.77},
        "frames": [],
    }

    for timestamp in SAMPLE_TIMES:
        frame_path = frames_dir / f"frame_{int(timestamp)}s.jpg"
        extract_frame(args.video, timestamp, frame_path)
        measurement = measure_caption_block(frame_path)
        overlays = render_overlays(frame_path, overlays_dir, args.position_y)
        report["frames"].append(
            {
                "timestamp_s": timestamp,
                "frame": str(frame_path.relative_to(ROOT)),
                "measurement": measurement,
                "overlays": overlays,
            }
        )

    summary_path = args.out_dir / "report.json"
    summary_path.write_text(json.dumps(report, indent=2))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Wrote {summary_path}")
        for entry in report["frames"]:
            measurement = entry["measurement"] or {}
            print(
                f"  t={entry['timestamp_s']}s center_y={measurement.get('center_y')} "
                f"block_h={measurement.get('block_h_px')}px"
            )
        print("Overlay QA PNGs in", overlays_dir.relative_to(ROOT))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
