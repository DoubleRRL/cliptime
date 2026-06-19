"""
Jump-cut helpers: remove filler words and dead silence using word timestamps.

Used during clip render to produce tighter comedy/podcast clips without LLM changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .layout_director import REACTION_RE
from .transcript_signals import FILLER_PHRASES, FILLER_WORDS

TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class KeepSpan:
    """Inclusive source-video time range to keep (milliseconds)."""

    src_start_ms: int
    src_end_ms: int

    @property
    def duration_ms(self) -> int:
        return max(0, self.src_end_ms - self.src_start_ms)


@dataclass
class TightCutsConfig:
    enabled: bool = True
    max_silence_ms: int = 350
    word_pad_before_ms: int = 80
    word_pad_after_ms: int = 120
    min_keep_ms: int = 120
    min_output_duration_s: float = 1.5
    preserve_reactions: bool = True
    preserve_punchline_pause_ms: int = 400
    merge_gap_ms: int = 200


def normalize_token(text: str) -> str:
    match = TOKEN_PATTERN.search(str(text or "").lower())
    return match.group(0) if match else ""


def is_filler_word(text: str) -> bool:
    token = normalize_token(text)
    if not token:
        return True
    if token in FILLER_WORDS:
        return True
    lowered = str(text or "").lower().strip()
    return any(phrase in lowered for phrase in FILLER_PHRASES if len(lowered.split()) <= 4)


def is_punchline_word(text: str) -> bool:
    stripped = str(text or "").strip()
    return bool(stripped) and stripped[-1] in {"!", "?"}


def _reaction_windows(
    utterances: Sequence[Dict[str, Any]],
    clip_start_ms: int,
    clip_end_ms: int,
) -> List[tuple[int, int]]:
    windows: List[tuple[int, int]] = []
    for row in utterances:
        text = str(row.get("text") or "")
        if not REACTION_RE.search(text):
            continue
        start = int(row.get("start") or 0)
        end = int(row.get("end") or start)
        if end <= clip_start_ms or start >= clip_end_ms:
            continue
        windows.append((max(start, clip_start_ms), min(end, clip_end_ms)))
    return windows


def _merge_spans(spans: List[KeepSpan], merge_gap_ms: int) -> List[KeepSpan]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda span: span.src_start_ms)
    merged: List[KeepSpan] = [ordered[0]]
    for span in ordered[1:]:
        prev = merged[-1]
        if span.src_start_ms <= prev.src_end_ms + merge_gap_ms:
            merged[-1] = KeepSpan(prev.src_start_ms, max(prev.src_end_ms, span.src_end_ms))
        else:
            merged.append(span)
    return merged


def compute_keep_spans(
    words: Sequence[Dict[str, Any]],
    clip_start_ms: int,
    clip_end_ms: int,
    config: Optional[TightCutsConfig] = None,
    utterances: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[KeepSpan]:
    """Build source-video keep spans from word timestamps inside the clip."""
    cfg = config or TightCutsConfig()
    if not cfg.enabled or clip_end_ms <= clip_start_ms:
        return [KeepSpan(clip_start_ms, clip_end_ms)]

    content_words = [
        word
        for word in words
        if int(word.get("start") or 0) < clip_end_ms
        and int(word.get("end") or 0) > clip_start_ms
        and not is_filler_word(str(word.get("text") or ""))
    ]

    if not content_words:
        return [KeepSpan(clip_start_ms, clip_end_ms)]

    reaction_windows = (
        _reaction_windows(utterances or [], clip_start_ms, clip_end_ms)
        if cfg.preserve_reactions
        else []
    )

    micro_spans: List[KeepSpan] = []
    for word in content_words:
        start = int(word.get("start") or clip_start_ms)
        end = int(word.get("end") or start)
        span_start = max(clip_start_ms, start - cfg.word_pad_before_ms)
        span_end = min(clip_end_ms, end + cfg.word_pad_after_ms)
        if is_punchline_word(str(word.get("text") or "")):
            span_end = min(clip_end_ms, span_end + cfg.preserve_punchline_pause_ms)
        for react_start, react_end in reaction_windows:
            if end < react_start or start >= react_end:
                continue
            span_start = min(span_start, react_start)
            span_end = max(span_end, react_end)
        if span_end - span_start >= cfg.min_keep_ms:
            micro_spans.append(KeepSpan(span_start, span_end))

    if not micro_spans:
        return [KeepSpan(clip_start_ms, clip_end_ms)]

    merged = _merge_spans(micro_spans, cfg.merge_gap_ms)
    return [span for span in merged if span.duration_ms >= cfg.min_keep_ms]


def output_duration_ms(keep_spans: Sequence[KeepSpan]) -> int:
    return sum(span.duration_ms for span in keep_spans)


def output_duration_s(keep_spans: Sequence[KeepSpan]) -> float:
    return output_duration_ms(keep_spans) / 1000.0


def should_apply_tight_cuts(
    keep_spans: Sequence[KeepSpan],
    clip_start_ms: int,
    clip_end_ms: int,
    config: Optional[TightCutsConfig] = None,
) -> bool:
    cfg = config or TightCutsConfig()
    if not cfg.enabled or not keep_spans:
        return False
    full_ms = max(0, clip_end_ms - clip_start_ms)
    if full_ms <= 0:
        return False
    kept_ms = output_duration_ms(keep_spans)
    if kept_ms < cfg.min_output_duration_s * 1000:
        return False
    if len(keep_spans) == 1:
        only = keep_spans[0]
        if only.src_start_ms <= clip_start_ms + 50 and only.src_end_ms >= clip_end_ms - 50:
            if kept_ms >= full_ms * 0.95:
                return False
    return kept_ms < full_ms * 0.98 or len(keep_spans) > 1


def remap_words_to_output(
    words: Sequence[Dict[str, Any]],
    keep_spans: Sequence[KeepSpan],
    clip_start_ms: int,
    span_output_durations_ms: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    """Map absolute-ms words onto the concatenated output timeline (seconds, clip-relative).

    When ``span_output_durations_ms`` is provided (encoded per-span clip lengths), word
    positions scale within each span so subtitles stay aligned with concat video.
    """
    if not keep_spans:
        return []

    content_words = [
        word
        for word in words
        if not is_filler_word(str(word.get("text") or ""))
    ]

    remapped: List[Dict[str, Any]] = []
    output_offset_ms = 0
    for index, span in enumerate(keep_spans):
        span_src_ms = span.duration_ms
        if span_src_ms <= 0:
            continue
        span_output_ms = (
            int(span_output_durations_ms[index])
            if span_output_durations_ms is not None
            and index < len(span_output_durations_ms)
            else span_src_ms
        )
        scale = span_output_ms / span_src_ms if span_src_ms else 1.0

        span_words = [
            word
            for word in content_words
            if int(word.get("start") or 0) < span.src_end_ms
            and int(word.get("end") or 0) > span.src_start_ms
        ]
        for word in span_words:
            abs_start = int(word.get("start") or span.src_start_ms)
            abs_end = int(word.get("end") or abs_start)
            rel_in_src_start = max(abs_start, span.src_start_ms) - span.src_start_ms
            rel_in_src_end = min(abs_end, span.src_end_ms) - span.src_start_ms
            rel_start_ms = output_offset_ms + int(rel_in_src_start * scale)
            rel_end_ms = output_offset_ms + int(rel_in_src_end * scale)
            if rel_end_ms <= rel_start_ms:
                continue
            remapped.append(
                {
                    "text": word.get("text"),
                    "start": rel_start_ms / 1000.0,
                    "end": rel_end_ms / 1000.0,
                    "confidence": word.get("confidence", 1.0),
                    "speaker": word.get("speaker"),
                }
            )
        output_offset_ms += span_output_ms

    remapped.sort(key=lambda row: (row["start"], row["end"]))
    return remapped


def get_absolute_words_in_range(
    transcript_data: Dict[str, Any],
    clip_start_s: float,
    clip_end_s: float,
) -> List[Dict[str, Any]]:
    """Return cached words overlapping the clip, preserving absolute millisecond times."""
    words = transcript_data.get("words") or []
    clip_start_ms = int(clip_start_s * 1000)
    clip_end_ms = int(clip_end_s * 1000)
    selected: List[Dict[str, Any]] = []
    for word_data in words:
        word_start = int(word_data.get("start") or 0)
        word_end = int(word_data.get("end") or word_start)
        if word_start < clip_end_ms and word_end > clip_start_ms:
            selected.append(dict(word_data))
    return selected
