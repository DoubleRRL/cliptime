from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.services.task_service import TaskService


@pytest.mark.asyncio
async def test_get_clip_transcript_words_returns_relative_timings(tmp_path: Path):
    service = TaskService(db=AsyncMock())
    service.clip_repo.get_clip_by_id = AsyncMock(
        return_value={
            "id": "clip-1",
            "task_id": "task-1",
            "start_time": "00:10",
            "end_time": "00:12",
        }
    )
    service.task_repo.get_task_by_id = AsyncMock(return_value={"id": "task-1"})
    service._resolve_task_transcript_and_video = AsyncMock(
        return_value=("transcript", tmp_path / "source.mp4")
    )

    cache = {
        "words": [
            {"text": "Hello", "start": 9_500, "end": 10_200},
            {"text": "world", "start": 10_200, "end": 11_000},
            {"text": "outside", "start": 12_500, "end": 13_000},
        ]
    }

    with patch("src.services.task_service.load_cached_transcript_data", return_value=cache):
        words = await service.get_clip_transcript_words("task-1", "clip-1")

    assert len(words) == 2
    assert words[0]["text"] == "Hello"
    assert words[0]["start"] == pytest.approx(0.0)
    assert words[0]["end"] == pytest.approx(0.2)
    assert words[1]["text"] == "world"
    assert words[1]["start"] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_get_clip_transcript_words_empty_when_no_cache(tmp_path: Path):
    service = TaskService(db=AsyncMock())
    service.clip_repo.get_clip_by_id = AsyncMock(
        return_value={
            "id": "clip-1",
            "task_id": "task-1",
            "start_time": "00:00",
            "end_time": "00:05",
        }
    )
    service.task_repo.get_task_by_id = AsyncMock(return_value={"id": "task-1"})
    service._resolve_task_transcript_and_video = AsyncMock(
        return_value=("transcript", tmp_path / "source.mp4")
    )

    with patch("src.services.task_service.load_cached_transcript_data", return_value=None):
        words = await service.get_clip_transcript_words("task-1", "clip-1")

    assert words == []
