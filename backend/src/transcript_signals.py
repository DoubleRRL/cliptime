"""
Pre-LLM signal ranking for transcript utterances.

Scores formatted transcript lines with local hook heuristics and optional
AssemblyAI sentiment/entity enrichments, then selects timeline-diverse anchors
and builds small context patches for focused LLM calls.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .transcript_windows import TranscriptLine, parse_transcript_lines

FILLER_PHRASES = ("you know", "i mean", "sort of", "kind of")
FILLER_WORDS = {"um", "uh", "like", "basically", "literally", "actually"}
HOOK_OPENERS = ("what", "why", "how", "when", "did you", "have you", "do you")
CONTRAST_WORDS = ("but", "however", "actually", "instead", "yet", "though")
BOLD_CLAIM_WORDS = ("never", "always", "best", "worst", "only", "secret", "truth")
STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "its",
    "that",
    "this",
    "with",
    "as",
    "by",
    "from",
    "i",
    "you",
    "we",
    "they",
    "he",
    "she",
    "my",
    "your",
    "our",
    "their",
    "so",
    "if",
    "not",
    "just",
    "really",
    "very",
    "can",
    "will",
    "would",
    "could",
    "should",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "about",
    "into",
    "than",
    "then",
    "there",
    "here",
    "what",
    "when",
    "where",
    "who",
    "why",
    "how",
}

SPEAKER_PATTERN = re.compile(r"^Speaker\s+([A-Z0-9]+):\s*", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class RankedAnchor:
    """A high-signal utterance selected as an LLM analysis anchor."""

    line_index: int
    start_seconds: int
    end_seconds: int
    signal_score: float
    text: str
    raw: str


def _tokenize(text: str) -> List[str]:
    return [
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOPWORDS and len(token) > 2
    ]


def _filler_ratio(text: str) -> float:
    lowered = text.lower()
    words = lowered.split()
    if not words:
        return 0.0
    filler_hits = 0
    for phrase in FILLER_PHRASES:
        filler_hits += lowered.count(phrase)
    for word in words:
        if word in FILLER_WORDS:
            filler_hits += 1
    return filler_hits / max(len(words), 1)


def _compute_tfidf_boosts(lines: Sequence[TranscriptLine]) -> Dict[int, float]:
    """Distinctive in-transcript terms boost salient utterances."""
    if not lines:
        return {}

    doc_freq: Dict[str, int] = {}
    line_tokens: Dict[int, List[str]] = {}
    for idx, line in enumerate(lines):
        tokens = _tokenize(line.text)
        line_tokens[idx] = tokens
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1

    doc_count = len(lines)
    boosts: Dict[int, float] = {}
    for idx, tokens in line_tokens.items():
        if not tokens:
            boosts[idx] = 0.0
            continue
        tfidf_sum = 0.0
        for token in tokens:
            df = doc_freq.get(token, 1)
            idf = math.log((doc_count + 1) / (df + 1)) + 1.0
            tfidf_sum += (tokens.count(token) / len(tokens)) * idf
        boosts[idx] = min(4.0, tfidf_sum / 3.0)
    return boosts


def _ms_to_seconds(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value) / 1000)
    except (TypeError, ValueError):
        return None


def _sentiment_boost_for_line(
    line: TranscriptLine,
    sentiments: Sequence[Dict[str, Any]],
) -> float:
    boost = 0.0
    for row in sentiments:
        start = _ms_to_seconds(row.get("start"))
        end = _ms_to_seconds(row.get("end"))
        if start is None or end is None:
            continue
        if line.end_seconds <= start or line.start_seconds >= end:
            continue
        sentiment = str(row.get("sentiment", "")).upper()
        confidence = float(row.get("confidence", 0.5) or 0.5)
        if sentiment in {"POSITIVE", "NEGATIVE"}:
            boost = max(boost, 1.5 + confidence)
    return boost


def _entity_boost_for_line(
    line: TranscriptLine,
    entities: Sequence[Dict[str, Any]],
) -> float:
    boost = 0.0
    for row in entities:
        start = _ms_to_seconds(row.get("start"))
        end = _ms_to_seconds(row.get("end"))
        if start is None or end is None:
            continue
        if line.end_seconds <= start or line.start_seconds >= end:
            continue
        boost += 1.0
    return min(3.0, boost)


def score_utterance(
    line: TranscriptLine,
    *,
    tfidf_boost: float = 0.0,
    speaker_changed: bool = False,
    sentiment_boost: float = 0.0,
    entity_boost: float = 0.0,
) -> float:
    """Composite hook signal score for a single utterance (no LLM)."""
    text = line.text.strip()
    if not text:
        return 0.0

    lowered = text.lower()
    words = text.split()
    word_count = len(words)
    score = 0.0

    if "?" in text[:80] or lowered.startswith(HOOK_OPENERS):
        score += 3.0

    if re.search(r"\d", text):
        score += 2.0

    if any(f" {word} " in f" {lowered} " for word in CONTRAST_WORDS):
        score += 1.5

    if any(f" {word} " in f" {lowered} " for word in BOLD_CLAIM_WORDS):
        score += 1.5

    if word_count <= 15 and ("?" in text or lowered.startswith(HOOK_OPENERS)):
        score += 2.0

    filler = _filler_ratio(text)
    if filler < 0.05:
        score += 2.0
    elif filler > 0.15:
        score -= 2.0

    if word_count > 80 and "?" not in text and "!" not in text:
        score -= 2.0

    if speaker_changed and (
        "?" in text[:80] or lowered.startswith(HOOK_OPENERS) or word_count <= 20
    ):
        score += 2.0

    score += tfidf_boost
    score += sentiment_boost
    score += entity_boost

    return max(0.0, score)


def compute_anchor_count(transcript: str) -> int:
    """Scale anchor budget with recording length (~1 per 75s, capped 6–18)."""
    lines = parse_transcript_lines(transcript)
    if lines:
        total_seconds = max(line.end_seconds for line in lines)
    else:
        total_seconds = max(600, len(transcript) // 15)
    return min(18, max(6, total_seconds // 75))


def rank_transcript_utterances(
    transcript: str,
    cache: Optional[Dict[str, Any]] = None,
) -> List[RankedAnchor]:
    """Score every parsed utterance and return anchors sorted by signal strength."""
    lines = parse_transcript_lines(transcript)
    if not lines:
        return []

    tfidf_boosts = _compute_tfidf_boosts(lines)
    sentiments = (cache or {}).get("sentiment_analysis") or []
    entities = (cache or {}).get("entities") or []

    anchors: List[RankedAnchor] = []
    previous_speaker: Optional[str] = None

    for idx, line in enumerate(lines):
        speaker_match = SPEAKER_PATTERN.match(line.raw[line.raw.find("]") + 1 :].strip())
        current_speaker = speaker_match.group(1) if speaker_match else None
        speaker_changed = (
            current_speaker is not None
            and previous_speaker is not None
            and current_speaker != previous_speaker
        )
        if current_speaker is not None:
            previous_speaker = current_speaker

        signal_score = score_utterance(
            line,
            tfidf_boost=tfidf_boosts.get(idx, 0.0),
            speaker_changed=speaker_changed,
            sentiment_boost=_sentiment_boost_for_line(line, sentiments),
            entity_boost=_entity_boost_for_line(line, entities),
        )
        if signal_score <= 0.5:
            continue

        anchors.append(
            RankedAnchor(
                line_index=idx,
                start_seconds=line.start_seconds,
                end_seconds=line.end_seconds,
                signal_score=signal_score,
                text=line.text,
                raw=line.raw,
            )
        )

    anchors.sort(key=lambda anchor: anchor.signal_score, reverse=True)
    return anchors


def select_anchor_moments(
    ranked: Sequence[RankedAnchor],
    *,
    max_anchors: int,
    bucket_seconds: int = 300,
    max_per_bucket: int = 3,
    min_score: float = 1.5,
) -> List[RankedAnchor]:
    """Pick top anchors with timeline diversity and discard weak zones."""
    if not ranked:
        return []

    strong = [anchor for anchor in ranked if anchor.signal_score >= min_score]
    if not strong:
        strong = list(ranked[:max_anchors])

    bucket_counts: Dict[int, int] = {}
    selected: List[RankedAnchor] = []

    for anchor in strong:
        bucket = anchor.start_seconds // bucket_seconds
        if bucket_counts.get(bucket, 0) >= max_per_bucket:
            continue
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        selected.append(anchor)
        if len(selected) >= max_anchors:
            break

    selected.sort(key=lambda anchor: anchor.start_seconds)
    return selected


def build_patch_for_anchor(
    anchor: RankedAnchor,
    lines: Sequence[TranscriptLine],
    *,
    pad_seconds: int = 45,
    min_chars: int = 800,
    max_chars: int = 1500,
) -> str:
    """Expand an anchor to a small timestamped patch for a focused LLM call."""
    if not lines:
        return anchor.raw

    window_start = max(0, anchor.start_seconds - pad_seconds)
    window_end = anchor.end_seconds + pad_seconds

    selected = [
        line
        for line in lines
        if line.end_seconds > window_start and line.start_seconds < window_end
    ]
    if not selected:
        return anchor.raw

    patch_lines = [line.raw for line in selected]
    patch = "\n".join(patch_lines)

    if len(patch) > max_chars:
        anchor_idx = next(
            (idx for idx, line in enumerate(selected) if line.raw == anchor.raw),
            len(selected) // 2,
        )
        trimmed: List[str] = [selected[anchor_idx].raw]
        left = anchor_idx - 1
        right = anchor_idx + 1
        while len("\n".join(trimmed)) < max_chars and (left >= 0 or right < len(selected)):
            if left >= 0:
                trimmed.insert(0, selected[left].raw)
                left -= 1
            if len("\n".join(trimmed)) >= max_chars:
                break
            if right < len(selected):
                trimmed.append(selected[right].raw)
                right += 1
        patch = "\n".join(trimmed)
        if len(patch) > max_chars:
            patch = patch[:max_chars]

    if len(patch) < min_chars:
        expanded_start = max(0, anchor.start_seconds - pad_seconds * 2)
        expanded_end = anchor.end_seconds + pad_seconds * 2
        expanded = [
            line.raw
            for line in lines
            if line.end_seconds > expanded_start and line.start_seconds < expanded_end
        ]
        patch = "\n".join(expanded)
        if len(patch) > max_chars:
            patch = patch[:max_chars]

    return patch


def build_signal_first_patches(
    transcript: str,
    cache: Optional[Dict[str, Any]] = None,
    *,
    max_anchors: Optional[int] = None,
    pad_seconds: int = 45,
    max_chars: int = 1500,
) -> tuple[List[RankedAnchor], List[str]]:
    """Rank utterances, select diverse anchors, and build per-anchor patches."""
    lines = parse_transcript_lines(transcript)
    ranked = rank_transcript_utterances(transcript, cache=cache)
    anchor_count = max_anchors or compute_anchor_count(transcript)
    anchors = select_anchor_moments(ranked, max_anchors=anchor_count)
    patches = [
        build_patch_for_anchor(
            anchor,
            lines,
            pad_seconds=pad_seconds,
            max_chars=max_chars,
        )
        for anchor in anchors
    ]
    return anchors, patches
