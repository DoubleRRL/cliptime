"""Tests for render-time segment duration clamping."""

from src.services.video_service import VideoService


def test_clamp_deep_context_over_90_seconds():
    segment = {
        "start_time": "00:00",
        "end_time": "06:00",
        "text": "Long monologue that should be trimmed.",
        "clip_type": "deep_context",
    }
    clamped = VideoService.clamp_segment_timestamps(segment)
    assert clamped["start_time"] == "00:00"
    assert clamped["end_time"] == "01:30"


def test_clamp_micro_hook_over_30_seconds():
    segment = {
        "start_time": "02:00",
        "end_time": "03:00",
        "text": "Hook that runs too long for micro tier.",
        "clip_type": "micro_hook",
    }
    clamped = VideoService.clamp_segment_timestamps(segment)
    assert clamped["start_time"] == "02:00"
    assert clamped["end_time"] == "02:30"


def test_clamp_leaves_valid_segment_unchanged():
    segment = {
        "start_time": "01:00",
        "end_time": "01:45",
        "text": "Valid deep context clip in Riverside range.",
        "clip_type": "deep_context",
    }
    clamped = VideoService.clamp_segment_timestamps(segment)
    assert clamped["end_time"] == "01:45"
