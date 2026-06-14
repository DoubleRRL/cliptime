"""
Video service - handles video processing business logic.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Awaitable
import logging
import json
import subprocess
import asyncio
import time

from ..utils.async_helpers import run_in_thread
from ..video_utils import (
    get_video_transcript,
    create_clips_with_transitions,
    create_optimized_clip,
    encoding_quality_for_mode,
    load_cached_transcript_data,
    parse_timestamp_to_seconds,
)
from ..ai import get_most_relevant_parts_by_transcript
from ..config import Config

logger = logging.getLogger(__name__)
config = Config()
UPLOAD_URL_PREFIX = "upload://"
YOUTUBE_HOST_MARKERS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


class VideoService:
    """Service for video processing operations."""

    @staticmethod
    def _get_file_duration(path: Path) -> Optional[float]:
        """Return video duration in seconds via ffprobe, or None on failure."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    str(path),
                ],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            return None

    @staticmethod
    def resolve_local_video_path(url: str) -> Path:
        """Resolve uploaded-video references without exposing server filesystem paths."""
        if url.startswith(UPLOAD_URL_PREFIX):
            filename = Path(url.removeprefix(UPLOAD_URL_PREFIX)).name
            return Path(config.temp_dir) / "uploads" / filename
        return Path(url)

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        lower = url.strip().lower()
        return any(marker in lower for marker in YOUTUBE_HOST_MARKERS)

    @staticmethod
    def validate_source_url(url: str) -> None:
        """Reject unsupported sources before task creation."""
        if VideoService.is_youtube_url(url):
            raise ValueError(
                "YouTube URLs are no longer supported. Upload a video file instead."
            )
        if url.startswith(UPLOAD_URL_PREFIX):
            return
        if Path(url).exists():
            return
        raise ValueError(
            "Only uploaded videos are supported. Upload a file before starting a session."
        )

    @staticmethod
    def ensure_local_source_type(source_type: str) -> None:
        if source_type == "youtube":
            raise ValueError("YouTube sources are no longer supported")

    @staticmethod
    async def generate_transcript(
        video_path: Path,
        processing_mode: str = "balanced",
        progress_callback: Optional[Callable[[int, str, str], Awaitable[None]]] = None,
    ) -> str:
        """
        Generate transcript from video using AssemblyAI.
        Runs in thread pool to avoid blocking.
        """
        logger.info(f"Generating transcript for: {video_path}")
        speech_model = "best"
        if processing_mode == "fast":
            speech_model = config.fast_mode_transcript_model

        heartbeat_stop = asyncio.Event()

        async def transcription_heartbeat():
            started = time.monotonic()
            while not heartbeat_stop.is_set():
                elapsed = int(time.monotonic() - started)
                minutes, seconds = divmod(elapsed, 60)
                if progress_callback:
                    await progress_callback(
                        20,
                        f"Transcribing audio ({minutes:02d}:{seconds:02d} elapsed)...",
                        "processing",
                    )
                try:
                    await asyncio.wait_for(heartbeat_stop.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    continue

        heartbeat_task = asyncio.create_task(transcription_heartbeat())
        try:
            transcript = await run_in_thread(
                get_video_transcript, video_path, speech_model
            )
        finally:
            heartbeat_stop.set()
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Transcript generated: {len(transcript)} characters")
        return transcript

    @staticmethod
    async def analyze_transcript(
        transcript: str,
        processing_mode: str = "quality",
        progress_callback: Optional[Callable[[int, str, str], Awaitable[None]]] = None,
        transcript_cache: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Analyze transcript with AI to find relevant segments.
        This is already async, no need to wrap.
        """
        logger.info("Starting AI analysis of transcript")
        relevant_parts = await get_most_relevant_parts_by_transcript(
            transcript,
            processing_mode=processing_mode,
            progress_callback=progress_callback,
            transcript_cache=transcript_cache,
        )
        logger.info(
            f"AI analysis complete: {len(relevant_parts.most_relevant_segments)} segments found"
        )
        return relevant_parts

    @staticmethod
    def segment_to_dict(segment: Any) -> Dict[str, Any]:
        """Serialize a transcript segment with virality metadata for rendering."""
        if isinstance(segment, dict):
            return {
                "start_time": segment.get("start_time"),
                "end_time": segment.get("end_time"),
                "text": segment.get("text", ""),
                "relevance_score": segment.get("relevance_score", 0.0),
                "reasoning": segment.get("reasoning", ""),
                "virality_score": segment.get("virality_score", 0),
                "hook_score": segment.get("hook_score", 0),
                "engagement_score": segment.get("engagement_score", 0),
                "value_score": segment.get("value_score", 0),
                "shareability_score": segment.get("shareability_score", 0),
                "hook_type": segment.get("hook_type"),
            }

        virality = getattr(segment, "virality", None)
        return {
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "text": segment.text,
            "relevance_score": segment.relevance_score,
            "reasoning": segment.reasoning,
            "virality_score": virality.total_score if virality else 0,
            "hook_score": virality.hook_score if virality else 0,
            "engagement_score": virality.engagement_score if virality else 0,
            "value_score": virality.value_score if virality else 0,
            "shareability_score": virality.shareability_score if virality else 0,
            "hook_type": virality.hook_type if virality else None,
        }

    @staticmethod
    def apply_ranked_relevance_scores(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Spread relevance scores so the UI is not all 100%."""
        for idx, segment in enumerate(segments):
            segment["relevance_score"] = round(max(0.55, 0.98 - idx * 0.07), 2)
        return segments

    @staticmethod
    def cap_segments_for_mode(
        segments_json: List[Dict[str, Any]], processing_mode: str
    ) -> List[Dict[str, Any]]:
        mode = (processing_mode or "quality").lower()
        if mode == "fast":
            return segments_json[: config.fast_mode_max_clips]
        if mode == "balanced":
            return segments_json[: config.balanced_mode_max_clips]
        return segments_json[: config.quality_mode_max_clips]

    @staticmethod
    async def create_video_clips(
        video_path: Path,
        segments: List[Dict[str, Any]],
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        caption_template: str = "default",
        output_format: str = "vertical",
        add_subtitles: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Create standalone video clips from segments with optional subtitles.
        Runs in thread pool as video processing is CPU-intensive.
        output_format: 'vertical' (9:16) or 'original' (keep source size, faster).
        add_subtitles: False skips subtitles; with original format uses ffmpeg stream copy (no re-encode).
        """
        logger.info(f"Creating {len(segments)} video clips subtitles={add_subtitles}")
        clips_output_dir = Path(config.temp_dir) / "clips"
        clips_output_dir.mkdir(parents=True, exist_ok=True)

        clips_info = await run_in_thread(
            create_clips_with_transitions,
            video_path,
            segments,
            clips_output_dir,
            font_family,
            font_size,
            font_color,
            caption_template,
            output_format,
            add_subtitles,
        )

        logger.info(f"Successfully created {len(clips_info)} clips")
        return clips_info

    MICRO_HOOK_MAX_SECONDS = 30
    DEEP_CONTEXT_MAX_SECONDS = 90

    @staticmethod
    def clamp_segment_timestamps(segment: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce tier duration limits before rendering."""
        from ..timestamp_parse import seconds_to_mmss

        start_seconds = parse_timestamp_to_seconds(segment["start_time"])
        end_seconds = parse_timestamp_to_seconds(segment["end_time"])
        duration = end_seconds - start_seconds
        if duration <= 0:
            return segment

        clip_type = segment.get("clip_type")
        if clip_type == "micro_hook":
            max_duration = VideoService.MICRO_HOOK_MAX_SECONDS
        elif clip_type == "deep_context":
            max_duration = VideoService.DEEP_CONTEXT_MAX_SECONDS
        else:
            max_duration = VideoService.DEEP_CONTEXT_MAX_SECONDS

        if duration <= max_duration:
            return segment

        clamped_end = start_seconds + max_duration
        logger.warning(
            "Clamping clip span %s-%s from %.1fs to %.1fs (tier=%s)",
            segment["start_time"],
            segment["end_time"],
            duration,
            max_duration,
            clip_type or "unknown",
        )
        clamped = dict(segment)
        clamped["end_time"] = seconds_to_mmss(int(clamped_end))
        return clamped

    @staticmethod
    async def create_single_clip(
        video_path: Path,
        segment: Dict[str, Any],
        clip_index: int,
        output_dir: Path,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        caption_template: str = "default",
        output_format: str = "vertical",
        add_subtitles: bool = True,
        highlight_color: str = "#8B5CF6",
        background_color: str = "#1A1A1ACC",
        processing_mode: str = "quality",
        position_y: Optional[float] = None,
        emphasis_callouts: bool = True,
        emphasis_words: Optional[list[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Render a single clip in the thread pool and return clip_info dict, or None on failure."""
        try:
            from ..ai import detect_emphasis_words
            from ..caption_templates import get_template
            from ..video_utils import (
                load_cached_transcript_data,
                get_words_in_range,
                parse_timestamp_to_seconds,
            )

            segment = VideoService.clamp_segment_timestamps(segment)
            start_seconds = parse_timestamp_to_seconds(segment["start_time"])
            end_seconds = parse_timestamp_to_seconds(segment["end_time"])
            duration = end_seconds - start_seconds

            if duration <= 0:
                logger.warning(
                    f"Skipping clip {clip_index + 1}: invalid duration {duration:.1f}s"
                )
                return None

            template = get_template(caption_template)
            if emphasis_callouts is None:
                emphasis_callouts = bool(template.get("emphasis_callouts", True))

            resolved_emphasis = list(emphasis_words or [])
            if emphasis_callouts and not resolved_emphasis:
                transcript_text = str(segment.get("text") or "").strip()
                word_tokens: list[str] = []
                cached = load_cached_transcript_data(video_path)
                if cached:
                    words = get_words_in_range(cached, start_seconds, end_seconds)
                    word_tokens = [
                        str(word.get("text") or "").strip()
                        for word in words
                        if str(word.get("text") or "").strip()
                    ]
                    if word_tokens:
                        transcript_text = " ".join(word_tokens)
                if not word_tokens and transcript_text:
                    word_tokens = transcript_text.split()
                resolved_emphasis = await detect_emphasis_words(
                    transcript_text, word_tokens
                )

            clip_filename = (
                f"clip_{clip_index + 1}_"
                f"{segment['start_time'].replace(':', '')}-"
                f"{segment['end_time'].replace(':', '')}.mp4"
            )
            clip_path = output_dir / clip_filename

            success = await run_in_thread(
                create_optimized_clip,
                video_path,
                start_seconds,
                end_seconds,
                clip_path,
                add_subtitles,
                font_family,
                font_size,
                font_color,
                caption_template,
                output_format,
                highlight_color=highlight_color,
                background_color=background_color,
                encode_quality=encoding_quality_for_mode(processing_mode),
                position_y=position_y,
                emphasis_callouts=emphasis_callouts,
                emphasis_words=resolved_emphasis,
            )

            if not success:
                logger.error(f"Failed to create clip {clip_index + 1}")
                return None

            logger.info(f"Created clip {clip_index + 1}: {duration:.1f}s")
            return {
                "clip_id": clip_index + 1,
                "filename": clip_filename,
                "path": str(clip_path),
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "duration": duration,
                "text": segment.get("text", ""),
                "relevance_score": segment.get("relevance_score", 0.0),
                "reasoning": segment.get("reasoning", ""),
                "virality_score": segment.get("virality_score", 0),
                "hook_score": segment.get("hook_score", 0),
                "engagement_score": segment.get("engagement_score", 0),
                "value_score": segment.get("value_score", 0),
                "shareability_score": segment.get("shareability_score", 0),
                "hook_type": segment.get("hook_type"),
                "emphasis_words": resolved_emphasis,
            }
        except Exception as e:
            logger.error(f"Error creating clip {clip_index + 1}: {e}")
            return None

    @staticmethod
    async def apply_single_transition(
        prev_clip_path: Path,
        current_clip_info: Dict[str, Any],
        clip_index: int,
        output_dir: Path,
    ) -> Dict[str, Any]:
        """Return the original clip info.

        Standalone exports intentionally do not depend on adjacent clips.
        """
        logger.info(
            "Skipping inter-clip transition for clip %s to preserve standalone exports",
            clip_index + 1,
        )
        return current_clip_info

    @staticmethod
    def determine_source_type(url: str) -> str:
        """Uploaded files use the video_url source type."""
        VideoService.validate_source_url(url)
        return "video_url"

    @staticmethod
    async def process_video_complete(
        url: str,
        source_type: str,
        task_id: Optional[str] = None,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        caption_template: str = "default",
        processing_mode: str = "quality",
        output_format: str = "vertical",
        add_subtitles: bool = True,
        cached_transcript: Optional[str] = None,
        cached_analysis_json: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str, str], Awaitable[None]]] = None,
        should_cancel: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> Dict[str, Any]:
        """
        Complete video processing pipeline.
        Returns dict with segments and clips info.

        progress_callback: Optional function to call with progress updates
                          Signature: async def callback(progress: int, message: str, status: str)
        """
        try:
            # Step 1: Get video path (download or use existing)
            if should_cancel and await should_cancel():
                raise Exception("Task cancelled")

            if progress_callback:
                await progress_callback(5, "Loading & validating video...", "processing")

            VideoService.ensure_local_source_type(source_type)
            video_path = VideoService.resolve_local_video_path(url)
            if not video_path.exists():
                raise Exception("Video file not found")

            # Post-download duration guard (catches cases where preflight info was unavailable)
            file_duration = await run_in_thread(
                VideoService._get_file_duration, video_path
            )
            if file_duration and file_duration > config.max_video_duration:
                mins = config.max_video_duration // 60
                raise Exception(
                    f"Video is too long ({int(file_duration) // 60} min). "
                    f"Maximum allowed duration is {mins} minutes."
                )

            # Step 2: Generate transcript
            if should_cancel and await should_cancel():
                raise Exception("Task cancelled")

            if progress_callback:
                await progress_callback(20, "Generating speaker-labeled transcript (ASR)...", "processing")

            transcript = cached_transcript
            if not transcript:
                transcript = await VideoService.generate_transcript(
                    video_path,
                    processing_mode=processing_mode,
                    progress_callback=progress_callback,
                )

            # Step 3: AI analysis
            if should_cancel and await should_cancel():
                raise Exception("Task cancelled")

            if progress_callback:
                await progress_callback(
                    45,
                    "Analyzing content: extracting micro-hooks & deep-context clips...",
                    "processing",
                )

            relevant_parts = None
            if cached_analysis_json:
                try:
                    cached_analysis = json.loads(cached_analysis_json)
                    segments = cached_analysis.get("most_relevant_segments", [])
                    if not segments:
                        micro = cached_analysis.get("micro_hooks") or []
                        deep = cached_analysis.get("deep_context_clips") or []
                        segments = list(micro) + list(deep)

                    if segments:
                        class _SimpleResult:
                            def __init__(self, payload: Dict[str, Any]):
                                self.summary = payload.get("summary")
                                self.key_topics = payload.get("key_topics")
                                self.most_relevant_segments = payload.get(
                                    "most_relevant_segments", []
                                )
                                self.micro_hooks = payload.get("micro_hooks", [])
                                self.deep_context_clips = payload.get(
                                    "deep_context_clips", []
                                )

                        relevant_parts = _SimpleResult(
                            {
                                "summary": cached_analysis.get("summary"),
                                "key_topics": cached_analysis.get("key_topics", []),
                                "most_relevant_segments": segments,
                                "micro_hooks": cached_analysis.get("micro_hooks", []),
                                "deep_context_clips": cached_analysis.get(
                                    "deep_context_clips", []
                                ),
                            }
                        )
                except Exception:
                    relevant_parts = None

            if relevant_parts is None:
                transcript_cache = load_cached_transcript_data(video_path)
                relevant_parts = await VideoService.analyze_transcript(
                    transcript,
                    processing_mode=processing_mode,
                    progress_callback=progress_callback,
                    transcript_cache=transcript_cache,
                )

            # Step 4: Create clips
            if should_cancel and await should_cancel():
                raise Exception("Task cancelled")

            if progress_callback:
                await progress_callback(
                    65,
                    "Analysis complete — mapping speaker seating & preparing clips...",
                    "processing",
                )

            segments_json: List[Dict[str, Any]] = []
            for segment in getattr(relevant_parts, "micro_hooks", []) or []:
                entry = VideoService.segment_to_dict(segment)
                entry["clip_type"] = "micro_hook"
                segments_json.append(entry)
            for segment in getattr(relevant_parts, "deep_context_clips", []) or []:
                entry = VideoService.segment_to_dict(segment)
                entry["clip_type"] = "deep_context"
                segments_json.append(entry)
            if not segments_json:
                segments_json = [
                    VideoService.segment_to_dict(segment)
                    for segment in relevant_parts.most_relevant_segments
                ]

            segments_json = VideoService.apply_ranked_relevance_scores(segments_json)
            segments_json = VideoService.cap_segments_for_mode(
                segments_json, processing_mode
            )

            micro_hooks_json: List[Dict[str, Any]] = []
            deep_context_json: List[Dict[str, Any]] = []
            for segment in getattr(relevant_parts, "micro_hooks", []) or []:
                if isinstance(segment, dict):
                    micro_hooks_json.append(segment)
                else:
                    micro_hooks_json.append(
                        {
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "text": segment.text,
                        }
                    )
            for segment in getattr(relevant_parts, "deep_context_clips", []) or []:
                if isinstance(segment, dict):
                    deep_context_json.append(segment)
                else:
                    deep_context_json.append(
                        {
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "text": segment.text,
                        }
                    )

            return {
                "segments": segments_json,
                "segments_to_render": segments_json,
                "video_path": str(video_path),
                "clips": [],
                "summary": relevant_parts.summary if relevant_parts else None,
                "key_topics": relevant_parts.key_topics if relevant_parts else None,
                "transcript": transcript,
                "analysis_json": json.dumps(
                    {
                        "summary": relevant_parts.summary if relevant_parts else None,
                        "key_topics": relevant_parts.key_topics
                        if relevant_parts
                        else [],
                        "most_relevant_segments": segments_json,
                        "micro_hooks": micro_hooks_json,
                        "deep_context_clips": deep_context_json,
                    }
                ),
            }

        except Exception as e:
            logger.error(f"Error in video processing pipeline: {e}")
            raise
