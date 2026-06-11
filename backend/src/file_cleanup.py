"""Utilities for deleting generated media files from disk."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def safe_unlink(path: str | Path) -> bool:
    """Delete a file if it exists. Returns True when removed."""
    try:
        target = Path(path)
        if target.is_file():
            target.unlink()
            logger.info("Deleted file %s", target)
            return True
    except OSError as exc:
        logger.warning("Failed to delete %s: %s", path, exc)
    return False


def delete_clip_files(clips: list[dict]) -> int:
    """Delete on-disk MP4s for the given clip rows. Returns count removed."""
    removed = 0
    for clip in clips:
        file_path = clip.get("file_path")
        if file_path and safe_unlink(file_path):
            removed += 1
    return removed
