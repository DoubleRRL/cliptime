"""
Task service - orchestrates task creation and processing workflow.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, Callable
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import json
import hashlib
from time import perf_counter

from ..redis_client import get_redis
from ..utils.async_helpers import run_in_thread
from ..repositories.task_repository import TaskRepository
from ..repositories.source_repository import SourceRepository
from ..repositories.clip_repository import ClipRepository
from ..repositories.cache_repository import CacheRepository
from .video_service import UPLOAD_URL_PREFIX, VideoService
from ..config import Config, get_config
from ..clip_editor import (
    trim_clip_file,
    split_clip_file,
    merge_clip_files,
    overlay_custom_captions,
)
from ..video_utils import (
    parse_timestamp_to_seconds,
    load_cached_transcript_data,
    get_words_in_range,
)
from ..file_cleanup import delete_clip_files, delete_upload_source_files

logger = logging.getLogger(__name__)


def compute_re_render_bounds(
    start_seconds: float,
    end_seconds: float,
    start_delta_seconds: float,
    end_delta_seconds: float,
    video_duration: float,
    min_duration: float = 3.0,
) -> tuple[float, float]:
    """Compute clamped source bounds after trim/extend deltas."""
    new_start = start_seconds + start_delta_seconds
    new_end = end_seconds - end_delta_seconds

    new_start = max(0.0, min(new_start, video_duration))
    new_end = max(0.0, min(new_end, video_duration))

    if new_end <= new_start:
        raise ValueError("Clip boundaries are invalid after adjustment")

    if new_end - new_start < min_duration:
        raise ValueError(f"Clip must be at least {min_duration:.0f} seconds long")

    return new_start, new_end


class TaskService:
    """Service for task workflow orchestration."""

    def __init__(self, db: AsyncSession, config: Config | None = None):
        self.db = db
        self.task_repo = TaskRepository()
        self.source_repo = SourceRepository()
        self.clip_repo = ClipRepository()
        self.cache_repo = CacheRepository()
        self.video_service = VideoService()
        self.config = config or get_config()

    @staticmethod
    def _build_cache_key(url: str, source_type: str, processing_mode: str) -> str:
        payload = f"{source_type}|{processing_mode}|{url.strip()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _humanize_error_message(error_code: str, raw_message: str) -> str:
        messages = {
            "transcription_error": (
                "Couldn't transcribe audio. Check your AssemblyAI key and quota, then try again."
            ),
            "analysis_error": (
                "AI clip selection failed. Try LLM=ollama:qwen2.5:latest or a shorter test video."
            ),
            "download_error": "Couldn't download the video. Check the URL and try again.",
            "render_error": "Clip rendering failed. Check worker logs for details.",
            "cancelled": "Processing was cancelled.",
        }
        if error_code in messages:
            return messages[error_code]
        return raw_message or "There was an error processing your video."

    def _is_stale_queued_task(self, task: Dict[str, Any]) -> bool:
        """Detect queued tasks that have likely stalled due to worker issues."""
        if task.get("status") != "queued":
            return False

        created_at = task.get("created_at")
        updated_at = task.get("updated_at") or created_at

        if not created_at or not updated_at:
            return False

        now = (
            datetime.now(updated_at.tzinfo)
            if getattr(updated_at, "tzinfo", None)
            else datetime.utcnow()
        )
        age_seconds = (now - updated_at).total_seconds()
        return age_seconds >= self.config.queued_task_timeout_seconds

    def _is_stale_processing_task(self, task: Dict[str, Any]) -> bool:
        """Detect processing tasks with no recent worker updates."""
        if task.get("status") != "processing":
            return False

        updated_at = task.get("updated_at") or task.get("created_at")
        if not updated_at:
            return False

        now = (
            datetime.now(updated_at.tzinfo)
            if getattr(updated_at, "tzinfo", None)
            else datetime.utcnow()
        )
        age_seconds = (now - updated_at).total_seconds()
        return age_seconds >= self.config.processing_task_timeout_seconds

    async def create_task_with_source(
        self,
        user_id: str,
        url: str,
        title: Optional[str] = None,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        caption_template: str = "default",
        processing_mode: str = "quality",
        llm_model: Optional[str] = None,
    ) -> str:
        """
        Create a new task with associated source.
        Returns the task ID.
        """
        # Validate user exists
        if not await self.task_repo.user_exists(self.db, user_id):
            raise ValueError(f"User {user_id} not found")

        # Determine source type
        source_type = self.video_service.determine_source_type(url)

        # Get or generate title
        if not title:
            if source_type == "youtube":
                title = await self.video_service.get_video_title(url)
            else:
                title = "Uploaded Video"

        # Create source
        source_id = await self.source_repo.create_source(
            self.db, source_type=source_type, title=title, url=url
        )

        # Create task
        task_id = await self.task_repo.create_task(
            self.db,
            user_id=user_id,
            source_id=source_id,
            status="queued",  # Changed from "processing" to "queued"
            font_family=font_family,
            font_size=font_size,
            font_color=font_color,
            caption_template=caption_template,
            processing_mode=processing_mode,
            llm_model=llm_model,
        )

        logger.info(f"Created task {task_id} for user {user_id}")
        return task_id

    async def process_task(
        self,
        task_id: str,
        url: str,
        source_type: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        caption_template: str = "default",
        processing_mode: str = "quality",
        output_format: str = "vertical",
        add_subtitles: bool = True,
        highlight_color: str = "#8B5CF6",
        background_color: str = "#1A1A1ACC",
        progress_callback: Optional[Callable] = None,
        should_cancel: Optional[Callable] = None,
        clip_ready_callback: Optional[Callable] = None,
        cleanup_settings: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Process a task: download video, analyze, create clips.
        Returns processing results.
        """
        try:
            logger.info(f"Starting processing for task {task_id}")
            started_at = datetime.utcnow()
            stage_timings: Dict[str, float] = {}

            # Idempotent retries: drop partial clips from a prior failed run.
            existing_task = await self.task_repo.get_task_by_id(self.db, task_id)
            if existing_task and existing_task.get("status") in {
                "processing",
                "error",
            }:
                partial_clips = await self.clip_repo.get_clips_by_task(
                    self.db, task_id
                )
                if partial_clips:
                    delete_clip_files(partial_clips)
                    await self.clip_repo.delete_clips_by_task(self.db, task_id)
                    await self.task_repo.update_task_clips(self.db, task_id, [])
                    await self.db.commit()
                    logger.info(
                        "Cleared %s partial clip(s) before retry for task %s",
                        len(partial_clips),
                        task_id,
                    )

            cache_key = self._build_cache_key(url, source_type, processing_mode)

            cache_entry = await self.cache_repo.get_cache(self.db, cache_key)
            cached_transcript = (
                cache_entry.get("transcript_text") if cache_entry else None
            )
            cached_analysis_json = (
                cache_entry.get("analysis_json") if cache_entry else None
            )
            cache_hit = False
            if cached_transcript and cached_analysis_json:
                try:
                    cached_analysis = json.loads(cached_analysis_json)
                    cached_segments = cached_analysis.get("most_relevant_segments") or []
                    if not cached_segments:
                        cached_segments = list(
                            cached_analysis.get("micro_hooks") or []
                        ) + list(cached_analysis.get("deep_context_clips") or [])
                    cache_hit = bool(cached_segments)
                except Exception:
                    cache_hit = False

            await self.task_repo.update_task_runtime_metadata(
                self.db,
                task_id,
                started_at=started_at,
                cache_hit=cache_hit,
                error_code="",
            )

            # Update status to processing
            await self.task_repo.update_task_status(
                self.db,
                task_id,
                "processing",
                progress=0,
                progress_message="Starting...",
            )

            # Progress callback wrapper
            async def update_progress(
                progress: int, message: str, status: str = "processing"
            ):
                await self.task_repo.update_task_status(
                    self.db,
                    task_id,
                    status,
                    progress=progress,
                    progress_message=message,
                )
                if progress_callback:
                    await progress_callback(progress, message, status)

            # Process video with progress updates
            pipeline_start = perf_counter()
            result = await self.video_service.process_video_complete(
                url=url,
                source_type=source_type,
                task_id=task_id,
                font_family=font_family,
                font_size=font_size,
                font_color=font_color,
                caption_template=caption_template,
                processing_mode=processing_mode,
                output_format=output_format,
                add_subtitles=add_subtitles,
                cached_transcript=cached_transcript,
                cached_analysis_json=cached_analysis_json,
                progress_callback=update_progress,
                should_cancel=should_cancel,
            )
            stage_timings["pipeline_seconds"] = round(
                perf_counter() - pipeline_start, 3
            )

            # Checkpoint transcript + analysis before clip render so ARQ retries
            # can skip Whisper/Ollama if the worker times out during rendering.
            await self.cache_repo.upsert_cache(
                self.db,
                cache_key=cache_key,
                source_url=url,
                source_type=source_type,
                transcript_text=result.get("transcript"),
                analysis_json=result.get("analysis_json"),
            )
            await self.db.commit()

            # Render clips in parallel (bounded), persisting and notifying as
            # each finishes. DB writes stay in this coroutine so the shared
            # AsyncSession is never used concurrently.
            segments_to_render = result.get("segments_to_render", [])
            if not segments_to_render:
                raise RuntimeError(
                    "AI analysis returned no clip segments. "
                    "Try a different local model (e.g. qwen3:8b) or balanced mode."
                )
            video_path = Path(result["video_path"])
            total_clips = len(segments_to_render)
            clips_output_dir = Path(self.config.temp_dir) / "clips"
            clips_output_dir.mkdir(parents=True, exist_ok=True)

            render_start = perf_counter()
            semaphore = asyncio.Semaphore(self.config.parallel_clip_renders)

            async def render_one(
                index: int, segment: Dict[str, Any]
            ) -> tuple[int, Optional[Dict[str, Any]], bool]:
                async with semaphore:
                    if should_cancel and await should_cancel():
                        return index, None, True
                    clip_info = await self.video_service.create_single_clip(
                        video_path,
                        segment,
                        index,
                        clips_output_dir,
                        font_family,
                        font_size,
                        font_color,
                        caption_template,
                        output_format,
                        add_subtitles,
                        highlight_color,
                        background_color,
                        processing_mode,
                    )
                    return index, clip_info, False

            render_tasks = [
                asyncio.create_task(render_one(i, segment))
                for i, segment in enumerate(segments_to_render)
            ]

            clip_id_by_index: Dict[int, str] = {}
            clips_done = 0
            try:
                for future in asyncio.as_completed(render_tasks):
                    index, clip_info, was_cancelled = await future
                    if was_cancelled:
                        raise Exception("Task cancelled")

                    clips_done += 1
                    clip_progress = (
                        70 + int((clips_done / total_clips) * 25)
                        if total_clips > 0
                        else 95
                    )
                    await update_progress(
                        clip_progress,
                        f"Created clip {clips_done}/{total_clips}...",
                    )

                    if clip_info is None:
                        continue  # Skip failed clip

                    # Save to DB immediately
                    clip_id = await self.clip_repo.create_clip(
                        self.db,
                        task_id=task_id,
                        filename=clip_info["filename"],
                        file_path=clip_info["path"],
                        start_time=clip_info["start_time"],
                        end_time=clip_info["end_time"],
                        duration=clip_info["duration"],
                        text=clip_info.get("text", ""),
                        relevance_score=clip_info.get("relevance_score", 0.0),
                        reasoning=clip_info.get("reasoning", ""),
                        clip_order=index + 1,
                        virality_score=clip_info.get("virality_score", 0),
                        hook_score=clip_info.get("hook_score", 0),
                        engagement_score=clip_info.get("engagement_score", 0),
                        value_score=clip_info.get("value_score", 0),
                        shareability_score=clip_info.get("shareability_score", 0),
                        hook_type=clip_info.get("hook_type"),
                        emphasis_words_json=json.dumps(clip_info.get("emphasis_words") or [])
                        if clip_info.get("emphasis_words")
                        else None,
                    )
                    await self.db.commit()
                    clip_id_by_index[index] = clip_id

                    # Keep the task's clip IDs in segment order
                    ordered_ids = [
                        clip_id_by_index[i]
                        for i in sorted(clip_id_by_index)
                    ]
                    await self.task_repo.update_task_clips(
                        self.db, task_id, ordered_ids
                    )

                    # Notify frontend via SSE
                    if clip_ready_callback:
                        clip_record = await self.clip_repo.get_clip_by_id(
                            self.db, clip_id
                        )
                        if clip_record:
                            await clip_ready_callback(
                                index, total_clips, clip_record
                            )
            except BaseException:
                for task in render_tasks:
                    task.cancel()
                raise

            clip_ids = [clip_id_by_index[i] for i in sorted(clip_id_by_index)]

            stage_timings["render_seconds"] = round(
                perf_counter() - render_start, 3
            )

            # Mark as completed
            await self.task_repo.update_task_status(
                self.db,
                task_id,
                "completed",
                progress=100,
                progress_message="Complete!",
            )

            if progress_callback:
                await progress_callback(100, "Complete!", "completed")

            await self.task_repo.update_task_runtime_metadata(
                self.db,
                task_id,
                completed_at=datetime.utcnow(),
                stage_timings_json=json.dumps(stage_timings),
                error_code="",
            )

            logger.info(
                f"Task {task_id} completed successfully with {len(clip_ids)} clips"
            )

            return {
                "task_id": task_id,
                "clips_count": len(clip_ids),
                "segments": result["segments"],
                "summary": result.get("summary"),
                "key_topics": result.get("key_topics"),
            }

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            if str(e) == "Task cancelled":
                await self.task_repo.update_task_status(
                    self.db,
                    task_id,
                    "cancelled",
                    progress=0,
                    progress_message="Cancelled by user",
                )
                if progress_callback:
                    await progress_callback(0, "Cancelled by user", "cancelled")
                raise
            error_code = "task_error"
            message = str(e).lower()
            if "download" in message or "youtube" in message:
                error_code = "download_error"
            elif "transcript" in message or "transcribe" in message:
                error_code = "transcription_error"
            elif "analysis" in message:
                error_code = "analysis_error"
            elif "cancelled" in message:
                error_code = "cancelled"

            user_message = self._humanize_error_message(error_code, str(e))
            await self.task_repo.update_task_status(
                self.db,
                task_id,
                "error",
                progress=0,
                progress_message=user_message,
            )
            if progress_callback:
                await progress_callback(0, user_message, "error")

            await self.task_repo.update_task_runtime_metadata(
                self.db,
                task_id,
                completed_at=datetime.utcnow(),
                error_code=error_code,
            )
            raise

    async def get_task_with_clips(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task details with all clips."""
        task = await self.task_repo.get_task_by_id(self.db, task_id)

        if not task:
            return None

        if self._is_stale_queued_task(task):
            timeout_seconds = self.config.queued_task_timeout_seconds
            logger.warning(
                f"Task {task_id} stuck in queued status for over {timeout_seconds}s; marking as error"
            )
            await self.task_repo.update_task_status(
                self.db,
                task_id,
                "error",
                progress=0,
                progress_message=(
                    "Task timed out while waiting in queue. "
                    "Ensure the worker service is running and healthy (docker-compose logs -f worker)."
                ),
            )
            task = await self.task_repo.get_task_by_id(self.db, task_id)
            if not task:
                return None

        if self._is_stale_processing_task(task):
            timeout_seconds = self.config.processing_task_timeout_seconds
            logger.warning(
                "Task %s stuck in processing status for over %ss; marking as error",
                task_id,
                timeout_seconds,
            )
            await self.task_repo.update_task_status(
                self.db,
                task_id,
                "error",
                progress=task.get("progress") or 0,
                progress_message=(
                    "Processing timed out with no progress updates. "
                    "Cancel and resume the task, or check worker logs "
                    "(docker compose logs -f worker)."
                ),
            )
            task = await self.task_repo.get_task_by_id(self.db, task_id)
            if not task:
                return None

        # Get clips
        clips = await self.clip_repo.get_clips_by_task(self.db, task_id)
        task["clips"] = clips
        task["clips_count"] = len(clips)

        return task

    async def count_user_tasks(self, user_id: str) -> int:
        """Count all tasks for a user."""
        return await self.task_repo.count_user_tasks(self.db, user_id)

    async def get_user_tasks(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[Dict[str, Any]]:
        """Get paginated tasks for a user."""
        return await self.task_repo.get_user_tasks(
            self.db, user_id, limit, offset
        )

    async def delete_task(self, task_id: str) -> None:
        """Delete a task, its clips, and source media when no other task references it."""
        task = await self.task_repo.get_task_by_id(self.db, task_id)
        if not task:
            logger.warning("delete_task called for missing task %s", task_id)
            return

        if task.get("status") in ("queued", "processing"):
            try:
                await get_redis().setex(f"task_cancel:{task_id}", 3600, "1")
            except Exception as exc:
                logger.warning(
                    "Failed to set cancel flag for task %s: %s", task_id, exc
                )

        clips = await self.clip_repo.get_clips_by_task(self.db, task_id)
        delete_clip_files(clips)
        await self.clip_repo.delete_clips_by_task(self.db, task_id)

        source_id = task.get("source_id")
        source_url = task.get("source_url")
        if source_id:
            other_tasks = await self.task_repo.count_tasks_by_source_id(
                self.db, source_id, exclude_task_id=task_id
            )
            if other_tasks == 0 and source_url:
                if str(source_url).startswith(UPLOAD_URL_PREFIX):
                    try:
                        video_path = self.video_service.resolve_local_video_path(
                            source_url
                        )
                        delete_upload_source_files(video_path)
                    except Exception as exc:
                        logger.warning(
                            "Failed to delete upload files for task %s: %s",
                            task_id,
                            exc,
                        )
                await self.cache_repo.delete_by_source_url(self.db, source_url)

        await self.task_repo.delete_task(self.db, task_id)

        logger.info("Deleted task %s and associated artifacts", task_id)

    async def update_task_settings(
        self,
        task_id: str,
        font_family: str,
        font_size: int,
        font_color: str,
        caption_template: str,
        apply_to_existing: bool,
    ) -> Dict[str, Any]:
        """Update task-level settings and optionally regenerate all clips."""
        await self.task_repo.update_task_settings(
            self.db,
            task_id,
            font_family,
            font_size,
            font_color,
            caption_template,
        )

        if apply_to_existing:
            await self.regenerate_all_clips_for_task(
                task_id,
                font_family,
                font_size,
                font_color,
                caption_template,
            )

        return await self.get_task_with_clips(task_id) or {}

    async def regenerate_all_clips_for_task(
        self,
        task_id: str,
        font_family: str,
        font_size: int,
        font_color: str,
        caption_template: str,
    ) -> None:
        """Regenerate all clips in a task using existing segment boundaries."""
        task = await self.task_repo.get_task_by_id(self.db, task_id)
        if not task:
            raise ValueError("Task not found")

        source_url = task.get("source_url")
        source_type = task.get("source_type")
        output_format = "vertical"
        add_subtitles = True

        # Preserve original output_format and add_subtitles from task creation (stored in Redis)
        source_payload = await get_redis().get(f"task_source:{task_id}")
        if source_payload:
            parsed = json.loads(source_payload)
            of = parsed.get("output_format", output_format)
            if of in ("vertical", "original"):
                output_format = of
            asub = parsed.get("add_subtitles", add_subtitles)
            if isinstance(asub, bool):
                add_subtitles = asub

        if not source_url or not source_type:
            raise ValueError("Task source URL is missing; cannot regenerate clips")

        clips = await self.clip_repo.get_clips_by_task(self.db, task_id)
        if not clips:
            return

        video_path: Path
        if source_type == "youtube":
            downloaded = await self.video_service.download_video(source_url)
            if not downloaded:
                raise ValueError("Failed to download source video for regeneration")
            video_path = Path(downloaded)
        else:
            video_path = self.video_service.resolve_local_video_path(source_url)
            if not video_path.exists():
                raise ValueError("Source video file no longer exists")

        segments = [
            {
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "text": clip.get("text") or "",
                "relevance_score": clip.get("relevance_score", 0.5),
                "reasoning": clip.get("reasoning")
                or "Regenerated with updated settings",
                "virality_score": clip.get("virality_score", 0),
                "hook_score": clip.get("hook_score", 0),
                "engagement_score": clip.get("engagement_score", 0),
                "value_score": clip.get("value_score", 0),
                "shareability_score": clip.get("shareability_score", 0),
                "hook_type": clip.get("hook_type"),
            }
            for clip in clips
        ]

        clips_info = await self.video_service.create_video_clips(
            video_path,
            segments,
            font_family,
            font_size,
            font_color,
            caption_template,
            output_format,
            add_subtitles,
        )

        existing = await self.clip_repo.get_clips_by_task(self.db, task_id)
        delete_clip_files(existing)
        await self.clip_repo.delete_clips_by_task(self.db, task_id)

        clip_ids = []
        for i, clip_info in enumerate(clips_info):
            clip_id = await self.clip_repo.create_clip(
                self.db,
                task_id=task_id,
                filename=clip_info["filename"],
                file_path=clip_info["path"],
                start_time=clip_info["start_time"],
                end_time=clip_info["end_time"],
                duration=clip_info["duration"],
                text=clip_info.get("text") or "",
                relevance_score=clip_info.get("relevance_score", 0.5),
                reasoning=clip_info.get("reasoning")
                or "Regenerated with updated settings",
                clip_order=i + 1,
                virality_score=clip_info.get("virality_score", 0),
                hook_score=clip_info.get("hook_score", 0),
                engagement_score=clip_info.get("engagement_score", 0),
                value_score=clip_info.get("value_score", 0),
                shareability_score=clip_info.get("shareability_score", 0),
                hook_type=clip_info.get("hook_type"),
            )
            clip_ids.append(clip_id)

        await self.task_repo.update_task_clips(self.db, task_id, clip_ids)

    async def trim_clip(
        self,
        task_id: str,
        clip_id: str,
        start_offset: float,
        end_offset: float,
    ) -> Dict[str, Any]:
        clip = await self.clip_repo.get_clip_by_id(self.db, clip_id)
        if not clip or clip["task_id"] != task_id:
            raise ValueError("Clip not found")

        input_path = Path(clip["file_path"])
        if not input_path.exists():
            raise ValueError("Clip file not found")

        output_path = await run_in_thread(
            trim_clip_file,
            input_path,
            Path(self.config.temp_dir) / "clips",
            start_offset,
            end_offset,
        )
        clip_duration = max(0.1, clip["duration"] - start_offset - end_offset)

        start_seconds = parse_timestamp_to_seconds(clip["start_time"]) + start_offset
        end_seconds = start_seconds + clip_duration

        new_start = self._seconds_to_mmss(start_seconds)
        new_end = self._seconds_to_mmss(end_seconds)

        await self.clip_repo.update_clip(
            self.db,
            clip_id,
            output_path.name,
            str(output_path),
            new_start,
            new_end,
            clip_duration,
            clip.get("text") or "",
        )
        return (await self.clip_repo.get_clip_by_id(self.db, clip_id)) or {}

    async def re_render_clip(
        self,
        task_id: str,
        clip_id: str,
        start_delta_seconds: float,
        end_delta_seconds: float,
        font_family: str,
        font_size: int,
        font_color: str,
        caption_template: str,
        highlight_color: str = "#8B5CF6",
        background_color: str = "#1A1A1ACC",
        position_y: Optional[float] = None,
        replace: bool = False,
        emphasis_callouts: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Re-render a clip from source with adjusted boundaries and style."""
        from ..ai import detect_emphasis_words, score_segment_virality

        async def emit_progress(message: str, stage: str = "rerender"):
            if progress_callback:
                await progress_callback(message, stage)

        clip = await self.clip_repo.get_clip_by_id(self.db, clip_id)
        if not clip or clip["task_id"] != task_id:
            raise ValueError("Clip not found")

        task = await self.task_repo.get_task_by_id(self.db, task_id)
        if not task:
            raise ValueError("Task not found")

        await emit_progress("Preparing clip boundaries…", "prepare")

        _, video_path = await self._resolve_task_transcript_and_video(task)
        video_duration = VideoService._get_file_duration(video_path)
        if not video_duration or video_duration <= 0:
            raise ValueError("Could not determine source video duration")

        start_seconds, end_seconds = compute_re_render_bounds(
            parse_timestamp_to_seconds(clip["start_time"]),
            parse_timestamp_to_seconds(clip["end_time"]),
            start_delta_seconds,
            end_delta_seconds,
            video_duration,
        )

        new_start = self._seconds_to_mmss(start_seconds)
        new_end = self._seconds_to_mmss(end_seconds)

        transcript_text = clip.get("text") or ""
        word_tokens: list[str] = []
        cached = load_cached_transcript_data(video_path)
        if cached:
            words = get_words_in_range(cached, start_seconds, end_seconds)
            if words:
                word_tokens = [
                    str(word.get("text") or "").strip()
                    for word in words
                    if str(word.get("text") or "").strip()
                ]
                transcript_text = " ".join(word_tokens).strip()

        await emit_progress("Scoring segment…", "score")
        rescore = await score_segment_virality(transcript_text)
        virality = rescore.virality
        reasoning = (
            f"Edited from clip {clip_id}. "
            f"{virality.virality_reasoning or 'Re-scored after edit.'}"
        )

        emphasis_words: list[str] = []
        cached_emphasis = clip.get("emphasis_words_json")
        if (
            emphasis_callouts
            and cached_emphasis
            and transcript_text == (clip.get("text") or "")
        ):
            try:
                parsed = json.loads(cached_emphasis)
                if isinstance(parsed, list):
                    emphasis_words = [str(word) for word in parsed if str(word).strip()]
            except (TypeError, json.JSONDecodeError):
                emphasis_words = []

        if emphasis_callouts and not emphasis_words:
            emphasis_words = await detect_emphasis_words(transcript_text, word_tokens)

        segment_dict = {
            "start_time": new_start,
            "end_time": new_end,
            "text": transcript_text,
            "relevance_score": clip.get("relevance_score", 0.0),
            "reasoning": reasoning,
            "virality_score": virality.total_score,
            "hook_score": virality.hook_score,
            "engagement_score": virality.engagement_score,
            "value_score": virality.value_score,
            "shareability_score": virality.shareability_score,
            "hook_type": virality.hook_type,
        }

        clips_output_dir = Path(self.config.temp_dir) / "clips"
        clips_output_dir.mkdir(parents=True, exist_ok=True)
        existing_clips = await self.clip_repo.get_clips_by_task(self.db, task_id)
        if replace:
            clip_order = clip.get("clip_order") or 1
        else:
            clip_order = (
                max((item.get("clip_order", 0) for item in existing_clips), default=0) + 1
            )
        clip_index = max(int(clip_order) - 1, 0)

        await emit_progress("Rendering clip with subtitles…", "render")
        clip_info = await self.video_service.create_single_clip(
            video_path,
            segment_dict,
            clip_index,
            clips_output_dir,
            font_family,
            font_size,
            font_color,
            caption_template,
            "vertical",
            True,
            highlight_color=highlight_color,
            background_color=background_color,
            position_y=position_y,
            emphasis_callouts=emphasis_callouts,
            emphasis_words=emphasis_words,
        )
        if clip_info is None:
            raise ValueError("Failed to re-render clip")

        emphasis_json = json.dumps(emphasis_words) if emphasis_words else None

        if replace:
            old_path = clip.get("file_path")
            new_path = clip_info["path"]
            if old_path and old_path != new_path:
                delete_clip_files([clip])
            await self.clip_repo.update_clip_render(
                self.db,
                clip_id,
                clip_info["filename"],
                clip_info["path"],
                clip_info["start_time"],
                clip_info["end_time"],
                clip_info["duration"],
                transcript_text,
                reasoning,
                virality_score=virality.total_score,
                hook_score=virality.hook_score,
                engagement_score=virality.engagement_score,
                value_score=virality.value_score,
                shareability_score=virality.shareability_score,
                hook_type=virality.hook_type,
                emphasis_words_json=emphasis_json,
            )
            updated_clip = (await self.clip_repo.get_clip_by_id(self.db, clip_id)) or {}
            updated_clip["forked"] = False
            await emit_progress("Clip updated.", "complete")
            return updated_clip

        new_clip_id = await self.clip_repo.create_clip(
            self.db,
            task_id=task_id,
            filename=clip_info["filename"],
            file_path=clip_info["path"],
            start_time=clip_info["start_time"],
            end_time=clip_info["end_time"],
            duration=clip_info["duration"],
            text=transcript_text,
            relevance_score=clip.get("relevance_score", 0.0),
            reasoning=reasoning,
            clip_order=clip_order,
            virality_score=virality.total_score,
            hook_score=virality.hook_score,
            engagement_score=virality.engagement_score,
            value_score=virality.value_score,
            shareability_score=virality.shareability_score,
            hook_type=virality.hook_type,
            emphasis_words_json=emphasis_json,
        )
        await self.db.commit()

        existing_ids = list(task.get("generated_clips_ids") or [])
        if not existing_ids and existing_clips:
            existing_ids = [item["id"] for item in existing_clips]
        if new_clip_id not in existing_ids:
            existing_ids.append(new_clip_id)
        await self.task_repo.update_task_clips(self.db, task_id, existing_ids)

        new_clip = (await self.clip_repo.get_clip_by_id(self.db, new_clip_id)) or {}
        new_clip["parent_clip_id"] = clip_id
        new_clip["forked"] = True
        await emit_progress("Clip saved.", "complete")
        return new_clip

    async def split_clip(
        self, task_id: str, clip_id: str, split_time: float
    ) -> Dict[str, Any]:
        clip = await self.clip_repo.get_clip_by_id(self.db, clip_id)
        if not clip or clip["task_id"] != task_id:
            raise ValueError("Clip not found")

        input_path = Path(clip["file_path"])
        if not input_path.exists():
            raise ValueError("Clip file not found")

        first_path, second_path = await run_in_thread(
            split_clip_file,
            input_path,
            Path(self.config.temp_dir) / "clips",
            split_time,
        )

        start_seconds = parse_timestamp_to_seconds(clip["start_time"])
        clamped_split = max(0.2, min(split_time, float(clip["duration"]) - 0.2))
        split_abs = start_seconds + clamped_split
        end_seconds = parse_timestamp_to_seconds(clip["end_time"])

        await self.clip_repo.update_clip(
            self.db,
            clip_id,
            first_path.name,
            str(first_path),
            clip["start_time"],
            self._seconds_to_mmss(split_abs),
            clamped_split,
            clip.get("text") or "",
        )

        await self.clip_repo.create_clip(
            self.db,
            task_id=task_id,
            filename=second_path.name,
            file_path=str(second_path),
            start_time=self._seconds_to_mmss(split_abs),
            end_time=self._seconds_to_mmss(end_seconds),
            duration=max(0.1, end_seconds - split_abs),
            text=clip.get("text") or "",
            relevance_score=clip.get("relevance_score", 0.5),
            reasoning=clip.get("reasoning") or "Split from original clip",
            clip_order=clip.get("clip_order", 1) + 1,
            virality_score=clip.get("virality_score", 0),
            hook_score=clip.get("hook_score", 0),
            engagement_score=clip.get("engagement_score", 0),
            value_score=clip.get("value_score", 0),
            shareability_score=clip.get("shareability_score", 0),
            hook_type=clip.get("hook_type"),
        )

        await self.clip_repo.reorder_task_clips(self.db, task_id)
        return {"message": "Clip split successfully"}

    async def merge_clips(self, task_id: str, clip_ids: list[str]) -> Dict[str, Any]:
        if len(clip_ids) < 2:
            raise ValueError("At least two clips are required to merge")

        clips = []
        for clip_id in clip_ids:
            clip = await self.clip_repo.get_clip_by_id(self.db, clip_id)
            if not clip or clip["task_id"] != task_id:
                raise ValueError("One or more clips not found")
            clips.append(clip)

        ordered = sorted(clips, key=lambda c: c.get("clip_order", 0))
        merged_path = await run_in_thread(
            merge_clip_files,
            [Path(c["file_path"]) for c in ordered],
            Path(self.config.temp_dir) / "clips",
        )

        start_time = ordered[0]["start_time"]
        end_time = ordered[-1]["end_time"]
        duration = sum(float(c.get("duration", 0.0)) for c in ordered)
        text = " ".join((c.get("text") or "").strip() for c in ordered if c.get("text"))

        first = ordered[0]
        await self.clip_repo.update_clip(
            self.db,
            first["id"],
            merged_path.name,
            str(merged_path),
            start_time,
            end_time,
            duration,
            text,
        )

        for clip in ordered[1:]:
            await self.clip_repo.delete_clip(self.db, clip["id"])

        await self.clip_repo.reorder_task_clips(self.db, task_id)
        return {"message": "Clips merged successfully", "clip_id": first["id"]}

    async def update_clip_captions(
        self,
        task_id: str,
        clip_id: str,
        caption_text: str,
        position: str,
        highlight_words: list[str],
    ) -> Dict[str, Any]:
        clip = await self.clip_repo.get_clip_by_id(self.db, clip_id)
        if not clip or clip["task_id"] != task_id:
            raise ValueError("Clip not found")

        input_path = Path(clip["file_path"])
        if not input_path.exists():
            raise ValueError("Clip file not found")

        output_path = await run_in_thread(
            overlay_custom_captions,
            input_path,
            Path(self.config.temp_dir) / "clips",
            caption_text,
            position,
            highlight_words,
        )

        await self.clip_repo.update_clip(
            self.db,
            clip_id,
            output_path.name,
            str(output_path),
            clip["start_time"],
            clip["end_time"],
            clip["duration"],
            caption_text,
        )
        return (await self.clip_repo.get_clip_by_id(self.db, clip_id)) or {}

    async def get_clip_transcript_words(
        self, task_id: str, clip_id: str
    ) -> list[dict[str, Any]]:
        """Return word-level transcript timings relative to clip start."""
        clip = await self.clip_repo.get_clip_by_id(self.db, clip_id)
        if not clip or clip["task_id"] != task_id:
            raise ValueError("Clip not found")

        task = await self.task_repo.get_task_by_id(self.db, task_id)
        if not task:
            raise ValueError("Task not found")

        _, video_path = await self._resolve_task_transcript_and_video(task)
        cached = load_cached_transcript_data(video_path)
        if not cached:
            return []

        start_seconds = parse_timestamp_to_seconds(clip["start_time"])
        end_seconds = parse_timestamp_to_seconds(clip["end_time"])
        words = get_words_in_range(cached, start_seconds, end_seconds)
        return [
            {
                "text": str(word.get("text") or ""),
                "start": float(word.get("start", 0)),
                "end": float(word.get("end", 0)),
            }
            for word in words
            if str(word.get("text") or "").strip()
        ]

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Return aggregate processing performance metrics."""
        return await self.task_repo.get_performance_metrics(self.db)

    @staticmethod
    def _seconds_to_mmss(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        minutes = total // 60
        secs = total % 60
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _transcript_from_disk_cache(video_path: Path) -> Optional[str]:
        from ..video_utils import load_cached_transcript_data, format_ms_to_timestamp

        data = load_cached_transcript_data(video_path)
        if not data:
            return None

        utterances = data.get("utterances") or []
        if utterances:
            lines = []
            for utterance in utterances:
                start = format_ms_to_timestamp(int(utterance.get("start", 0)))
                end = format_ms_to_timestamp(int(utterance.get("end", 0)))
                text = str(utterance.get("text") or "").strip()
                if text:
                    lines.append(f"[{start} - {end}] {text}")
            if lines:
                return "\n".join(lines)

        text = data.get("text")
        return str(text).strip() if text else None

    async def _resolve_task_transcript_and_video(
        self, task: Dict[str, Any]
    ) -> tuple[str, Path]:
        source_url = task.get("source_url")
        source_type = task.get("source_type")
        processing_mode = task.get("processing_mode") or "quality"
        task_id = task.get("id")

        if not source_url or not source_type:
            raise ValueError("Task source is missing")

        cache_key = self._build_cache_key(source_url, source_type, processing_mode)
        cache_entry = await self.cache_repo.get_cache(self.db, cache_key)
        transcript = (cache_entry or {}).get("transcript_text")

        video_path: Optional[Path] = None
        cached_video = (cache_entry or {}).get("video_path")
        if cached_video:
            candidate = Path(cached_video)
            if candidate.exists():
                video_path = candidate

        if source_type == "youtube":
            if video_path is None:
                downloaded = await self.video_service.download_video(
                    source_url, task_id=task_id
                )
                if not downloaded:
                    raise ValueError("Failed to download source video")
                video_path = Path(downloaded)
        else:
            video_path = self.video_service.resolve_local_video_path(source_url)
            if not video_path.exists():
                raise ValueError("Source video file no longer exists")

        if not transcript:
            transcript = self._transcript_from_disk_cache(video_path)

        if not transcript:
            raise ValueError("Transcript not found for this task")

        return transcript, video_path

    async def generate_clips_from_query(
        self,
        task_id: str,
        query: str,
        clip_types: list[str],
        font_family: str,
        font_size: int,
        font_color: str,
        caption_template: str,
        clip_ready_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Find user-described moments and render custom clips."""
        from ..ai import find_segment_by_user_query

        task = await self.task_repo.get_task_by_id(self.db, task_id)
        if not task:
            raise ValueError("Task not found")
        if task.get("status") != "completed":
            raise ValueError("Task must be completed before generating custom clips")

        normalized_types: list[str] = []
        for clip_type in clip_types:
            if clip_type in ("micro_hook", "deep_context") and clip_type not in normalized_types:
                normalized_types.append(clip_type)
        if not normalized_types:
            raise ValueError("Select at least one clip format")

        transcript, video_path = await self._resolve_task_transcript_and_video(task)
        match_result = await find_segment_by_user_query(
            transcript,
            query,
            normalized_types,  # type: ignore[arg-type]
        )

        existing_clips = await self.clip_repo.get_clips_by_task(self.db, task_id)
        clip_order_start = max(
            (clip.get("clip_order", 0) for clip in existing_clips),
            default=0,
        )
        existing_ids = list(task.get("generated_clips_ids") or [])
        if not existing_ids and existing_clips:
            existing_ids = [clip["id"] for clip in existing_clips]

        clips_output_dir = Path(self.config.temp_dir) / "clips"
        clips_output_dir.mkdir(parents=True, exist_ok=True)

        output_format = "vertical"
        add_subtitles = True
        total = len(match_result.variants)
        new_ids = list(existing_ids)
        created = 0

        for index, variant in enumerate(match_result.variants):
            segment = variant.segment
            assessment = (
                f"Custom clip · {variant.clip_type.replace('_', ' ')} · "
                f"Match {int(variant.match_confidence * 100)}% · "
                f"{variant.quality_verdict}: "
                f"{variant.quality_reasoning or segment.reasoning}"
            )
            segment_dict = {
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "text": segment.text,
                "relevance_score": variant.match_confidence,
                "reasoning": assessment,
                "virality_score": segment.virality.total_score if segment.virality else 0,
                "hook_score": segment.virality.hook_score if segment.virality else 0,
                "engagement_score": segment.virality.engagement_score if segment.virality else 0,
                "value_score": segment.virality.value_score if segment.virality else 0,
                "shareability_score": segment.virality.shareability_score if segment.virality else 0,
                "hook_type": segment.virality.hook_type if segment.virality else None,
            }

            clip_info = await self.video_service.create_single_clip(
                video_path,
                segment_dict,
                len(existing_clips) + index,
                clips_output_dir,
                font_family,
                font_size,
                font_color,
                caption_template,
                output_format,
                add_subtitles,
            )
            if clip_info is None:
                continue

            clip_id = await self.clip_repo.create_clip(
                self.db,
                task_id=task_id,
                filename=clip_info["filename"],
                file_path=clip_info["path"],
                start_time=clip_info["start_time"],
                end_time=clip_info["end_time"],
                duration=clip_info["duration"],
                text=clip_info.get("text", ""),
                relevance_score=clip_info.get("relevance_score", 0.0),
                reasoning=clip_info.get("reasoning", ""),
                clip_order=clip_order_start + index + 1,
                virality_score=clip_info.get("virality_score", 0),
                hook_score=clip_info.get("hook_score", 0),
                engagement_score=clip_info.get("engagement_score", 0),
                value_score=clip_info.get("value_score", 0),
                shareability_score=clip_info.get("shareability_score", 0),
                hook_type=clip_info.get("hook_type"),
            )
            await self.db.commit()
            new_ids.append(clip_id)
            created += 1
            await self.task_repo.update_task_clips(self.db, task_id, new_ids)

            if clip_ready_callback:
                clip_record = await self.clip_repo.get_clip_by_id(self.db, clip_id)
                if clip_record:
                    await clip_ready_callback(index, total, clip_record)

        if created == 0:
            raise RuntimeError("Failed to render custom clips")

        return {
            "clips_created": created,
            "expected_clip_count": total,
        }
