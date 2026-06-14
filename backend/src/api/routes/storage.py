"""Storage usage and orphan cleanup routes."""

from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_config
from ...database import get_db
from ...storage_stats import (
    cleanup_orphan_files,
    collect_referenced_paths,
    filter_orphan_paths,
    get_storage_summary,
    scan_storage,
)
from ..deps import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storage", tags=["storage"])


class CleanupOrphansRequest(BaseModel):
    paths: list[str] | None = Field(
        default=None,
        description="Optional subset of orphan paths to delete. Omit to delete all orphans.",
    )


def _host_path(config_temp_dir: Path) -> str | None:
    configured = get_config().storage_host_path
    if configured:
        return configured
    return None


@router.get("/")
async def get_storage(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_current_user_id(request)
    temp_dir = Path(get_config().temp_dir)

    try:
        return await get_storage_summary(
            db,
            user_id,
            temp_dir,
            host_path=_host_path(temp_dir),
        )
    except Exception as exc:
        logger.error("Failed to compute storage summary: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error computing storage summary: {exc}"
        ) from exc


@router.post("/cleanup-orphans")
async def cleanup_orphans(
    request: Request,
    body: CleanupOrphansRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    user_id = get_current_user_id(request)
    temp_dir = Path(get_config().temp_dir)

    try:
        referenced = await collect_referenced_paths(db, user_id)
        scan = scan_storage(temp_dir, referenced)
        requested_paths = body.paths if body and body.paths else scan.orphan_paths
        paths_to_delete = filter_orphan_paths(requested_paths, scan.orphan_paths)
        if body and body.paths and not paths_to_delete:
            raise HTTPException(
                status_code=400,
                detail="No valid orphan paths provided",
            )

        removed, reclaimed = cleanup_orphan_files(paths_to_delete)
        summary = await get_storage_summary(
            db,
            user_id,
            temp_dir,
            host_path=_host_path(temp_dir),
        )
        return {
            "removed_files": removed,
            "reclaimed_bytes": reclaimed,
            **summary,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to cleanup orphan files: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error cleaning orphan files: {exc}"
        ) from exc
