"""Tests for transcript-length-scaled quality caps."""

from src.ai import _scaled_quality_caps


def test_scaled_caps_base_for_short_transcript():
    transcript = "[00:00 - 00:30] Short intro only.\n" * 5
    max_micro, max_deep = _scaled_quality_caps(transcript)
    assert max_micro == 8
    assert max_deep == 6


def test_scaled_caps_grow_for_long_transcript():
    lines = []
    for minute in range(55):
        start = minute * 60
        end = start + 30
        lines.append(
            f"[{start // 60:02d}:{start % 60:02d} - {end // 60:02d}:{end % 60:02d}] Segment {minute}"
        )
    transcript = "\n".join(lines)
    max_micro, max_deep = _scaled_quality_caps(transcript)
    assert max_micro == 12
    assert max_deep == 8
