"""Tests for async re-render enqueue route."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes import tasks as tasks_routes


@pytest.mark.asyncio
async def test_re_render_clip_enqueues_worker_job():
    request = AsyncMock()
    request.json = AsyncMock(
        return_value={
            "start_delta_seconds": 0,
            "end_delta_seconds": 0,
            "font_family": "TikTokSans-Regular",
            "font_size": 28,
            "font_color": "#FFFFFF",
            "caption_template": "riverside",
            "emphasis_callouts": True,
            "replace": False,
        }
    )

    task_service = AsyncMock()
    task_service.task_repo.get_task_by_id = AsyncMock(
        return_value={"id": "task-1", "user_id": "user-1"}
    )
    task_service.clip_repo.get_clip_by_id = AsyncMock(
        return_value={"id": "clip-1", "task_id": "task-1"}
    )

    with (
        patch.object(tasks_routes, "TaskService", return_value=task_service),
        patch.object(tasks_routes, "_require_task_owner", AsyncMock()),
        patch.object(tasks_routes, "is_font_accessible", return_value=True),
        patch.object(
            tasks_routes.JobQueue,
            "enqueue_job",
            AsyncMock(return_value="job-123"),
        ) as enqueue_mock,
    ):
        response = await tasks_routes.re_render_clip(
            "task-1",
            "clip-1",
            request,
            db=AsyncMock(),
        )

    assert response.status_code == 202
    body = response.body.decode()
    assert "job-123" in body
    assert "queued" in body
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.args[0] == "re_render_clip_task"


@pytest.mark.asyncio
async def test_re_render_clip_returns_404_when_clip_missing():
    request = AsyncMock()
    request.json = AsyncMock(return_value={})

    task_service = AsyncMock()
    task_service.task_repo.get_task_by_id = AsyncMock(
        return_value={"id": "task-1", "user_id": "user-1"}
    )
    task_service.clip_repo.get_clip_by_id = AsyncMock(return_value=None)

    with (
        patch.object(tasks_routes, "TaskService", return_value=task_service),
        patch.object(tasks_routes, "_require_task_owner", AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await tasks_routes.re_render_clip(
            "task-1",
            "clip-1",
            request,
            db=AsyncMock(),
        )

    assert exc_info.value.status_code == 404
