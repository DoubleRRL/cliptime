from pathlib import Path

from src.file_cleanup import delete_clip_files, delete_upload_source_files, safe_unlink


def test_safe_unlink_removes_file(tmp_path: Path):
    clip_file = tmp_path / "clip.mp4"
    clip_file.write_bytes(b"video")

    assert safe_unlink(clip_file) is True
    assert not clip_file.exists()


def test_delete_clip_files_counts_removed(tmp_path: Path):
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    removed = delete_clip_files(
        [
            {"file_path": str(first)},
            {"file_path": str(second)},
            {"file_path": str(tmp_path / "missing.mp4")},
        ]
    )

    assert removed == 2


def test_delete_upload_source_files_removes_video_and_sidecars(tmp_path: Path):
    video = tmp_path / "upload.mp4"
    video.write_bytes(b"video")
    transcript = video.with_suffix(".transcript_cache.json")
    speaker = video.with_suffix(".speaker_panel_cache.json")
    transcript.write_text("{}")
    speaker.write_text("{}")

    removed = delete_upload_source_files(video)

    assert removed == 3
    assert not video.exists()
    assert not transcript.exists()
    assert not speaker.exists()
