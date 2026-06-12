#!/usr/bin/env python3
"""
Benchmark Riverside reference clips against Cliptime tier targets.

Usage:
  uv run python scripts/benchmark_riverside.py [--samples-dir PATH]

With only sample clips (no full source video), reports duration distribution.
When a source video path is passed via --source, future versions can align
boundaries to transcript timestamps.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Riverside reference targets (seconds)
RIVERSIDE_TARGET_MIN = 12
RIVERSIDE_TARGET_TYPICAL_LOW = 44
RIVERSIDE_TARGET_TYPICAL_HIGH = 63
RIVERSIDE_TARGET_MAX = 90

CLIPTIME_MICRO_MAX = 30
CLIPTIME_DEEP_MAX = 90


def probe_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def classify_clip(duration: float) -> str:
    if duration <= CLIPTIME_MICRO_MAX:
        return "micro_hook"
    if duration <= CLIPTIME_DEEP_MAX:
        return "deep_context"
    return "over_tier"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Riverside sample clips")
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "riverside samples",
        help="Directory containing Riverside reference .mp4 clips",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Optional full source recording for timestamp alignment (not yet implemented)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    samples_dir: Path = args.samples_dir
    if not samples_dir.is_dir():
        print(f"Samples directory not found: {samples_dir}", file=sys.stderr)
        return 1

    clips = sorted(samples_dir.glob("*.mp4"))
    if not clips:
        print(f"No .mp4 files in {samples_dir}", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for clip in clips:
        duration = probe_duration_seconds(clip)
        rows.append(
            {
                "file": clip.name,
                "duration_seconds": round(duration, 1),
                "tier": classify_clip(duration),
                "within_riverside_range": RIVERSIDE_TARGET_MIN <= duration <= RIVERSIDE_TARGET_MAX,
                "within_cliptime_tiers": duration <= CLIPTIME_DEEP_MAX,
            }
        )

    durations = [row["duration_seconds"] for row in rows]
    summary = {
        "sample_count": len(rows),
        "durations_seconds": durations,
        "min_seconds": min(durations),
        "max_seconds": max(durations),
        "avg_seconds": round(sum(durations) / len(durations), 1),
        "riverside_reference": {
            "shortest_observed": RIVERSIDE_TARGET_MIN,
            "typical_low": RIVERSIDE_TARGET_TYPICAL_LOW,
            "typical_high": RIVERSIDE_TARGET_TYPICAL_HIGH,
            "longest_observed": RIVERSIDE_TARGET_TYPICAL_HIGH,
            "hard_max": RIVERSIDE_TARGET_MAX,
        },
        "cliptime_tiers": {
            "micro_max": CLIPTIME_MICRO_MAX,
            "deep_max": CLIPTIME_DEEP_MAX,
        },
        "clips": rows,
        "source_provided": args.source is not None,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print(f"Riverside samples: {samples_dir}")
    print(f"Clips analyzed: {len(rows)}")
    print(f"Duration range: {summary['min_seconds']}s – {summary['max_seconds']}s (avg {summary['avg_seconds']}s)")
    print()
    for row in rows:
        print(
            f"  {row['duration_seconds']:5.1f}s  [{row['tier']:13s}]  {row['file']}"
        )
    print()
    print("Cliptime targets: micro <= 30s, deep <= 90s")
    print("Riverside sweet spot: 44–63s deep-context beats, occasional 12–22s hooks")
    if args.source:
        print(f"\nSource video provided: {args.source}")
        print("Transcript alignment comparison is not implemented yet — add source to repo to enable.")
    else:
        print("\nTip: pass --source /path/to/full/recording.mp4 when available for IoU comparison.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
