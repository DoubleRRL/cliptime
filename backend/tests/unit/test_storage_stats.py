from pathlib import Path

from src.storage_stats import (
    _normalize_path,
    build_referenced_paths,
    cleanup_orphan_files,
    scan_storage,
)


def test_scan_storage_classifies_referenced_and_orphan_files(tmp_path: Path):
    clips_dir = tmp_path / "clips"
    uploads_dir = tmp_path / "uploads"
    clips_dir.mkdir()
    uploads_dir.mkdir()

    referenced_clip = clips_dir / "keep.mp4"
    orphan_clip = clips_dir / "stale.mp4"
    upload = uploads_dir / "source.mp4"
    download = tmp_path / "yt-video.mp4"

    for path in (referenced_clip, orphan_clip, upload, download):
        path.write_bytes(b"x" * 100)

    referenced = build_referenced_paths(
        clip_paths=[str(referenced_clip)],
        upload_urls=[],
        cache_video_paths=[str(download)],
    )
    referenced.add(_normalize_path(upload))

    result = scan_storage(tmp_path, referenced)

    assert result.total_bytes == 400
    assert result.breakdown["clips"] == 100
    assert result.breakdown["uploads"] == 100
    assert result.breakdown["downloads"] == 100
    assert result.breakdown["orphans"] == 100
    assert result.counts["orphan_files"] == 1
    assert str(orphan_clip.resolve()) in result.orphan_paths


def test_cleanup_orphan_files_removes_only_orphans(tmp_path: Path):
    orphan = tmp_path / "orphan.mp4"
    orphan.write_bytes(b"12345")

    removed, reclaimed = cleanup_orphan_files([str(orphan)])

    assert removed == 1
    assert reclaimed == 5
    assert not orphan.exists()
