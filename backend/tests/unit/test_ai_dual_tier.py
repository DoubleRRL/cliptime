"""Tests for dual-tier transcript analysis (micro_hooks + deep_context_clips)."""

from src.ai import (
    MICRO_HOOK_MAX_SECONDS,
    MICRO_HOOK_MIN_SECONDS,
    DEEP_CONTEXT_MAX_SECONDS,
    DEEP_CONTEXT_MIN_SECONDS,
    TranscriptSegment,
    TranscriptAnalysis,
    ViralityAnalysis,
    _parse_raw_analysis,
    _validate_and_finalize_analysis,
    build_transcript_analysis_prompt,
    _classify_segment_tier,
    _segment_duration_seconds,
)


def _virality() -> ViralityAnalysis:
    return ViralityAnalysis(
        hook_score=20,
        engagement_score=18,
        value_score=17,
        shareability_score=16,
        total_score=71,
        hook_type="question",
        virality_reasoning="test",
    )


def _segment(start: str, end: str, text: str = "one two three four") -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        relevance_score=0.9,
        reasoning="test reasoning",
        virality=_virality(),
    )


def test_build_transcript_analysis_prompt_includes_dual_tier_schema():
    prompt = build_transcript_analysis_prompt(
        transcript="[00:10 - 00:25] Hello world example line",
        json_only=True,
    )

    assert "micro_hooks" in prompt
    assert "deep_context_clips" in prompt
    assert "summary" in prompt
    assert "key_topics" in prompt
    assert "10-30 seconds" in prompt
    assert "30-90 seconds" in prompt


def test_parse_raw_analysis_dual_tier_buckets():
    raw = {
        "micro_hooks": [
            {
                "start_time": "00:10",
                "end_time": "00:25",
                "text": "short hook clip text here",
                "relevance_score": 0.9,
                "reasoning": "punchy",
            }
        ],
        "deep_context_clips": [
            {
                "start_time": "01:00",
                "end_time": "01:45",
                "text": "longer narrative clip text here",
                "relevance_score": 0.85,
                "reasoning": "context",
            }
        ],
        "summary": "Test summary",
        "key_topics": ["topic"],
    }

    analysis = _parse_raw_analysis(raw)

    assert len(analysis.micro_hooks) == 1
    assert len(analysis.deep_context_clips) == 1
    assert len(analysis.most_relevant_segments) == 2
    assert analysis.summary == "Test summary"


def test_parse_raw_analysis_legacy_most_relevant_segments():
    raw = {
        "most_relevant_segments": [
            {
                "start_time": "00:10",
                "end_time": "00:25",
                "text": "legacy segment text here",
                "relevance_score": 0.8,
            }
        ],
        "summary": "Legacy",
        "key_topics": ["legacy"],
    }

    analysis = _parse_raw_analysis(raw)

    assert len(analysis.most_relevant_segments) == 1


def test_classify_segment_tier_boundaries():
    assert _classify_segment_tier(MICRO_HOOK_MIN_SECONDS) == "micro_hook"
    # 30s is valid for both tiers; classifier prefers micro_hook at the boundary
    assert _classify_segment_tier(MICRO_HOOK_MAX_SECONDS) == "micro_hook"
    assert _classify_segment_tier(DEEP_CONTEXT_MIN_SECONDS + 1) == "deep_context"
    assert _classify_segment_tier(DEEP_CONTEXT_MAX_SECONDS) == "deep_context"
    assert _classify_segment_tier(5) is None
    assert _classify_segment_tier(120) is None


def test_validate_and_finalize_enforces_micro_hook_duration():
    analysis = TranscriptAnalysis(
        micro_hooks=[
            _segment("00:00", "00:05"),  # too short
            _segment("00:10", "00:25"),  # valid 15s
            _segment("00:30", "01:10"),  # too long for micro
        ],
        deep_context_clips=[],
        most_relevant_segments=[],
        summary="s",
        key_topics=["k"],
    )

    result = _validate_and_finalize_analysis(analysis)

    assert len(result.micro_hooks) == 1
    assert result.micro_hooks[0].start_time == "00:10"
    assert _segment_duration_seconds(result.micro_hooks[0]) == 15


def test_validate_and_finalize_enforces_deep_context_duration():
    analysis = TranscriptAnalysis(
        micro_hooks=[],
        deep_context_clips=[
            _segment("00:00", "00:20"),  # too short for deep
            _segment("01:00", "01:45"),  # valid 45s
            _segment("02:00", "04:00"),  # too long
        ],
        most_relevant_segments=[],
        summary="s",
        key_topics=["k"],
    )

    result = _validate_and_finalize_analysis(analysis)

    assert len(result.deep_context_clips) == 1
    assert result.deep_context_clips[0].start_time == "01:00"
    assert _segment_duration_seconds(result.deep_context_clips[0]) == 45


def test_validate_rebuckets_mislabeled_micro_hook_to_deep():
    analysis = TranscriptAnalysis(
        micro_hooks=[_segment("01:00", "01:45")],  # 45s labeled as micro
        deep_context_clips=[],
        most_relevant_segments=[],
        summary="s",
        key_topics=["k"],
    )

    result = _validate_and_finalize_analysis(analysis)

    assert len(result.micro_hooks) == 0
    assert len(result.deep_context_clips) == 1
    assert result.deep_context_clips[0].start_time == "01:00"


def test_validate_auto_classifies_legacy_segments():
    analysis = TranscriptAnalysis(
        micro_hooks=[],
        deep_context_clips=[],
        most_relevant_segments=[
            _segment("00:10", "00:25"),
            _segment("01:00", "01:45"),
        ],
        summary="s",
        key_topics=["k"],
    )

    result = _validate_and_finalize_analysis(analysis)

    assert len(result.micro_hooks) == 1
    assert len(result.deep_context_clips) == 1
    assert len(result.most_relevant_segments) == 2
