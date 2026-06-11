"""Authenticated clip file serving (replaces the public static mount)."""

from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_config
from ...database import get_db
from ...repositories.clip_repository import ClipRepository
from ..deps import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(tags=["clips"])


@router.get("/clips/{filename}")
async def serve_clip(
    filename: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Serve a generated clip after verifying the requester owns it."""
    user_id = get_current_user_id(request)

    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    owner_id = await ClipRepository.get_clip_owner_by_filename(db, filename)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    if owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this clip")

    clips_dir = Path(get_config().temp_dir) / "clips"
    clip_path = (clips_dir / filename).resolve()
    if not str(clip_path).startswith(str(clips_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found on disk")

    return FileResponse(
        path=str(clip_path),
        media_type="video/mp4",
        headers={"Cache-Control": "private, max-age=3600"},
    )
