from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.task_service import TaskService


def build_clip(**overrides) -> dict:
    base = {
        "id": "clip-1",
        "task_id": "task-1",
        "start_time": "00:10",
        "end_time": "00:20",
        "duration": 10.0,
        "text": "Sample transcript",
        "relevance_score": 0.9,
        "clip_order": 2,
        "file_path": "/tmp/clips/old.mp4",
        "filename": "old.mp4",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_re_render_clip_replace_updates_existing_row(tmp_path: Path):
    old_clip = tmp_path / "old.mp4"
    old_clip.write_bytes(b"old")
    new_clip = tmp_path / "new.mp4"
    new_clip.write_bytes(b"new")

    service = TaskService(db=AsyncMock())
    service.clip_repo.get_clip_by_id = AsyncMock(
        side_effect=[
            build_clip(file_path=str(old_clip)),
            {
                "id": "clip-1",
                "filename": "new.mp4",
                "file_path": str(new_clip),
                "start_time": "00:10",
                "end_time": "00:20",
                "duration": 10.0,
                "text": "Sample transcript",
                "video_url": "/clips/new.mp4",
            },
        ]
    )
    service.task_repo.get_task_by_id = AsyncMock(return_value={"id": "task-1"})
    service._resolve_task_transcript_and_video = AsyncMock(
        return_value=("transcript", tmp_path / "source.mp4")
    )
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[build_clip()])
    service.clip_repo.update_clip_render = AsyncMock()
    service.clip_repo.create_clip = AsyncMock()
    service.video_service.create_single_clip = AsyncMock(
        return_value={
            "filename": "new.mp4",
            "path": str(new_clip),
            "start_time": "00:10",
            "end_time": "00:20",
            "duration": 10.0,
        }
    )

    virality = MagicMock(
        total_score=80,
        hook_score=20,
        engagement_score=20,
        value_score=20,
        shareability_score=20,
        hook_type="question",
        virality_reasoning="Strong hook",
    )
    score_result = MagicMock(virality=virality)

    with (
        patch(
            "src.services.task_service.VideoService._get_file_duration",
            return_value=120.0,
        ),
        patch(
            "src.ai.score_segment_virality",
            AsyncMock(return_value=score_result),
        ),
        patch("src.services.task_service.load_cached_transcript_data", return_value=None),
    ):
        result = await service.re_render_clip(
            "task-1",
            "clip-1",
            0,
            0,
            "TikTokSans-Regular",
            28,
            "#FFFFFF",
            "riverside",
            position_y=0.7,
            replace=True,
        )

    assert not old_clip.exists()
    service.clip_repo.update_clip_render.assert_awaited_once()
    service.clip_repo.create_clip.assert_not_awaited()
    assert result.get("forked") is False


@pytest.mark.asyncio
async def test_re_render_clip_replace_same_path_keeps_new_file(tmp_path: Path):
    shared_clip = tmp_path / "clip_2_0010-0020.mp4"
    shared_clip.write_bytes(b"new-render")

    service = TaskService(db=AsyncMock())
    service.clip_repo.get_clip_by_id = AsyncMock(
        side_effect=[
            build_clip(
                file_path=str(shared_clip),
                filename="clip_2_0010-0020.mp4",
            ),
            {
                "id": "clip-1",
                "filename": "clip_2_0010-0020.mp4",
                "file_path": str(shared_clip),
                "start_time": "00:10",
                "end_time": "00:20",
                "duration": 10.0,
                "text": "Sample transcript",
                "video_url": "/clips/clip_2_0010-0020.mp4",
            },
        ]
    )
    service.task_repo.get_task_by_id = AsyncMock(return_value={"id": "task-1"})
    service._resolve_task_transcript_and_video = AsyncMock(
        return_value=("transcript", tmp_path / "source.mp4")
    )
    service.clip_repo.get_clips_by_task = AsyncMock(
        return_value=[build_clip(file_path=str(shared_clip))]
    )
    service.clip_repo.update_clip_render = AsyncMock()
    service.clip_repo.create_clip = AsyncMock()
    service.video_service.create_single_clip = AsyncMock(
        return_value={
            "filename": "clip_2_0010-0020.mp4",
            "path": str(shared_clip),
            "start_time": "00:10",
            "end_time": "00:20",
            "duration": 10.0,
        }
    )

    virality = MagicMock(
        total_score=80,
        hook_score=20,
        engagement_score=20,
        value_score=20,
        shareability_score=20,
        hook_type="question",
        virality_reasoning="Strong hook",
    )
    score_result = MagicMock(virality=virality)

    with (
        patch(
            "src.services.task_service.VideoService._get_file_duration",
            return_value=120.0,
        ),
        patch(
            "src.ai.score_segment_virality",
            AsyncMock(return_value=score_result),
        ),
        patch("src.services.task_service.load_cached_transcript_data", return_value=None),
    ):
        result = await service.re_render_clip(
            "task-1",
            "clip-1",
            0,
            0,
            "TikTokSans-Regular",
            28,
            "#FFFFFF",
            "riverside",
            position_y=0.7,
            replace=True,
        )

    assert shared_clip.exists()
    assert shared_clip.read_bytes() == b"new-render"
    service.clip_repo.update_clip_render.assert_awaited_once()
    service.clip_repo.create_clip.assert_not_awaited()
    assert result.get("forked") is False
