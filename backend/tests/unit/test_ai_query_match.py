"""Tests for user-query clip discovery."""

from src.ai import (
    DEEP_CONTEXT_MAX_SECONDS,
    DEEP_CONTEXT_MIN_SECONDS,
    MICRO_HOOK_MAX_SECONDS,
    MICRO_HOOK_MIN_SECONDS,
    QueryMatchResult,
    ViralityAnalysis,
    _extract_transcript_excerpt,
    _parse_query_match_result,
    _parse_query_match_variant,
    build_query_match_prompt,
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


def test_build_query_match_prompt_includes_clip_types():
    prompt = build_query_match_prompt(
        "[00:10 - 00:25] Example line about walking",
        "ass cheeks to walk",
        ["micro_hook", "deep_context"],
    )

    assert "micro_hook" in prompt
    assert "deep_context" in prompt
    assert "ass cheeks to walk" in prompt


def test_extract_transcript_excerpt_favors_matching_lines():
    transcript = "\n".join(
        [
            "[00:00 - 00:05] unrelated intro",
            "[00:10 - 00:20] do we really need ass cheeks to walk",
            "[00:30 - 00:40] another unrelated line",
        ]
    )

    excerpt = _extract_transcript_excerpt(transcript, "ass cheeks to walk", window_lines=5)
    assert "ass cheeks" in excerpt


def test_parse_query_match_result_dual_variants_from_anchor():
    raw = {
        "anchor_quote": "do we really need ass cheeks to walk",
        "variants": [
            {
                "clip_type": "micro_hook",
                "start_time": "00:10",
                "end_time": "00:25",
                "text": "do we really need ass cheeks to walk around",
                "relevance_score": 0.92,
                "quality_verdict": "strong",
                "quality_reasoning": "Exact quote match",
                "reasoning": "Punchy question hook",
                "virality": _virality().model_dump(),
            },
            {
                "clip_type": "deep_context",
                "start_time": "00:05",
                "end_time": "00:55",
                "text": "setup and the ass cheeks walking question with payoff",
                "relevance_score": 0.88,
                "quality_verdict": "fair",
                "quality_reasoning": "Good context window",
                "reasoning": "Adds setup",
                "virality": _virality().model_dump(),
            },
        ],
    }

    result = _parse_query_match_result(raw, ["micro_hook", "deep_context"])
    assert isinstance(result, QueryMatchResult)
    assert len(result.variants) == 2
    assert result.variants[0].clip_type == "micro_hook"
    assert result.variants[1].clip_type == "deep_context"


def test_parse_query_match_variant_enforces_tier_duration():
    micro = _parse_query_match_variant(
        {
            "clip_type": "micro_hook",
            "start_time": "00:10",
            "end_time": "00:25",
            "text": "valid micro hook clip text here",
            "relevance_score": 0.9,
            "quality_verdict": "strong",
            "quality_reasoning": "ok",
            "reasoning": "ok",
            "virality": _virality().model_dump(),
        },
        "micro_hook",
    )
    assert micro is not None
    duration = (
        int(micro.segment.end_time.split(":")[0]) * 60
        + int(micro.segment.end_time.split(":")[1])
    ) - (
        int(micro.segment.start_time.split(":")[0]) * 60
        + int(micro.segment.start_time.split(":")[1])
    )
    assert MICRO_HOOK_MIN_SECONDS <= duration <= MICRO_HOOK_MAX_SECONDS

    deep = _parse_query_match_variant(
        {
            "clip_type": "deep_context",
            "start_time": "00:00",
            "end_time": "01:00",
            "text": "valid deep context clip text with enough words here",
            "relevance_score": 0.85,
            "quality_verdict": "fair",
            "quality_reasoning": "ok",
            "reasoning": "ok",
            "virality": _virality().model_dump(),
        },
        "deep_context",
    )
    assert deep is not None
    deep_duration = (
        int(deep.segment.end_time.split(":")[0]) * 60
        + int(deep.segment.end_time.split(":")[1])
    ) - (
        int(deep.segment.start_time.split(":")[0]) * 60
        + int(deep.segment.start_time.split(":")[1])
    )
    assert DEEP_CONTEXT_MIN_SECONDS <= deep_duration <= DEEP_CONTEXT_MAX_SECONDS
