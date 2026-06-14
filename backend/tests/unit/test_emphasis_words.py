"""Tests for emphasis word detection heuristics."""

from unittest.mock import AsyncMock

import pytest

from src.ai import _heuristic_emphasis_words, detect_emphasis_words


def test_heuristic_emphasis_words_prefers_punchy_tokens():
    words = ["so", "basically", "INSANE", "right"]
    result = _heuristic_emphasis_words(words)
    assert "INSANE" in result


@pytest.mark.asyncio
async def test_detect_emphasis_words_empty():
    assert await detect_emphasis_words("", []) == []


@pytest.mark.asyncio
async def test_detect_emphasis_words_uses_heuristic_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr("src.ai.effective_llm", lambda: "ollama:test")
    monkeypatch.setattr("src.ai._ollama_json_request", AsyncMock(return_value=None))

    result = await detect_emphasis_words(
        "this is INSANE honestly",
        ["this", "is", "INSANE", "honestly"],
    )
    assert result
    assert any(word.upper() == "INSANE" for word in result)
