"""Scan TEMP_DIR usage and detect orphan media files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .services.video_service import UPLOAD_URL_PREFIX, VideoService

MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
    ".mkv",
    ".avi",
    ".mp3",
    ".m4a",
    ".wav",
}
CACHE_SUFFIXES = (
    ".transcript_cache.json",
    ".speaker_panel_cache.json",
)


@dataclass
class StorageScanResult:
    total_bytes: int = 0
    breakdown: dict[str, int] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    orphan_paths: list[str] = field(default_factory=list)
    temp_dir: str = ""


def _normalize_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def _is_cache_file(path: Path) -> bool:
    name = path.name
    return any(name.endswith(suffix) for suffix in CACHE_SUFFIXES)


def _is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTENSIONS


def _sidecar_paths_for(video_path: Path) -> Iterable[Path]:
    yield video_path.with_suffix(".transcript_cache.json")
    yield video_path.with_suffix(".speaker_panel_cache.json")


def build_referenced_paths(
    clip_paths: Iterable[str],
    upload_urls: Iterable[str],
    cache_video_paths: Iterable[str],
) -> set[Path]:
    referenced: set[Path] = set()

    for raw in clip_paths:
        if not raw:
            continue
        path = _normalize_path(Path(raw))
        referenced.add(path)

    for url in upload_urls:
        if not url or not str(url).startswith(UPLOAD_URL_PREFIX):
            continue
        path = _normalize_path(VideoService.resolve_local_video_path(str(url)))
        referenced.add(path)
        for sidecar in _sidecar_paths_for(path):
            referenced.add(_normalize_path(sidecar))

    for raw in cache_video_paths:
        if not raw:
            continue
        path = _normalize_path(Path(raw))
        referenced.add(path)
        for sidecar in _sidecar_paths_for(path):
            referenced.add(_normalize_path(sidecar))

    return referenced


def scan_storage(temp_dir: Path, referenced_paths: set[Path]) -> StorageScanResult:
    root = _normalize_path(temp_dir)
    breakdown = {
        "clips": 0,
        "uploads": 0,
        "downloads": 0,
        "caches": 0,
        "orphans": 0,
    }
    orphan_paths: list[str] = []
    total_bytes = 0

    if not root.exists():
        return StorageScanResult(
            total_bytes=0,
            breakdown=breakdown,
            counts={"orphan_files": 0},
            orphan_paths=[],
            temp_dir=str(root),
        )

    clips_dir = _normalize_path(root / "clips")
    uploads_dir = _normalize_path(root / "uploads")

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        size = _file_size(path)
        if size <= 0:
            continue

        normalized = _normalize_path(path)
        total_bytes += size
        is_referenced = normalized in referenced_paths

        if is_referenced:
            if _is_cache_file(path):
                bucket = "caches"
            elif clips_dir in normalized.parents or normalized.parent == clips_dir:
                bucket = "clips"
            elif uploads_dir in normalized.parents or normalized.parent == uploads_dir:
                bucket = "uploads"
            else:
                bucket = "downloads"
        elif _is_cache_file(path):
            bucket = "orphans"
            orphan_paths.append(str(normalized))
        else:
            bucket = "orphans"
            orphan_paths.append(str(normalized))

        breakdown[bucket] += size

    return StorageScanResult(
        total_bytes=total_bytes,
        breakdown=breakdown,
        counts={"orphan_files": len(orphan_paths)},
        orphan_paths=orphan_paths,
        temp_dir=str(root),
    )


async def collect_referenced_paths(db: AsyncSession, user_id: str) -> set[Path]:
    clip_result = await db.execute(
        text(
            """
            SELECT c.file_path
            FROM generated_clips c
            JOIN tasks t ON t.id = c.task_id
            WHERE t.user_id = :user_id AND c.file_path IS NOT NULL
            """
        ),
        {"user_id": user_id},
    )
    clip_paths = [row.file_path for row in clip_result.fetchall()]

    upload_result = await db.execute(
        text(
            """
            SELECT DISTINCT s.url
            FROM sources s
            JOIN tasks t ON t.source_id = s.id
            WHERE t.user_id = :user_id AND s.url IS NOT NULL
            """
        ),
        {"user_id": user_id},
    )
    upload_urls = [row.url for row in upload_result.fetchall()]

    cache_result = await db.execute(
        text(
            """
            SELECT video_path
            FROM processing_cache
            WHERE video_path IS NOT NULL
            """
        )
    )
    cache_video_paths = [row.video_path for row in cache_result.fetchall()]

    return build_referenced_paths(clip_paths, upload_urls, cache_video_paths)


async def get_storage_summary(db: AsyncSession, user_id: str, temp_dir: Path) -> dict:
    referenced = await collect_referenced_paths(db, user_id)
    scan = scan_storage(temp_dir, referenced)

    task_count = await db.execute(
        text("SELECT COUNT(*) AS count FROM tasks WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    clip_count = await db.execute(
        text(
            """
            SELECT COUNT(*) AS count
            FROM generated_clips c
            JOIN tasks t ON t.id = c.task_id
            WHERE t.user_id = :user_id
            """
        ),
        {"user_id": user_id},
    )

    return {
        "total_bytes": scan.total_bytes,
        "breakdown": scan.breakdown,
        "counts": {
            "tasks": int(task_count.scalar() or 0),
            "clips": int(clip_count.scalar() or 0),
            "orphan_files": scan.counts.get("orphan_files", 0),
        },
        "temp_dir": scan.temp_dir,
    }


def cleanup_orphan_files(orphan_paths: Iterable[str]) -> tuple[int, int]:
    removed = 0
    reclaimed = 0
    for raw in orphan_paths:
        path = Path(raw)
        size = _file_size(path)
        try:
            if path.is_file():
                path.unlink()
                removed += 1
                reclaimed += size
        except OSError:
            continue
    return removed, reclaimed
