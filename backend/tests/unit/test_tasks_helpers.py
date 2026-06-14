from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.tasks import (
    _normalize_font_color,
    _normalize_font_family,
    _normalize_font_size,
    _resolve_clip_input_path,
    export_clip,
)


def test_normalize_font_size_bounds_values():
    assert _normalize_font_size("4") == 12
    assert _normalize_font_size("120") == 72


def test_normalize_font_color_accepts_hex_values():
    assert _normalize_font_color("#abcdef") == "#ABCDEF"
    assert _normalize_font_color("blue") == "#FFFFFF"


def test_normalize_font_family_uses_default_for_empty_values():
    assert _normalize_font_family("  ") == "TikTokSans-Regular"
    assert _normalize_font_family("Inter") == "Inter"


def test_resolve_clip_input_path_prefers_existing_file_path(tmp_path: Path):
    clip_file = tmp_path / "clips" / "clip_1.mp4"
    clip_file.parent.mkdir(parents=True)
    clip_file.write_bytes(b"clip")

    resolved = _resolve_clip_input_path(
        {
            "file_path": str(clip_file),
            "filename": "clip_1.mp4",
        }
    )
    assert resolved == clip_file


def test_resolve_clip_input_path_falls_back_to_clips_dir(tmp_path: Path, monkeypatch):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir(parents=True)
    clip_file = clips_dir / "clip_2.mp4"
    clip_file.write_bytes(b"clip")

    monkeypatch.setattr("src.api.routes.tasks.config.temp_dir", str(tmp_path))

    resolved = _resolve_clip_input_path(
        {
            "file_path": str(tmp_path / "missing" / "clip_2.mp4"),
            "filename": "clip_2.mp4",
        }
    )
    assert resolved == clip_file


@pytest.mark.asyncio
async def test_export_clip_returns_404_when_file_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.api.routes.tasks.config.temp_dir", str(tmp_path))

    task_service = MagicMock()
    task_service.clip_repo.get_clip_by_id = AsyncMock(
        return_value={
            "id": "clip-1",
            "task_id": "task-1",
            "filename": "missing.mp4",
            "file_path": str(tmp_path / "clips" / "missing.mp4"),
        }
    )

    request = MagicMock()

    with (
        patch("src.api.routes.tasks._require_task_owner", AsyncMock()),
        patch("src.api.routes.tasks.TaskService", return_value=task_service),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await export_clip("task-1", "clip-1", request, "tiktok", db=AsyncMock())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Clip file not found on disk"

