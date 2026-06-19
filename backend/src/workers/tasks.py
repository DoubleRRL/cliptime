"""
Worker tasks - background jobs processed by arq workers.
"""

import logging
from typing import Dict, Any
import json

from ..observability import configure_logging, set_trace_id

configure_logging()

logger = logging.getLogger(__name__)


async def process_video_task(
    ctx: Dict[str, Any],
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "riverside",
    processing_mode: str = "quality",
    output_format: str = "vertical",
    add_subtitles: bool = True,
    highlight_color: str = "#8B5CF6",
    background_color: str | None = "#1A1A1ACC",
    cleanup_settings: Dict[str, Any] | None = None,
    llm_model: str | None = None,
    position_y: float | None = None,
    emphasis_callouts: bool = True,
    tight_cuts: bool = True,
) -> Dict[str, Any]:
    """
    Background worker task to process a video.

    Args:
        ctx: arq context (provides Redis connection and other utilities)
        task_id: Task ID to update
        url: Uploaded video reference (`upload://…`) or local path
        source_type: Always `video_url` for new tasks
        user_id: User ID who created the task
        font_family: Font family for subtitles
        font_size: Font size for subtitles
        font_color: Font color for subtitles

    Returns:
        Dict with processing results
    """
    from ..ai import set_model_override
    from ..database import AsyncSessionLocal
    from ..services.task_service import TaskService
    from ..workers.progress import ProgressTracker

    set_trace_id(f"task-{task_id}")
    set_model_override(llm_model)
    if llm_model:
        logger.info(f"Worker processing task {task_id} with model override {llm_model}")
    else:
        logger.info(f"Worker processing task {task_id}")

    # Create progress tracker
    progress = ProgressTracker(ctx["redis"], task_id)

    async with AsyncSessionLocal() as db:
        task_service = TaskService(db)

        try:
            # Progress callback
            async def update_progress(
                percent: int, message: str, status: str = "processing"
            ):
                await progress.update(percent, message, status)
                logger.info(f"Task {task_id}: {percent}% - {message}")

            async def should_cancel() -> bool:
                cancelled = await ctx["redis"].get(f"task_cancel:{task_id}")
                return bool(cancelled)

            async def clip_ready_callback(
                clip_index: int, total_clips: int, clip_data: dict
            ):
                await progress.clip_ready(clip_index, total_clips, clip_data)

            # Process the video
            result = await task_service.process_task(
                task_id=task_id,
                url=url,
                source_type=source_type,
                font_family=font_family,
                font_size=font_size,
                font_color=font_color,
                caption_template=caption_template,
                processing_mode=processing_mode,
                output_format=output_format,
                add_subtitles=add_subtitles,
                highlight_color=highlight_color,
                background_color=background_color,
                progress_callback=update_progress,
                should_cancel=should_cancel,
                clip_ready_callback=clip_ready_callback,
                cleanup_settings=cleanup_settings,
                position_y=position_y,
                emphasis_callouts=emphasis_callouts,
                tight_cuts=tight_cuts,
            )

            logger.info(f"Task {task_id} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            try:
                job_try = int(ctx.get("job_try", 1))
                max_tries = int(getattr(WorkerSettings, "max_tries", 3))
                if job_try >= max_tries:
                    payload = {
                        "task_id": task_id,
                        "error": str(e),
                        "tries": job_try,
                    }
                    await ctx["redis"].set(
                        f"dead_letter:{task_id}", json.dumps(payload)
                    )
                    await ctx["redis"].sadd("tasks:dead_letter", task_id)
            except Exception:
                logger.exception("Failed to persist dead-letter payload")

            try:
                from ..services.task_service import TaskService

                error_code = "task_error"
                lowered = str(e).lower()
                if "video file not found" in lowered or "upload" in lowered:
                    error_code = "download_error"
                elif "transcript" in lowered or "transcribe" in lowered:
                    error_code = "transcription_error"
                elif "analysis" in lowered:
                    error_code = "analysis_error"
                await progress.error(
                    TaskService._humanize_error_message(error_code, str(e))
                )
            except Exception:
                await progress.error(str(e))
            raise

async def generate_clips_from_query_task(
    ctx: Dict[str, Any],
    task_id: str,
    query: str,
    clip_types: list,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "riverside",
) -> Dict[str, Any]:
    """Background worker task to find and render custom clips from a user query."""
    from ..ai import set_model_override
    from ..database import AsyncSessionLocal
    from ..services.task_service import TaskService
    from ..workers.progress import ProgressTracker

    set_trace_id(f"task-{task_id}-custom")
    logger.info("Worker generating custom clips for task %s", task_id)

    progress = ProgressTracker(ctx["redis"], task_id)

    async with AsyncSessionLocal() as db:
        task_service = TaskService(db)

        # Custom clip search should use the same model the task was created with.
        task_record = await task_service.task_repo.get_task_by_id(db, task_id)
        set_model_override((task_record or {}).get("llm_model"))

        async def clip_ready_callback(
            clip_index: int, total_clips: int, clip_data: dict
        ):
            await progress.clip_ready(clip_index, total_clips, clip_data)

        try:
            result = await task_service.generate_clips_from_query(
                task_id=task_id,
                query=query,
                clip_types=clip_types,
                font_family=font_family,
                font_size=font_size,
                font_color=font_color,
                caption_template=caption_template,
                clip_ready_callback=clip_ready_callback,
            )
            logger.info("Custom clip generation completed for task %s", task_id)
            return result
        except Exception as e:
            logger.error(
                "Custom clip generation failed for task %s: %s",
                task_id,
                e,
                exc_info=True,
            )
            raise


async def re_render_clip_task(
    ctx: Dict[str, Any],
    task_id: str,
    clip_id: str,
    start_delta_seconds: float,
    end_delta_seconds: float,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "riverside",
    highlight_color: str = "#8B5CF6",
    background_color: str = "#1A1A1ACC",
    position_y: float | None = None,
    replace: bool = False,
    emphasis_callouts: bool = True,
    tight_cuts: bool = True,
) -> Dict[str, Any]:
    """Background worker task to re-render a clip with updated styling."""
    from ..ai import set_model_override
    from ..database import AsyncSessionLocal
    from ..services.task_service import TaskService
    from ..workers.progress import ProgressTracker

    set_trace_id(f"task-{task_id}-rerender-{clip_id}")
    logger.info("Worker re-rendering clip %s for task %s", clip_id, task_id)

    progress = ProgressTracker(ctx["redis"], task_id)

    async with AsyncSessionLocal() as db:
        task_service = TaskService(db)
        task_record = await task_service.task_repo.get_task_by_id(db, task_id)
        set_model_override((task_record or {}).get("llm_model"))

        async def progress_callback(message: str, stage: str = "rerender"):
            await progress.update(0, message, "processing", stage=stage)

        try:
            updated_clip = await task_service.re_render_clip(
                task_id,
                clip_id,
                start_delta_seconds,
                end_delta_seconds,
                font_family,
                font_size,
                font_color,
                caption_template,
                highlight_color=highlight_color,
                background_color=background_color,
                position_y=position_y,
                replace=replace,
                emphasis_callouts=emphasis_callouts,
                tight_cuts=tight_cuts,
                progress_callback=progress_callback,
            )
            forked = bool(updated_clip.get("forked", not replace))
            await progress.clip_ready(
                0,
                1,
                updated_clip,
                source_clip_id=clip_id,
                replace=replace,
                forked=forked,
            )
            logger.info("Re-render completed for clip %s in task %s", clip_id, task_id)
            return {
                "clip": updated_clip,
                "forked": forked,
                "parent_clip_id": clip_id if forked else None,
            }
        except Exception as e:
            logger.error(
                "Re-render failed for clip %s in task %s: %s",
                clip_id,
                task_id,
                e,
                exc_info=True,
            )
            await progress.rerender_error(clip_id, str(e))
            raise


# Worker configuration for arq
class WorkerSettings:
    """Configuration for arq worker."""

    from ..config import Config
    from arq.connections import RedisSettings

    config = Config()

    # Functions to run
    functions = [
        process_video_task,
        generate_clips_from_query_task,
        re_render_clip_task,
    ]
    queue_name = "supoclip_tasks"

    # Redis settings from environment
    redis_settings = RedisSettings(
        host=config.redis_host, port=config.redis_port, password=config.redis_password, database=0
    )

    # Retry settings
    max_tries = 3  # Retry failed jobs up to 3 times
    job_timeout = config.worker_job_timeout_seconds

    # Worker pool settings — serialize heavy video jobs by default
    max_jobs = config.worker_max_jobs
    cron_jobs = []
