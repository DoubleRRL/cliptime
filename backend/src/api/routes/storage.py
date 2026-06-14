"""Storage usage and orphan cleanup routes."""

from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_config
from ...database import get_db
from ...storage_stats import (
    cleanup_orphan_files,
    collect_referenced_paths,
    get_storage_summary,
    scan_storage,
)
from ..deps import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/")
async def get_storage(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_current_user_id(request)
    temp_dir = Path(get_config().temp_dir)

    try:
        return await get_storage_summary(db, user_id, temp_dir)
    except Exception as exc:
        logger.error("Failed to compute storage summary: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error computing storage summary: {exc}"
        ) from exc


@router.post("/cleanup-orphans")
async def cleanup_orphans(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_current_user_id(request)
    temp_dir = Path(get_config().temp_dir)

    try:
        referenced = await collect_referenced_paths(db, user_id)
        scan = scan_storage(temp_dir, referenced)
        removed, reclaimed = cleanup_orphan_files(scan.orphan_paths)
        summary = await get_storage_summary(db, user_id, temp_dir)
        return {
            "removed_files": removed,
            "reclaimed_bytes": reclaimed,
            **summary,
        }
    except Exception as exc:
        logger.error("Failed to cleanup orphan files: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error cleaning orphan files: {exc}"
        ) from exc
