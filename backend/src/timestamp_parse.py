"""Shared timestamp and safe integer parsing for LLM output."""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_RANGE_SPLIT = re.compile(r"\s*-\s*")


def safe_int(
    value: object,
    default: int = 0,
    *,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
) -> int:
    """Parse int from LLM output; tolerate ranges and garbage."""
    if value is None:
        result = default
    elif isinstance(value, bool):
        result = int(value)
    elif isinstance(value, int):
        result = value
    elif isinstance(value, float):
        result = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.replace(".", "").isdigit():
            result = int(float(stripped))
        else:
            result = default
    else:
        try:
            result = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            result = default

    if min_val is not None:
        result = max(min_val, result)
    if max_val is not None:
        result = min(max_val, result)
    return result


def _strip_brackets(ts: str) -> str:
    return ts.strip().strip("[]").strip()


def _parse_single_timestamp_component(part: str) -> int:
    """Parse MM:SS, HH:MM:SS, bare minutes, or seconds."""
    part = part.strip()
    if not part:
        return 0

    if part.replace(".", "").isdigit() and ":" not in part:
        numeric = float(part)
        # Bare numbers under 1000 without colons: treat as seconds if >= 60 else minutes
        if numeric < 60 and "." not in part:
            return int(numeric * 60)
        return int(numeric)

    if ":" in part:
        segments = part.split(":")
        try:
            if len(segments) == 2:
                return int(segments[0]) * 60 + int(segments[1])
            if len(segments) == 3:
                return (
                    int(segments[0]) * 3600
                    + int(segments[1]) * 60
                    + int(segments[2])
                )
        except ValueError:
            logger.warning("Failed to parse timestamp component: %s", part)
            return 0

    if part.isdigit():
        return int(part) * 60

    return 0


def parse_timestamp_or_range(ts: str) -> Tuple[int, Optional[int]]:
    """
    Parse MM:SS, HH:MM:SS, or range forms like '09 - 10', '09:00 - 10:00'.
    Returns (start_seconds, end_seconds|None).
    """
    cleaned = _strip_brackets(ts)
    if not cleaned:
        return 0, None

    if " - " in cleaned or _RANGE_SPLIT.search(cleaned):
        parts = _RANGE_SPLIT.split(cleaned, maxsplit=1)
        if len(parts) == 2:
            start = _parse_single_timestamp_component(parts[0])
            end = _parse_single_timestamp_component(parts[1])
            return start, end

    return _parse_single_timestamp_component(cleaned), None


def resolve_segment_timestamps(start_raw: str, end_raw: str) -> Tuple[int, int]:
    """Resolve start/end seconds from LLM fields, including combined ranges."""
    start_s, start_end = parse_timestamp_or_range(start_raw)
    end_s, end_end = parse_timestamp_or_range(end_raw)

    if start_end is not None:
        return start_s, start_end
    if end_end is not None:
        return end_s, end_end
    return start_s, end_s


def seconds_to_mmss(total: int) -> str:
    total = max(0, total)
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_timestamp_to_seconds(ts: str) -> float:
    """Parse a timestamp or range string to seconds (start if range)."""
    start, end = parse_timestamp_or_range(ts.strip())
    return float(start if end is None else start)


def parse_timestamp_range_to_seconds(ts: str) -> Tuple[float, Optional[float]]:
    """Parse timestamp; return (start_seconds, end_seconds_or_none)."""
    start, end = parse_timestamp_or_range(ts.strip())
    return float(start), float(end) if end is not None else None
