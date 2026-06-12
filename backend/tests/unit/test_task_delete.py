from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.task_service import TaskService


def build_task(
    *,
    task_id: str = "task-1",
    source_id: str = "source-1",
    source_url: str = "upload://video.mp4",
    source_type: str = "video_url",
    status: str = "completed",
) -> dict:
    return {
        "id": task_id,
        "source_id": source_id,
        "source_url": source_url,
        "source_type": source_type,
        "status": status,
    }


@pytest.mark.asyncio
async def test_delete_task_removes_clips_and_task(tmp_path: Path):
    clip_file = tmp_path / "clip.mp4"
    clip_file.write_bytes(b"clip")

    service = TaskService(db=AsyncMock())
    service.task_repo.get_task_by_id = AsyncMock(
        return_value=build_task(status="completed")
    )
    service.clip_repo.get_clips_by_task = AsyncMock(
        return_value=[{"file_path": str(clip_file)}]
    )
    service.clip_repo.delete_clips_by_task = AsyncMock()
    service.task_repo.count_tasks_by_source_id = AsyncMock(return_value=0)
    service.cache_repo.delete_by_source_url = AsyncMock()
    service.task_repo.delete_task = AsyncMock()

    await service.delete_task("task-1")

    assert not clip_file.exists()
    service.clip_repo.delete_clips_by_task.assert_awaited_once()
    service.cache_repo.delete_by_source_url.assert_awaited_once()
    service.task_repo.delete_task.assert_awaited_once_with(service.db, "task-1")


@pytest.mark.asyncio
async def test_delete_task_keeps_upload_when_other_tasks_share_source(tmp_path: Path):
    upload_file = tmp_path / "video.mp4"
    upload_file.write_bytes(b"video")
    sidecar = upload_file.with_suffix(".transcript_cache.json")
    sidecar.write_text("{}")

    service = TaskService(db=AsyncMock())
    service.task_repo.get_task_by_id = AsyncMock(return_value=build_task())
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[])
    service.clip_repo.delete_clips_by_task = AsyncMock()
    service.task_repo.count_tasks_by_source_id = AsyncMock(return_value=1)
    service.cache_repo.delete_by_source_url = AsyncMock()
    service.task_repo.delete_task = AsyncMock()
    service.video_service.resolve_local_video_path = MagicMock(return_value=upload_file)

    await service.delete_task("task-1")

    assert upload_file.exists()
    assert sidecar.exists()
    service.cache_repo.delete_by_source_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_task_removes_upload_when_last_task_for_source(tmp_path: Path):
    upload_file = tmp_path / "video.mp4"
    upload_file.write_bytes(b"video")
    transcript_cache = upload_file.with_suffix(".transcript_cache.json")
    speaker_cache = upload_file.with_suffix(".speaker_panel_cache.json")
    transcript_cache.write_text("{}")
    speaker_cache.write_text("{}")

    service = TaskService(db=AsyncMock())
    service.task_repo.get_task_by_id = AsyncMock(return_value=build_task())
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[])
    service.clip_repo.delete_clips_by_task = AsyncMock()
    service.task_repo.count_tasks_by_source_id = AsyncMock(return_value=0)
    service.cache_repo.delete_by_source_url = AsyncMock()
    service.task_repo.delete_task = AsyncMock()
    service.video_service.resolve_local_video_path = MagicMock(return_value=upload_file)

    await service.delete_task("task-1")

    assert not upload_file.exists()
    assert not transcript_cache.exists()
    assert not speaker_cache.exists()
    service.cache_repo.delete_by_source_url.assert_awaited_once_with(
        service.db, "upload://video.mp4"
    )


@pytest.mark.asyncio
async def test_delete_task_sets_cancel_flag_for_processing_task():
    fake_redis = AsyncMock()
    service = TaskService(db=AsyncMock())
    service.task_repo.get_task_by_id = AsyncMock(
        return_value=build_task(status="processing")
    )
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[])
    service.clip_repo.delete_clips_by_task = AsyncMock()
    service.task_repo.count_tasks_by_source_id = AsyncMock(return_value=1)
    service.task_repo.delete_task = AsyncMock()

    with patch("src.services.task_service.get_redis", MagicMock(return_value=fake_redis)):
        await service.delete_task("task-1")

    fake_redis.setex.assert_awaited_once_with("task_cancel:task-1", 3600, "1")
