"""Tests for timestamp and safe-int parsing of LLM output."""

import pytest

from src.ai import (
    TranscriptSegment,
    ViralityAnalysis,
    _parse_segment_list,
    rerank_candidates,
)
from src.timestamp_parse import (
    parse_timestamp_or_range,
    parse_timestamp_to_seconds,
    resolve_segment_timestamps,
    safe_int,
)


def test_parse_timestamp_or_range_minute_range():
    start, end = parse_timestamp_or_range("09 - 10")
    assert start == 540
    assert end == 600


def test_parse_timestamp_or_range_clock_range():
    start, end = parse_timestamp_or_range("09:00 - 10:00")
    assert start == 540
    assert end == 600


def test_parse_timestamp_or_range_single_mmss():
    start, end = parse_timestamp_or_range("09:15")
    assert start == 555
    assert end is None


def test_safe_int_rejects_range_string():
    assert safe_int("09 - 10", default=10) == 10


def test_resolve_segment_timestamps_combined_range():
    start, end = resolve_segment_timestamps("09 - 10", "00:00")
    assert start == 540
    assert end == 600


def test_parse_timestamp_to_seconds_range_returns_start():
    assert parse_timestamp_to_seconds("09 - 10") == 540.0


def test_parse_segment_list_reads_flat_virality_fields():
    raw = [
        {
            "start_time": "01:30",
            "end_time": "02:00",
            "text": "one two three four five",
            "relevance_score": 0.9,
            "hook_score": 22,
            "engagement_score": 21,
            "value_score": 18,
            "shareability_score": 19,
            "virality_score": 80,
            "hook_type": "story",
        }
    ]
    segments = _parse_segment_list(raw)
    assert len(segments) == 1
    assert segments[0].virality.hook_score == 22
    assert segments[0].virality.total_score == 80


def test_parse_segment_list_handles_range_start_time():
    raw = [
        {
            "start_time": "09 - 10",
            "end_time": "00:00",
            "text": "one two three four five",
            "relevance_score": 0.8,
            "virality": {
                "hook_score": "09 - 10",
                "engagement_score": 12,
                "value_score": 11,
                "shareability_score": 10,
                "total_score": 43,
                "hook_type": "none",
                "virality_reasoning": "test",
            },
        }
    ]
    segments = _parse_segment_list(raw)
    assert len(segments) == 1
    assert segments[0].start_time == "09:00"
    assert segments[0].end_time == "10:00"
    assert segments[0].virality.hook_score == 10


@pytest.mark.asyncio
async def test_rerank_candidates_malformed_id(monkeypatch):
    async def fake_json_request(system, prompt, num_predict=2048):
        return {
            "ranked_ids": [0],
            "scores": [{"id": "09 - 10", "hook_score": 20, "engagement_score": 20, "value_score": 20, "shareability_score": 20, "total_score": 80}],
        }

    monkeypatch.setattr("src.ai._ollama_json_request", fake_json_request)

    virality = ViralityAnalysis(
        hook_score=10,
        engagement_score=10,
        value_score=10,
        shareability_score=10,
        total_score=40,
        hook_type="none",
        virality_reasoning="test",
    )
    candidates = [
        TranscriptSegment(
            start_time="01:00",
            end_time="01:20",
            text="one two three four five",
            relevance_score=0.9,
            reasoning="test",
            virality=virality,
        )
    ]

    result = await rerank_candidates(candidates)
    assert len(result) == 1
    assert result[0].start_time == "01:00"
