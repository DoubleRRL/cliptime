"""
Transcript windowing and candidate merge/dedup for map-reduce clip analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .ai import TranscriptSegment, _timestamp_to_seconds

LINE_PATTERN = re.compile(
    r"^\[(?P<start>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?)\]"
)


@dataclass(frozen=True)
class TranscriptLine:
    start_seconds: int
    end_seconds: int
    text: str
    raw: str


@dataclass(frozen=True)
class TranscriptWindow:
    index: int
    start_seconds: int
    end_seconds: int
    text: str
    line_count: int


def parse_transcript_lines(transcript: str) -> List[TranscriptLine]:
    """Parse formatted transcript lines into structured objects."""
    lines: List[TranscriptLine] = []
    for raw in transcript.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        match = LINE_PATTERN.match(stripped)
        if not match:
            continue
        start_seconds = _timestamp_to_seconds(match.group("start"))
        end_seconds = _timestamp_to_seconds(match.group("end"))
        body = stripped[match.end() :].strip()
        if body.startswith("Speaker"):
            body = re.sub(r"^Speaker\s+[A-Z0-9]+:\s*", "", body)
        lines.append(
            TranscriptLine(
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                text=body,
                raw=stripped,
            )
        )
    return lines


def split_transcript_into_windows(
    transcript: str,
    window_seconds: int = 300,
    overlap_seconds: int = 30,
    max_windows: Optional[int] = None,
) -> List[TranscriptWindow]:
    """Split a timestamped transcript into utterance-aligned overlapping windows."""
    lines = parse_transcript_lines(transcript)
    if not lines:
        return [
            TranscriptWindow(
                index=0,
                start_seconds=0,
                end_seconds=window_seconds,
                text=transcript.strip(),
                line_count=0,
            )
        ]

    total_end = max(line.end_seconds for line in lines)
    if total_end <= 0:
        total_end = window_seconds

    windows: List[TranscriptWindow] = []
    cursor = 0
    index = 0
    step = max(window_seconds - overlap_seconds, 60)

    while cursor < total_end:
        window_start = cursor
        window_end = min(cursor + window_seconds, total_end)
        selected = [
            line
            for line in lines
            if line.end_seconds > window_start and line.start_seconds < window_end
        ]
        if selected:
            text = "\n".join(line.raw for line in selected)
            windows.append(
                TranscriptWindow(
                    index=index,
                    start_seconds=window_start,
                    end_seconds=window_end,
                    text=text,
                    line_count=len(selected),
                )
            )
            index += 1
            if max_windows is not None and len(windows) >= max_windows:
                break
        if window_end >= total_end:
            break
        cursor += step

    return windows or [
        TranscriptWindow(
            index=0,
            start_seconds=0,
            end_seconds=total_end,
            text="\n".join(line.raw for line in lines),
            line_count=len(lines),
        )
    ]


def _segment_bounds(segment: TranscriptSegment) -> Tuple[int, int]:
    return _timestamp_to_seconds(segment.start_time), _timestamp_to_seconds(
        segment.end_time
    )


def segment_duration_seconds(segment: TranscriptSegment) -> int:
    start, end = _segment_bounds(segment)
    return max(0, end - start)


def segment_iou(a: TranscriptSegment, b: TranscriptSegment) -> float:
    """Intersection-over-union for two timestamp spans."""
    a_start, a_end = _segment_bounds(a)
    b_start, b_end = _segment_bounds(b)
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    if overlap <= 0:
        return 0.0
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return overlap / union


def segment_contains(outer: TranscriptSegment, inner: TranscriptSegment) -> bool:
    outer_start, outer_end = _segment_bounds(outer)
    inner_start, inner_end = _segment_bounds(inner)
    return outer_start <= inner_start and inner_end <= outer_end


def _virality_score(segment: TranscriptSegment) -> float:
    if segment.virality:
        return float(segment.virality.total_score)
    return segment.relevance_score * 100.0


def _segment_key(segment: TranscriptSegment) -> Tuple[str, str]:
    return segment.start_time, segment.end_time


def deduplicate_segments(
    segments: Sequence[TranscriptSegment],
    iou_threshold: float = 0.5,
) -> List[TranscriptSegment]:
    """Remove duplicate and heavily overlapping segments, keeping higher scores."""
    ranked = sorted(segments, key=_virality_score, reverse=True)
    kept: List[TranscriptSegment] = []
    seen_keys: set[Tuple[str, str]] = set()

    for candidate in ranked:
        key = _segment_key(candidate)
        if key in seen_keys:
            continue

        overlaps = False
        for existing in kept:
            if segment_iou(candidate, existing) >= iou_threshold:
                overlaps = True
                break
            if segment_contains(existing, candidate) and _virality_score(
                existing
            ) >= _virality_score(candidate):
                overlaps = True
                break
            if segment_contains(candidate, existing) and _virality_score(
                candidate
            ) > _virality_score(existing):
                kept.remove(existing)
                seen_keys.discard(_segment_key(existing))
                break

        if overlaps:
            continue

        kept.append(candidate)
        seen_keys.add(key)

    kept.sort(key=_virality_score, reverse=True)
    return kept


def apply_diversity_cap(
    segments: Sequence[TranscriptSegment],
    bucket_seconds: int = 300,
    max_per_bucket: int = 2,
) -> List[TranscriptSegment]:
    """Limit how many clips can come from the same time bucket."""
    ranked = sorted(segments, key=_virality_score, reverse=True)
    bucket_counts: dict[int, int] = {}
    selected: List[TranscriptSegment] = []

    for segment in ranked:
        start, _ = _segment_bounds(segment)
        bucket = start // bucket_seconds
        if bucket_counts.get(bucket, 0) >= max_per_bucket:
            continue
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        selected.append(segment)

    selected.sort(key=_virality_score, reverse=True)
    return selected


def select_final_segments(
    micro_hooks: Sequence[TranscriptSegment],
    deep_context_clips: Sequence[TranscriptSegment],
    *,
    max_micro: int,
    max_deep: int,
    bucket_seconds: int = 300,
    max_per_bucket: int = 2,
) -> Tuple[List[TranscriptSegment], List[TranscriptSegment]]:
    """Merge, deduplicate, diversify, and cap each tier."""
    deduped_micro = deduplicate_segments(list(micro_hooks))
    deduped_deep = deduplicate_segments(list(deep_context_clips))

    diverse_micro = apply_diversity_cap(
        deduped_micro, bucket_seconds=bucket_seconds, max_per_bucket=max_per_bucket
    )
    diverse_deep = apply_diversity_cap(
        deduped_deep, bucket_seconds=bucket_seconds, max_per_bucket=max_per_bucket
    )

    return diverse_micro[:max_micro], diverse_deep[:max_deep]


def extract_candidate_hints(window_text: str, limit: int = 5) -> List[str]:
    """Heuristic seed timestamps to guide local models within a window."""
    hints: List[str] = []
    for raw in window_text.splitlines():
        match = LINE_PATTERN.match(raw.strip())
        if not match:
            continue
        body = raw[match.end() :].strip()
        if "?" in body[:80] or body.lower().startswith(
            ("what", "why", "how", "when", "did you", "have you")
        ):
            hints.append(match.group("start"))
        if len(hints) >= limit:
            break
    return hints
