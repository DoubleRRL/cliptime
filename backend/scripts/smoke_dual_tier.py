#!/usr/bin/env python3
"""Smoke test for dual-tier transcript analysis (no video render required)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.ai import (  # noqa: E402
    _parse_raw_analysis,
    _validate_and_finalize_analysis,
    build_transcript_analysis_prompt,
    get_most_relevant_parts_by_transcript,
)


SAMPLE_TRANSCRIPT = "\n".join(
    [
        "[00:00 - 00:12] Speaker A: Welcome back to the show everyone.",
        "[00:12 - 00:28] Speaker A: The one mistake that kills most startups is hiring too fast.",
        "[00:28 - 00:45] Speaker B: That is a bold claim. What evidence do you have?",
        "[00:45 - 01:30] Speaker A: We studied forty companies over three years and the pattern is clear.",
        "[01:30 - 02:15] Speaker B: Walk us through the framework you used and the biggest surprise.",
        "[02:15 - 03:00] Speaker A: The surprise was that culture debt compounds faster than technical debt.",
    ]
)

SAMPLE_OLLAMA_JSON = {
    "micro_hooks": [
        {
            "start_time": "00:12",
            "end_time": "00:28",
            "text": "The one mistake that kills most startups is hiring too fast.",
            "relevance_score": 0.95,
            "reasoning": "Strong hook with a contrarian claim.",
        },
        {
            "start_time": "02:15",
            "end_time": "02:35",
            "text": "The surprise was that culture debt compounds faster than technical debt.",
            "relevance_score": 0.9,
            "reasoning": "Memorable insight suitable for shorts.",
        },
    ],
    "deep_context_clips": [
        {
            "start_time": "00:45",
            "end_time": "01:30",
            "text": "We studied forty companies over three years and the pattern is clear.",
            "relevance_score": 0.88,
            "reasoning": "Provides study context and credibility.",
        }
    ],
    "summary": "Founders discuss hiring mistakes and culture debt.",
    "key_topics": ["startups", "hiring", "culture debt"],
}


def smoke_parse_and_validate() -> None:
    print("==> parse + tier validation (offline fixture)")
    analysis = _parse_raw_analysis(SAMPLE_OLLAMA_JSON)
    final = _validate_and_finalize_analysis(analysis)

    assert len(final.micro_hooks) >= 1, "expected at least one micro_hook"
    assert len(final.deep_context_clips) >= 1, "expected at least one deep_context_clip"
    assert len(final.most_relevant_segments) == len(final.micro_hooks) + len(
        final.deep_context_clips
    )

    for segment in final.micro_hooks:
        start_m, start_s = map(int, segment.start_time.split(":"))
        end_m, end_s = map(int, segment.end_time.split(":"))
        duration = (end_m * 60 + end_s) - (start_m * 60 + start_s)
        assert 10 <= duration <= 30, f"micro_hook duration out of range: {duration}s"

    for segment in final.deep_context_clips:
        start_m, start_s = map(int, segment.start_time.split(":"))
        end_m, end_s = map(int, segment.end_time.split(":"))
        duration = (end_m * 60 + end_s) - (start_m * 60 + start_s)
        assert 30 <= duration <= 90, f"deep_context duration out of range: {duration}s"

    print(
        f"    OK: {len(final.micro_hooks)} micro_hooks, "
        f"{len(final.deep_context_clips)} deep_context_clips"
    )


async def smoke_live_ollama_if_configured() -> bool:
    llm = os.getenv("LLM", "")
    if not llm.startswith("ollama:"):
        print("==> live Ollama call skipped (set LLM=ollama:<model> to enable)")
        return True

    print(f"==> live Ollama analysis ({llm})")
    prompt = build_transcript_analysis_prompt(SAMPLE_TRANSCRIPT, json_only=True)
    assert "micro_hooks" in prompt and "deep_context_clips" in prompt

    try:
        result = await get_most_relevant_parts_by_transcript(SAMPLE_TRANSCRIPT)
    except RuntimeError as exc:
        print(f"    WARN: live Ollama call failed: {exc}")
        print("    Offline parse/validation passed; pull a JSON-capable model (e.g. llama3.1:8b).")
        return False

    print(
        f"    OK: {len(result.micro_hooks)} micro_hooks, "
        f"{len(result.deep_context_clips)} deep_context_clips, "
        f"{len(result.most_relevant_segments)} total"
    )
    print(f"    summary: {result.summary[:80]}...")
    return True


def main() -> int:
    smoke_parse_and_validate()
    live_ok = asyncio.run(smoke_live_ollama_if_configured())
    print("Smoke test passed (offline dual-tier validation).")
    if not live_ok:
        print("Note: live Ollama step did not pass; fix LLM model or OLLAMA_BASE_URL for full E2E.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
