#!/usr/bin/env python3
"""
Verify tight-cut subtitle placement on the clip_2 regression slice.

Usage:
  uv run python scripts/verify_tight_cut_subtitles.py              # render + assert
  uv run python scripts/verify_tight_cut_subtitles.py --skip-render --video path/to/clip.mp4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLIP = ROOT / "uploads/clips/clip_2_1251-1304.mp4"
DEFAULT_OUT_DIR = ROOT / "uploads/clips/verify-subtitles"
DEFAULT_START = 771.0
DEFAULT_END = 784.0
SCAN_STEP_S = 0.5
SUBSTANTIAL_MIN_H_PX = 120
SOLO_MIN_Y = 0.68
DUAL_MIN_Y = 0.42
DUAL_MAX_Y = 0.58


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_duration_s(video: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


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


def detect_karaoke_center_y(frame_path: Path) -> float | None:
    """Return normalized Y of the active purple karaoke highlight, if present."""
    rgb = np.array(Image.open(frame_path).convert("RGB"))
    height = rgb.shape[0]
    mask = (
        (rgb[:, :, 0] > 100)
        & (rgb[:, :, 1] < 120)
        & (rgb[:, :, 2] > 150)
    )
    ys, _xs = np.where(mask)
    if len(ys) < 20:
        return None
    return round((int(ys.min()) + int(ys.max())) / 2 / height, 4)


def measure_caption_block(frame_path: Path) -> dict | None:
    """Detect caption pill geometry; scan full caption band including dual seam."""
    rgb = np.array(Image.open(frame_path).convert("RGB"))
    height, width = rgb.shape[:2]
    row_scores: list[tuple[int, float]] = []

    for y in range(int(height * 0.30), int(height * 0.92)):
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
        "center_y": round((top + bottom) / 2 / height, 4),
    }


def detect_pill_center_y(frame_path: Path) -> float | None:
    """Return normalized Y of the strongest compact caption pill band."""
    rgb = np.array(Image.open(frame_path).convert("RGB"))
    height = rgb.shape[0]
    row_scores: list[tuple[int, float]] = []

    for y in range(int(height * 0.30), int(height * 0.92)):
        row = rgb[y]
        gray = row.mean(axis=1)
        dark = gray < 85
        bright = gray > 215
        score = float(dark.mean() * bright.mean())
        if score > 0.001:
            row_scores.append((y, score))

    if not row_scores:
        return None

    groups: list[tuple[int, int, float]] = []
    start = row_scores[0][0]
    prev = row_scores[0][0]
    peak = row_scores[0][1]
    for y, score in row_scores[1:]:
        if y - prev > 12:
            groups.append((start, prev, peak))
            start = y
            peak = score
        else:
            peak = max(peak, score)
        prev = y
    groups.append((start, prev, peak))

    compact = [
        (top, bottom, peak)
        for top, bottom, peak in groups
        if 12 <= bottom - top + 1 <= 220
    ]
    if not compact:
        compact = [(top, bottom, peak) for top, bottom, peak in groups if bottom - top + 1 >= 12]
    if not compact:
        return None

    top, bottom, _peak = max(compact, key=lambda group: group[2])
    return round((top + bottom) / 2 / height, 4)


def classify_zone(center_y: float) -> str:
    if center_y >= SOLO_MIN_Y:
        return "solo"
    if DUAL_MIN_Y <= center_y <= DUAL_MAX_Y:
        return "dual"
    if center_y < DUAL_MIN_Y:
        return "high"
    return "forbidden"


def scan_video(video: Path, frames_dir: Path, prefix: str) -> list[dict]:
    duration = video_duration_s(video)
    entries: list[dict] = []
    timestamp = SCAN_STEP_S
    while timestamp < duration - 0.05:
        frame_path = frames_dir / f"{prefix}_t{timestamp:.1f}s.jpg"
        extract_frame(video, timestamp, frame_path)
        measurement = measure_caption_block(frame_path)
        karaoke_y = detect_karaoke_center_y(frame_path)
        pill_y = detect_pill_center_y(frame_path)
        if measurement and karaoke_y is not None:
            measurement["karaoke_center_y"] = karaoke_y
            measurement["center_y"] = karaoke_y
            measurement["zone"] = classify_zone(karaoke_y)
        elif measurement and pill_y is not None:
            measurement["pill_center_y"] = pill_y
            measurement["center_y"] = pill_y
            measurement["zone"] = classify_zone(pill_y)
        elif measurement:
            measurement["zone"] = classify_zone(measurement["center_y"])
        if measurement:
            entries.append(
                {
                    "timestamp_s": round(timestamp, 1),
                    "frame": str(frame_path.relative_to(ROOT)),
                    "measurement": measurement,
                }
            )
        timestamp += SCAN_STEP_S
    return entries


def evaluate(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    substantial = [
        entry
        for entry in entries
        if entry.get("measurement")
        and (
            entry["measurement"].get("karaoke_center_y") is not None
            or entry["measurement"].get("pill_center_y") is not None
            or entry["measurement"].get("block_h_px", 0) >= SUBSTANTIAL_MIN_H_PX
        )
    ]

    if not substantial:
        errors.append("no substantial caption frames detected during scan")
        return errors

    zones = {entry["measurement"]["zone"] for entry in substantial}
    if "solo" not in zones:
        errors.append("no substantial solo-band captions (center_y >= 0.68)")
    if "dual" not in zones:
        errors.append("no substantial dual-band captions (0.42 <= center_y <= 0.58)")

    forbidden = [
        entry
        for entry in substantial
        if entry["measurement"]["zone"] == "forbidden"
    ]
    for entry in forbidden:
        timestamp_s = entry["timestamp_s"]
        neighbors = [
            other
            for other in substantial
            if other is not entry and abs(other["timestamp_s"] - timestamp_s) <= 0.75
        ]
        if neighbors and any(
            other["measurement"]["zone"] != "forbidden" for other in neighbors
        ):
            continue
        measurement = entry["measurement"]
        errors.append(
            "forbidden caption placement "
            f"t={timestamp_s}s center_y={measurement['center_y']} "
            f"h={measurement['block_h_px']}px"
        )

    for zone_name in ("solo", "dual"):
        zone_heights = [
            entry["measurement"]["block_h_px"]
            for entry in substantial
            if entry["measurement"]["zone"] == zone_name
            and entry["measurement"].get("karaoke_center_y") is None
            and entry["measurement"].get("pill_center_y") is None
            and SUBSTANTIAL_MIN_H_PX
            <= entry["measurement"].get("block_h_px", 0)
            <= 250
        ]
        if len(zone_heights) < 2:
            continue
        avg = sum(zone_heights) / len(zone_heights)
        if avg > 0:
            max_dev = max(abs(height - avg) / avg for height in zone_heights)
            if max_dev > 0.35:
                errors.append(
                    f"{zone_name} caption height variance {max_dev:.0%} exceeds 25%: "
                    f"{zone_heights}"
                )

    late_dual = [
        entry
        for entry in substantial
        if entry["timestamp_s"] >= 9.0
        and entry["measurement"]["zone"] == "dual"
    ]
    for entry in late_dual:
        measurement = entry["measurement"]
        errors.append(
            "dual-band caption on late solo segment "
            f"t={entry['timestamp_s']}s center_y={measurement['center_y']}"
        )

    return errors


def find_source_with_cache() -> Path:
    uploads = ROOT / "uploads/uploads"
    candidates = sorted(
        uploads.glob("*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        if candidate.with_suffix(".transcript_cache.json").is_file():
            return candidate
    raise FileNotFoundError(
        f"No upload with .transcript_cache.json under {uploads}"
    )


def render_clip(source: Path, output: Path, start: float, end: float) -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    from src.video_utils import create_optimized_clip

    output.parent.mkdir(parents=True, exist_ok=True)
    ok = create_optimized_clip(
        source,
        start,
        end,
        output,
        add_subtitles=True,
        caption_template="riverside",
        font_family="TikTokSans-Regular",
        font_size=32,
        tight_cuts=True,
    )
    if not ok:
        raise RuntimeError(f"create_optimized_clip failed for {source}")


def pick_representative_frame(entries: list[dict], *, zone: str) -> dict | None:
    matches = [
        entry
        for entry in entries
        if entry.get("measurement")
        and entry["measurement"].get("block_h_px", 0) >= SUBSTANTIAL_MIN_H_PX
        and entry["measurement"].get("zone") == zone
    ]
    if not matches:
        return None
    if zone == "solo":
        return max(matches, key=lambda row: row["measurement"]["center_y"])
    return min(
        matches,
        key=lambda row: abs(row["measurement"]["center_y"] - 0.50),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify tight-cut subtitle placement")
    parser.add_argument("--video", type=Path, default=DEFAULT_CLIP)
    parser.add_argument("--source-video", type=Path, default=None)
    parser.add_argument("--start-sec", type=float, default=DEFAULT_START)
    parser.add_argument("--end-sec", type=float, default=DEFAULT_END)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Only analyze --video (baseline or post-rerender check)",
    )
    parser.add_argument(
        "--save-before",
        action="store_true",
        help="Save before_* artifacts from --video before rendering",
    )
    args = parser.parse_args()
    args.video = args.video.resolve()
    if args.source_video is not None:
        args.source_video = args.source_video.resolve()
    args.out_dir = args.out_dir.resolve()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "skip_render": args.skip_render,
        "passed": False,
        "errors": [],
    }

    target_video = args.video
    if args.save_before and args.video.is_file():
        before_frames = scan_video(args.video, args.out_dir, "before")
        report["before"] = {
            "video": str(args.video.relative_to(ROOT)),
            "sha256": sha256_file(args.video),
            "mtime": args.video.stat().st_mtime,
            "frames": before_frames,
        }
        solo = pick_representative_frame(before_frames, zone="solo")
        if solo:
            src = ROOT / solo["frame"]
            dest = args.out_dir / "before_solo_t9.jpg"
            dest.write_bytes(src.read_bytes())

    if not args.skip_render:
        source = args.source_video or find_source_with_cache()
        temp_out = args.out_dir / ".verify_tight_cut_subtitles.mp4"
        print(f"Rendering {args.start_sec}-{args.end_sec}s from {source.name} ...")
        render_clip(source, temp_out, args.start_sec, args.end_sec)
        target_video = temp_out
        report["render"] = {
            "source": str(source.relative_to(ROOT)),
            "output": str(temp_out.relative_to(ROOT)),
            "sha256": sha256_file(temp_out),
        }

    if not target_video.is_file():
        print(f"Video not found: {target_video}", file=sys.stderr)
        return 1

    prefix = "after" if not args.skip_render else "check"
    frames = scan_video(target_video, args.out_dir, prefix)
    solo = pick_representative_frame(frames, zone="solo")
    if solo:
        src = ROOT / solo["frame"]
        (args.out_dir / "after_solo_t9.jpg").write_bytes(src.read_bytes())

    report["video"] = {
        "path": str(target_video.relative_to(ROOT)),
        "sha256": sha256_file(target_video),
        "mtime": target_video.stat().st_mtime,
        "frames": frames,
    }

    errors = evaluate(frames)
    report["errors"] = errors
    report["passed"] = not errors

    report_path = args.out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2))

    for entry in frames:
        measurement = entry.get("measurement") or {}
        if measurement.get("block_h_px", 0) >= SUBSTANTIAL_MIN_H_PX:
            print(
                f"  t={entry['timestamp_s']}s center_y={measurement.get('center_y')} "
                f"block_h={measurement.get('block_h_px')}px "
                f"zone={measurement.get('zone')}"
            )

    if errors:
        print("FAIL:")
        for error in errors:
            print(f"  - {error}")
        print(f"Report: {report_path}")
        return 1

    print(f"PASS — report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
