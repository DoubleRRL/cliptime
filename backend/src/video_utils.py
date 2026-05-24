"""
Utility functions for video-related operations.
Optimized for MoviePy v2, AssemblyAI integration, and high-quality output.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import os
import logging
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import json

import cv2
from moviepy import VideoFileClip, CompositeVideoClip, TextClip, ColorClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut, FadeIn, FadeOut

import assemblyai as aai
import srt
from datetime import timedelta

from .config import Config
from .assemblyai_compat import apply_assemblyai_api_patch, speech_models_for_mode
from .speaker_panels import get_or_calibrate_panels, panel_to_vertical_crop
from .caption_templates import get_template, CAPTION_TEMPLATES
from .font_registry import find_font_path

apply_assemblyai_api_patch()

logger = logging.getLogger(__name__)
config = Config()
TRANSCRIPT_CACHE_SCHEMA_VERSION = 2


class VideoProcessor:
    """Handles video processing operations with optimized settings."""

    def __init__(
        self,
        font_family: str = "THEBOLDFONT",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ):
        self.font_family = font_family
        self.font_size = font_size
        self.font_color = font_color
        resolved_font = find_font_path(font_family, allow_all_user_fonts=True)
        if not resolved_font:
            resolved_font = find_font_path("TikTokSans-Regular")
        if not resolved_font:
            resolved_font = find_font_path("THEBOLDFONT")
        self.font_path = str(resolved_font) if resolved_font else ""

    def get_optimal_encoding_settings(
        self, target_quality: str = "high"
    ) -> Dict[str, Any]:
        """Get optimal encoding settings for different quality levels."""
        settings = {
            "high": {
                "codec": "libx264",
                "audio_codec": "aac",
                "audio_bitrate": "256k",
                "preset": "slow",
                "ffmpeg_params": [
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-profile:v",
                    "high",
                    "-movflags",
                    "+faststart",
                    "-sws_flags",
                    "lanczos",
                ],
            },
            "medium": {
                "codec": "libx264",
                "audio_codec": "aac",
                "bitrate": "4000k",
                "audio_bitrate": "192k",
                "preset": "fast",
                "ffmpeg_params": ["-crf", "23", "-pix_fmt", "yuv420p"],
            },
        }
        return settings.get(target_quality, settings["high"])


def build_transcription_config(speech_model: str = "best") -> aai.TranscriptionConfig:
    """Build an AssemblyAI config compatible with the installed SDK version."""
    import inspect

    kwargs: dict = {
        "speaker_labels": True,
        "punctuate": True,
        "format_text": True,
    }
    params = inspect.signature(aai.TranscriptionConfig.__init__).parameters
    models = speech_models_for_mode(speech_model)

    if "speech_models" in params:
        kwargs["speech_models"] = models
    elif "speech_model" in params:
        # Legacy SDK: set enum for internal use; API patch converts to speech_models.
        kwargs["speech_model"] = (
            aai.SpeechModel.nano if speech_model == "nano" else aai.SpeechModel.best
        )
    else:
        logger.warning(
            "AssemblyAI SDK has no speech model parameter; API patch will inject speech_models"
        )

    return aai.TranscriptionConfig(**kwargs)


def get_video_transcript(video_path: Path, speech_model: str = "best") -> str:
    """Get transcript using AssemblyAI with word-level timing for precise subtitles."""
    logger.info(f"Getting transcript for: {video_path}")

    # Configure AssemblyAI
    aai.settings.api_key = config.assembly_ai_api_key
    transcriber = aai.Transcriber()

    config_obj = build_transcription_config(speech_model)

    try:
        logger.info("Starting AssemblyAI transcription")
        transcript = transcriber.transcribe(str(video_path), config=config_obj)

        if transcript.status == aai.TranscriptStatus.error:
            logger.error(f"AssemblyAI transcription failed: {transcript.error}")
            raise Exception(f"Transcription failed: {transcript.error}")

        formatted_lines = format_transcript_for_analysis(transcript)

        # Cache the raw transcript for subtitle generation
        cache_transcript_data(video_path, transcript)

        result = "\n".join(formatted_lines)
        logger.info(
            f"Transcript formatted: {len(formatted_lines)} segments, {len(result)} chars"
        )
        return result

    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        raise


def cache_transcript_data(video_path: Path, transcript) -> None:
    """Cache AssemblyAI transcript data for subtitle generation."""
    cache_path = video_path.with_suffix(".transcript_cache.json")

    words_data = []
    if transcript.words:
        words_data = [_serialize_transcript_word(word) for word in transcript.words]

    utterances_data = []
    if getattr(transcript, "utterances", None):
        utterances_data = [
            {
                "text": utterance.text,
                "start": utterance.start,
                "end": utterance.end,
                "speaker": getattr(utterance, "speaker", None),
                "words": [
                    _serialize_transcript_word(word)
                    for word in getattr(utterance, "words", []) or []
                ],
            }
            for utterance in transcript.utterances
        ]

    cache_data = {
        "version": TRANSCRIPT_CACHE_SCHEMA_VERSION,
        "words": words_data,
        "utterances": utterances_data,
        "text": transcript.text,
    }

    with open(cache_path, "w") as f:
        json.dump(cache_data, f)

    logger.info(f"Cached {len(words_data)} words to {cache_path}")


def load_cached_transcript_data(video_path: Path) -> Optional[Dict]:
    """Load cached AssemblyAI transcript data."""
    cache_path = video_path.with_suffix(".transcript_cache.json")

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r") as f:
            payload = json.load(f)
            if "version" not in payload:
                payload["version"] = TRANSCRIPT_CACHE_SCHEMA_VERSION
                payload.setdefault("utterances", [])
            return payload
    except Exception as e:
        logger.warning(f"Failed to load transcript cache: {e}")
        return None


def _serialize_transcript_word(word) -> Dict[str, Any]:
    return {
        "text": word.text,
        "start": word.start,
        "end": word.end,
        "confidence": word.confidence if hasattr(word, "confidence") else 1.0,
        "speaker": getattr(word, "speaker", None),
    }


def format_transcript_for_analysis(transcript) -> List[str]:
    """Format transcripts into readable timestamped segments for AI analysis."""
    utterances = getattr(transcript, "utterances", None) or []
    if utterances:
        formatted_lines = []
        for utterance in utterances:
            start_time = format_ms_to_timestamp(utterance.start)
            end_time = format_ms_to_timestamp(utterance.end)
            speaker = getattr(utterance, "speaker", None)
            speaker_prefix = f"Speaker {speaker}: " if speaker else ""
            formatted_lines.append(
                f"[{start_time} - {end_time}] {speaker_prefix}{utterance.text}"
            )
        return formatted_lines

    formatted_lines = []
    words = getattr(transcript, "words", None) or []
    if not words:
        return formatted_lines

    logger.info(f"Processing {len(words)} words with precise timing")

    current_segment = []
    current_start = None
    segment_word_count = 0
    max_words_per_segment = 8

    for word in words:
        if current_start is None:
            current_start = word.start

        current_segment.append(word.text)
        segment_word_count += 1

        if (
            segment_word_count >= max_words_per_segment
            or word.text.endswith(".")
            or word.text.endswith("!")
            or word.text.endswith("?")
        ):
            if current_segment:
                start_time = format_ms_to_timestamp(current_start)
                end_time = format_ms_to_timestamp(word.end)
                text = " ".join(current_segment)
                formatted_lines.append(f"[{start_time} - {end_time}] {text}")

            current_segment = []
            current_start = None
            segment_word_count = 0

    if current_segment and current_start is not None:
        start_time = format_ms_to_timestamp(current_start)
        end_time = format_ms_to_timestamp(words[-1].end)
        text = " ".join(current_segment)
        formatted_lines.append(f"[{start_time} - {end_time}] {text}")

    return formatted_lines


def format_ms_to_timestamp(ms: int) -> str:
    """Format milliseconds to MM:SS format."""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def round_to_even(value: int) -> int:
    """Round integer to nearest even number for H.264 compatibility."""
    return value - (value % 2)


def get_scaled_font_size(base_font_size: int, video_width: int) -> int:
    """Scale caption font size by output width with sensible bounds."""
    scaled_size = int(base_font_size * (video_width / 720))
    return max(24, min(64, scaled_size))


def get_subtitle_max_width(video_width: int) -> int:
    """Return max subtitle text width with horizontal safe margins."""
    horizontal_padding = max(40, int(video_width * 0.06))
    return max(200, video_width - (horizontal_padding * 2))


def get_safe_vertical_position(
    video_height: int, text_height: int, position_y: float
) -> int:
    """Return subtitle y position clamped inside a top/bottom safe area."""
    min_top_padding = max(40, int(video_height * 0.05))
    min_bottom_padding = max(120, int(video_height * 0.10))

    desired_y = int(video_height * position_y - text_height // 2)
    max_y = video_height - min_bottom_padding - text_height
    return max(min_top_padding, min(desired_y, max_y))


def detect_optimal_crop_region(
    video_clip: VideoFileClip,
    start_time: float,
    end_time: float,
    target_ratio: float = 9 / 16,
) -> Tuple[int, int, int, int]:
    """Detect optimal crop region using improved face detection."""
    try:
        original_width, original_height = video_clip.size

        # Calculate target dimensions and ensure they're even
        if original_width / original_height > target_ratio:
            new_width = round_to_even(int(original_height * target_ratio))
            new_height = round_to_even(original_height)
        else:
            new_width = round_to_even(original_width)
            new_height = round_to_even(int(original_width / target_ratio))

        # Try improved face detection
        face_centers = detect_faces_in_clip(video_clip, start_time, end_time)

        # Calculate crop position
        if face_centers:
            # Use weighted average of face centers with temporal consistency
            total_weight = sum(
                area * confidence for _, _, area, confidence in face_centers
            )
            if total_weight > 0:
                weighted_x = (
                    sum(
                        x * area * confidence for x, y, area, confidence in face_centers
                    )
                    / total_weight
                )
                weighted_y = (
                    sum(
                        y * area * confidence for x, y, area, confidence in face_centers
                    )
                    / total_weight
                )

                # Add slight bias towards upper portion for better face framing
                weighted_y = max(0, weighted_y - new_height * 0.1)

                x_offset = max(
                    0, min(int(weighted_x - new_width // 2), original_width - new_width)
                )
                y_offset = max(
                    0,
                    min(
                        int(weighted_y - new_height // 2), original_height - new_height
                    ),
                )

                logger.info(
                    f"Face-centered crop: {len(face_centers)} faces detected with improved algorithm"
                )
            else:
                # Center crop
                x_offset = (
                    (original_width - new_width) // 2
                    if original_width > new_width
                    else 0
                )
                y_offset = (
                    (original_height - new_height) // 2
                    if original_height > new_height
                    else 0
                )
        else:
            # Center crop
            x_offset = (
                (original_width - new_width) // 2 if original_width > new_width else 0
            )
            y_offset = (
                (original_height - new_height) // 2
                if original_height > new_height
                else 0
            )
            logger.info("Using center crop (no faces detected)")

        # Ensure offsets are even too
        x_offset = round_to_even(x_offset)
        y_offset = round_to_even(y_offset)

        logger.info(
            f"Crop dimensions: {new_width}x{new_height} at offset ({x_offset}, {y_offset})"
        )
        return (x_offset, y_offset, new_width, new_height)

    except Exception as e:
        logger.error(f"Error in crop detection: {e}")
        # Fallback to center crop
        original_width, original_height = video_clip.size
        if original_width / original_height > target_ratio:
            new_width = round_to_even(int(original_height * target_ratio))
            new_height = round_to_even(original_height)
        else:
            new_width = round_to_even(original_width)
            new_height = round_to_even(int(original_width / target_ratio))

        x_offset = (
            round_to_even((original_width - new_width) // 2)
            if original_width > new_width
            else 0
        )
        y_offset = (
            round_to_even((original_height - new_height) // 2)
            if original_height > new_height
            else 0
        )

        return (x_offset, y_offset, new_width, new_height)


def detect_faces_in_clip(
    video_clip: VideoFileClip, start_time: float, end_time: float
) -> List[Tuple[int, int, int, float]]:
    """
    Improved face detection using multiple methods and temporal consistency.
    Returns list of (x, y, area, confidence) tuples.
    """
    face_centers = []

    try:
        # Try to use MediaPipe (most accurate)
        mp_face_detection = None
        try:
            import mediapipe as mp

            mp_face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,  # 0 for short-range (better for close faces)
                min_detection_confidence=0.5,
            )
            logger.info("Using MediaPipe face detector")
        except ImportError:
            logger.info("MediaPipe not available, falling back to OpenCV")
        except Exception as e:
            logger.warning(f"MediaPipe face detector failed to initialize: {e}")

        # Initialize OpenCV face detectors as fallback
        haar_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Try to load DNN face detector (more accurate than Haar)
        dnn_net = None
        try:
            # Load OpenCV's DNN face detector
            prototxt_path = cv2.data.haarcascades.replace(
                "haarcascades", "opencv_face_detector.pbtxt"
            )
            model_path = cv2.data.haarcascades.replace(
                "haarcascades", "opencv_face_detector_uint8.pb"
            )

            # If DNN model files don't exist, we'll fall back to Haar cascade
            import os

            if os.path.exists(prototxt_path) and os.path.exists(model_path):
                dnn_net = cv2.dnn.readNetFromTensorflow(model_path, prototxt_path)
                logger.info("OpenCV DNN face detector loaded as backup")
            else:
                logger.info("OpenCV DNN face detector not available")
        except Exception:
            logger.info("OpenCV DNN face detector failed to load")

        # Sample more frames for better face detection (every 0.5 seconds)
        duration = end_time - start_time
        sample_interval = min(0.5, duration / 10)  # At least 10 samples, max every 0.5s
        sample_times = []

        current_time = start_time
        while current_time < end_time:
            sample_times.append(current_time)
            current_time += sample_interval

        # Ensure we always sample the middle and end
        if duration > 1.0:
            middle_time = start_time + duration / 2
            if middle_time not in sample_times:
                sample_times.append(middle_time)

        sample_times = [t for t in sample_times if t < end_time]
        logger.info(f"Sampling {len(sample_times)} frames for face detection")

        for sample_time in sample_times:
            try:
                frame = video_clip.get_frame(sample_time)
                height, width = frame.shape[:2]
                detected_faces = []

                # Try MediaPipe first (most accurate)
                if mp_face_detection is not None:
                    try:
                        # MediaPipe expects RGB format
                        results = mp_face_detection.process(frame)

                        if results.detections:
                            for detection in results.detections:
                                bbox = detection.location_data.relative_bounding_box
                                confidence = detection.score[0]

                                # Convert relative coordinates to absolute
                                x = int(bbox.xmin * width)
                                y = int(bbox.ymin * height)
                                w = int(bbox.width * width)
                                h = int(bbox.height * height)

                                if w > 30 and h > 30:  # Minimum face size
                                    detected_faces.append((x, y, w, h, confidence))
                    except Exception as e:
                        logger.warning(
                            f"MediaPipe detection failed for frame at {sample_time}s: {e}"
                        )

                # If MediaPipe didn't find faces, try DNN detector
                if not detected_faces and dnn_net is not None:
                    try:
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        blob = cv2.dnn.blobFromImage(
                            frame_bgr, 1.0, (300, 300), [104, 117, 123]
                        )
                        dnn_net.setInput(blob)
                        detections = dnn_net.forward()

                        for i in range(detections.shape[2]):
                            confidence = detections[0, 0, i, 2]
                            if confidence > 0.5:  # Confidence threshold
                                x1 = int(detections[0, 0, i, 3] * width)
                                y1 = int(detections[0, 0, i, 4] * height)
                                x2 = int(detections[0, 0, i, 5] * width)
                                y2 = int(detections[0, 0, i, 6] * height)

                                w = x2 - x1
                                h = y2 - y1

                                if w > 30 and h > 30:  # Minimum face size
                                    detected_faces.append((x1, y1, w, h, confidence))
                    except Exception as e:
                        logger.warning(
                            f"DNN detection failed for frame at {sample_time}s: {e}"
                        )

                # If still no faces found, use Haar cascade
                if not detected_faces:
                    try:
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

                        faces = haar_cascade.detectMultiScale(
                            gray,
                            scaleFactor=1.05,  # More sensitive
                            minNeighbors=3,  # Less strict
                            minSize=(40, 40),  # Smaller minimum size
                            maxSize=(
                                int(width * 0.7),
                                int(height * 0.7),
                            ),  # Maximum size limit
                        )

                        for x, y, w, h in faces:
                            # Estimate confidence based on face size and position
                            face_area = w * h
                            relative_size = face_area / (width * height)
                            confidence = min(
                                0.9, 0.3 + relative_size * 2
                            )  # Rough confidence estimate
                            detected_faces.append((x, y, w, h, confidence))
                    except Exception as e:
                        logger.warning(
                            f"Haar cascade detection failed for frame at {sample_time}s: {e}"
                        )

                # Process detected faces
                for x, y, w, h, confidence in detected_faces:
                    face_center_x = x + w // 2
                    face_center_y = y + h // 2
                    face_area = w * h

                    # Filter out very small or very large faces
                    frame_area = width * height
                    relative_area = face_area / frame_area

                    if (
                        0.005 < relative_area < 0.3
                    ):  # Face should be 0.5% to 30% of frame
                        face_centers.append(
                            (face_center_x, face_center_y, face_area, confidence)
                        )

            except Exception as e:
                logger.warning(f"Error detecting faces in frame at {sample_time}s: {e}")
                continue

        # Close MediaPipe detector
        if mp_face_detection is not None:
            mp_face_detection.close()

        # Remove outliers (faces that are very far from the median position)
        if len(face_centers) > 2:
            face_centers = filter_face_outliers(face_centers)

        logger.info(f"Detected {len(face_centers)} reliable face centers")
        return face_centers

    except Exception as e:
        logger.error(f"Error in face detection: {e}")
        return []


def filter_face_outliers(
    face_centers: List[Tuple[int, int, int, float]],
) -> List[Tuple[int, int, int, float]]:
    """Remove face detections that are outliers (likely false positives)."""
    if len(face_centers) < 3:
        return face_centers

    try:
        # Calculate median position
        x_positions = [x for x, y, area, conf in face_centers]
        y_positions = [y for x, y, area, conf in face_centers]

        median_x = np.median(x_positions)
        median_y = np.median(y_positions)

        # Calculate standard deviation
        std_x = np.std(x_positions)
        std_y = np.std(y_positions)

        # Filter out faces that are more than 2 standard deviations away
        filtered_faces = []
        for face in face_centers:
            x, y, area, conf = face
            if abs(x - median_x) <= 2 * std_x and abs(y - median_y) <= 2 * std_y:
                filtered_faces.append(face)

        logger.info(
            f"Filtered {len(face_centers)} -> {len(filtered_faces)} faces (removed outliers)"
        )
        return (
            filtered_faces if filtered_faces else face_centers
        )  # Return original if all filtered

    except Exception as e:
        logger.warning(f"Error filtering face outliers: {e}")
        return face_centers


def parse_timestamp_to_seconds(timestamp_str: str) -> float:
    """Parse timestamp string to seconds (supports ranges like '09 - 10')."""
    from .timestamp_parse import parse_timestamp_to_seconds as _shared_parse

    try:
        result = _shared_parse(timestamp_str)
        logger.info("Parsed '%s' -> %ss", timestamp_str, result)
        return result
    except (ValueError, IndexError) as e:
        logger.error("Failed to parse timestamp '%s': %s", timestamp_str, e)
        return 0.0


def get_words_in_range(
    transcript_data: Dict, clip_start: float, clip_end: float
) -> List[Dict]:
    """Extract words that fall within a clip timerange."""
    if not transcript_data or not transcript_data.get("words"):
        return []

    clip_start_ms = int(clip_start * 1000)
    clip_end_ms = int(clip_end * 1000)

    relevant_words = []
    for word_data in transcript_data["words"]:
        word_start = word_data["start"]
        word_end = word_data["end"]

        if word_start < clip_end_ms and word_end > clip_start_ms:
            relative_start = max(0, (word_start - clip_start_ms) / 1000.0)
            relative_end = min(
                (clip_end_ms - clip_start_ms) / 1000.0,
                (word_end - clip_start_ms) / 1000.0,
            )

            if relative_end > relative_start:
                relevant_words.append(
                    {
                        "text": word_data["text"],
                        "start": relative_start,
                        "end": relative_end,
                        "confidence": word_data.get("confidence", 1.0),
                        "speaker": word_data.get("speaker"),
                    }
                )

    return relevant_words


def create_assemblyai_subtitles(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    video_width: int,
    video_height: int,
    font_family: str = "THEBOLDFONT",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "default",
    highlight_color: Optional[str] = None,
    background_color: Optional[str] = None,
    layout_timeline: Optional[List] = None,
) -> List[TextClip]:
    """Create subtitles using AssemblyAI's precise word timing with template support."""
    transcript_data = load_cached_transcript_data(video_path)

    if not transcript_data or not transcript_data.get("words"):
        logger.warning("No cached transcript data available for subtitles")
        return []

    # Get template settings
    template = get_template(caption_template)
    animation_type = template.get("animation", "none")

    effective_font_family = font_family or template["font_family"]
    effective_font_size = int(font_size) if font_size else int(template["font_size"])
    effective_font_color = font_color or template["font_color"]
    effective_template = {
        **template,
        "font_size": effective_font_size,
        "font_color": effective_font_color,
        "font_family": effective_font_family,
    }
    if highlight_color:
        effective_template["highlight_color"] = highlight_color
    if background_color:
        effective_template["background_color"] = background_color

    logger.info(
        f"Creating subtitles with template '{caption_template}', animation: {animation_type}"
    )

    # Get words in range
    relevant_words = get_words_in_range(transcript_data, clip_start, clip_end)

    if not relevant_words:
        logger.warning("No words found in clip timerange")
        return []

    # Choose subtitle creation method based on animation type
    if animation_type == "karaoke":
        return create_karaoke_subtitles(
            relevant_words,
            video_width,
            video_height,
            effective_template,
            effective_font_family,
            layout_timeline=layout_timeline,
        )
    elif animation_type == "pop":
        return create_pop_subtitles(
            relevant_words,
            video_width,
            video_height,
            effective_template,
            effective_font_family,
        )
    elif animation_type == "fade":
        return create_fade_subtitles(
            relevant_words,
            video_width,
            video_height,
            effective_template,
            effective_font_family,
        )
    else:
        # Default static subtitles
        return create_static_subtitles(
            relevant_words,
            video_width,
            video_height,
            effective_template,
            effective_font_family,
        )


def create_static_subtitles(
    relevant_words: List[Dict],
    video_width: int,
    video_height: int,
    template: Dict,
    font_family: str,
) -> List[TextClip]:
    """Create standard static subtitles (original behavior)."""
    subtitle_clips = []
    processor = VideoProcessor(
        font_family, template["font_size"], template["font_color"]
    )

    calculated_font_size = get_scaled_font_size(template["font_size"], video_width)
    position_y = template.get("position_y", 0.75)
    max_text_width = get_subtitle_max_width(video_width)

    words_per_subtitle = 3
    for i in range(0, len(relevant_words), words_per_subtitle):
        word_group = relevant_words[i : i + words_per_subtitle]
        if not word_group:
            continue

        segment_start = word_group[0]["start"]
        segment_end = word_group[-1]["end"]
        segment_duration = segment_end - segment_start

        if segment_duration < 0.1:
            continue

        text = " ".join(word["text"] for word in word_group)

        try:
            stroke_color = template.get("stroke_color", "black")
            stroke_width = template.get("stroke_width", 1)

            text_clip = (
                TextClip(
                    text=text,
                    font=processor.font_path,
                    font_size=calculated_font_size,
                    color=template["font_color"],
                    stroke_color=stroke_color if stroke_color else None,
                    stroke_width=stroke_width if stroke_color else 0,
                    method="caption",
                    size=(max_text_width, None),
                    text_align="center",
                    interline=6,
                )
                .with_duration(segment_duration)
                .with_start(segment_start)
            )

            text_height = text_clip.size[1] if text_clip.size else 40
            vertical_position = get_safe_vertical_position(
                video_height, text_height, position_y
            )
            text_clip = text_clip.with_position(("center", vertical_position))

            subtitle_clips.append(text_clip)

        except Exception as e:
            logger.warning(f"Failed to create subtitle for '{text}': {e}")
            continue

    logger.info(f"Created {len(subtitle_clips)} static subtitle elements")
    return subtitle_clips


# ---------------------------------------------------------------------------
# Speaker Seating Map & Dynamic Camera Cuts (OpusClip-style)
# ---------------------------------------------------------------------------


def build_speaker_seating_map(
    video_clip: VideoFileClip,
    transcript_data: Dict,
) -> Dict[str, int]:
    """
    Scan the first few speaking turns of each speaker, run face detection on
    those frames, and return ``{speaker_id: median_face_center_x}``.

    Returns an empty dict if fewer than two speakers exist or face detection
    is unavailable – callers should treat that as "use center crop".
    """
    utterances = transcript_data.get("utterances") or []
    if not utterances:
        logger.info("No utterances found – skipping speaker seating map")
        return {}

    MAX_TURNS = 3  # sample at most 3 utterances per speaker
    speaker_sample_times: Dict[str, List[float]] = {}
    for utt in utterances:
        speaker = utt.get("speaker")
        if not speaker:
            continue
        bucket = speaker_sample_times.setdefault(speaker, [])
        if len(bucket) < MAX_TURNS:
            start_s = utt.get("start", 0) / 1000.0
            end_s = utt.get("end", 0) / 1000.0
            mid = max(0.0, min((start_s + end_s) / 2.0, video_clip.duration - 0.1))
            bucket.append(mid)

    if len(speaker_sample_times) < 2:
        logger.info(
            f"{len(speaker_sample_times)} speaker(s) detected – skipping seating map"
        )
        return {}

    seating_map: Dict[str, int] = {}
    for speaker, sample_times in speaker_sample_times.items():
        x_coords: List[int] = []
        for t in sample_times:
            try:
                frame = video_clip.get_frame(t)
                fh, fw = frame.shape[:2]

                # Try MediaPipe first (most accurate)
                detected = False
                try:
                    import mediapipe as mp  # type: ignore
                    mp_fd = mp.solutions.face_detection.FaceDetection(
                        model_selection=0, min_detection_confidence=0.4
                    )
                    results = mp_fd.process(frame)
                    mp_fd.close()
                    if results.detections:
                        detected = True
                        for det in results.detections:
                            bbox = det.location_data.relative_bounding_box
                            cx = int((bbox.xmin + bbox.width / 2) * fw)
                            x_coords.append(cx)
                except Exception:
                    pass

                # Haar cascade fallback
                if not detected:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                    cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                    )
                    faces = cascade.detectMultiScale(
                        gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30)
                    )
                    for (fx, fy, fww, fhh) in faces:
                        x_coords.append(fx + fww // 2)

            except Exception as exc:
                logger.warning(
                    f"Face detection for speaker {speaker} at t={t:.2f}s failed: {exc}"
                )

        if x_coords:
            seating_map[speaker] = int(np.median(x_coords))
            logger.info(
                f"Speaker {speaker} → face x={seating_map[speaker]} "
                f"(from {len(x_coords)} detection(s))"
            )
        else:
            logger.info(f"No face detections for speaker {speaker}")

    return seating_map


def build_speaker_turns(
    transcript_data: Dict,
    clip_start_ms: int,
    clip_end_ms: int,
    min_turn_duration: float = 1.2,
) -> List[Dict]:
    """
    Segment the word list into debounced speaker turns within
    ``[clip_start_ms, clip_end_ms]``.

    Each returned dict has the form::

        {"speaker": str | None, "start_ms": int, "end_ms": int}

    Back-channels shorter than ``min_turn_duration`` seconds are merged into
    the preceding turn to prevent disorienting rapid cuts.
    """
    words = transcript_data.get("words") or []
    clip_words = [
        w for w in words
        if w.get("start", 0) < clip_end_ms and w.get("end", 0) > clip_start_ms
    ]
    if not clip_words:
        return []

    # Build raw turns from consecutive words sharing the same speaker
    raw_turns: List[Dict] = []
    cur_spk = clip_words[0].get("speaker")
    t_start = clip_words[0]["start"]
    t_end = clip_words[0]["end"]

    for word in clip_words[1:]:
        spk = word.get("speaker")
        if spk == cur_spk:
            t_end = word["end"]
        else:
            raw_turns.append({"speaker": cur_spk, "start_ms": t_start, "end_ms": t_end})
            cur_spk, t_start, t_end = spk, word["start"], word["end"]
    raw_turns.append({"speaker": cur_spk, "start_ms": t_start, "end_ms": t_end})

    # Debounce: merge short turns into the previous one
    min_ms = int(min_turn_duration * 1000)
    merged: List[Dict] = []
    for turn in raw_turns:
        dur = turn["end_ms"] - turn["start_ms"]
        if merged and dur < min_ms:
            merged[-1]["end_ms"] = turn["end_ms"]
        else:
            merged.append(dict(turn))

    # Clamp to clip boundaries and drop zero-length turns
    for t in merged:
        t["start_ms"] = max(t["start_ms"], clip_start_ms)
        t["end_ms"] = min(t["end_ms"], clip_end_ms)
    return [t for t in merged if t["end_ms"] > t["start_ms"]]


@dataclass
class DirectedLayoutContext:
    timeline: List
    panels: Dict[str, Dict[str, int]]
    riverside_feed: bool
    seating_map: Dict[str, int]
    clip_start_ms: int


def prepare_directed_layout(
    full_video: VideoFileClip,
    transcript_data: Dict,
    clip_start_s: float,
    clip_end_s: float,
    video_path: Optional[Path] = None,
) -> DirectedLayoutContext:
    """Build panels, seating, and layout timeline for a clip segment."""
    from .layout_director import (
        build_layout_timeline,
        build_portrait_layout_timeline,
    )
    from .speaker_panels import (
        default_riverside_panels,
        is_portrait_source,
        is_riverside_dual_feed,
    )

    src_w, src_h = full_video.size
    panels: Dict[str, Dict[str, int]] = {}
    if video_path is not None:
        panels = get_or_calibrate_panels(full_video, transcript_data, video_path)

    clip_start_ms = int(clip_start_s * 1000)
    clip_end_ms = int(clip_end_s * 1000)
    seating_map = build_speaker_seating_map(full_video, transcript_data)

    if is_portrait_source(src_w, src_h):
        timeline = build_portrait_layout_timeline(
            full_video, clip_start_s, clip_end_s
        )
        riverside_feed = False
    else:
        riverside_feed = is_riverside_dual_feed(src_w, src_h, panels)
        if riverside_feed and len(panels) < 2:
            panels = default_riverside_panels(src_w, src_h)
        timeline = build_layout_timeline(
            transcript_data,
            clip_start_ms,
            clip_end_ms,
            src_w=src_w,
            src_h=src_h,
            full_video=full_video,
            panels=panels,
        )

    return DirectedLayoutContext(
        timeline=timeline,
        panels=panels,
        riverside_feed=riverside_feed,
        seating_map=seating_map,
        clip_start_ms=clip_start_ms,
    )


def create_directed_clip(
    full_video: VideoFileClip,
    clip: VideoFileClip,
    transcript_data: Dict,
    clip_start_s: float,
    clip_end_s: float,
    target_w: int,
    target_h: int,
    video_path: Optional[Path] = None,
    layout_ctx: Optional[DirectedLayoutContext] = None,
) -> VideoFileClip:
    """
    Return a 9:16 clip with Riverside-style directed layouts.

    Landscape sources: solo speaker crops plus dual stacked segments during
    reaction/overlap moments. Portrait sources: full-frame pass-through.
    """
    from moviepy import concatenate_videoclips  # local import to avoid circular

    from .layout_director import (
        render_dual_stack_segment,
        render_pass_through_segment,
        render_riverside_dual_stack_segment,
        render_riverside_solo_segment,
        render_solo_segment,
    )

    CROSSFADE = 0.1  # seconds

    try:
        ctx = layout_ctx or prepare_directed_layout(
            full_video,
            transcript_data,
            clip_start_s,
            clip_end_s,
            video_path=video_path,
        )
        src_w, src_h = full_video.size
        timeline = ctx.timeline
        panels = ctx.panels
        riverside_feed = ctx.riverside_feed
        seating_map = ctx.seating_map

        segments: List[VideoFileClip] = []
        for seg in timeline:
            t_start = seg.start_ms / 1000.0
            t_end = seg.end_ms / 1000.0
            rendered: Optional[VideoFileClip] = None

            if seg.mode == "pass_through":
                rendered = render_pass_through_segment(
                    full_video, t_start, t_end, target_w, target_h
                )
            elif seg.mode == "dual" and len(panels) >= 2:
                if riverside_feed:
                    rendered = render_riverside_dual_stack_segment(
                        full_video,
                        t_start,
                        t_end,
                        panels,
                        src_w,
                        src_h,
                        target_w,
                        target_h,
                        seating_map=seating_map,
                    )
                else:
                    rendered = render_dual_stack_segment(
                        full_video,
                        t_start,
                        t_end,
                        panels,
                        src_w,
                        src_h,
                        target_w,
                        target_h,
                    )
            elif riverside_feed:
                rendered = render_riverside_solo_segment(
                    full_video,
                    t_start,
                    t_end,
                    seg.speaker,
                    panels,
                    src_w,
                    src_h,
                    target_w,
                    target_h,
                    seating_map=seating_map,
                )
            else:
                rendered = render_solo_segment(
                    full_video,
                    t_start,
                    t_end,
                    seg.speaker,
                    panels,
                    src_w,
                    src_h,
                    target_w,
                    target_h,
                    seating_map=seating_map,
                )

            if rendered is not None:
                segments.append(rendered)

        if segments:
            if len(segments) == 1:
                logger.info("Directed layout applied (single segment)")
                return segments[0]
            faded: List[VideoFileClip] = [segments[0]]
            for seg_clip in segments[1:]:
                if seg_clip.duration > CROSSFADE * 2:
                    seg_clip = seg_clip.with_effects([CrossFadeIn(CROSSFADE)])
                faded.append(seg_clip)
            result = concatenate_videoclips(faded, method="compose")
            logger.info(
                "Directed layout applied: %s segments (riverside_feed=%s)",
                len(segments),
                riverside_feed,
            )
            return result

    except Exception as exc:
        logger.warning(
            f"Directed layout failed, falling back to face-centred crop: {exc}"
        )

    # --- Fallback: static face-centred crop ---
    x_offset, y_offset, new_width, new_height = detect_optimal_crop_region(
        full_video, clip_start_s, clip_end_s, target_ratio=9 / 16
    )
    fallback = clip.cropped(
        x1=x_offset, y1=y_offset,
        x2=x_offset + new_width, y2=y_offset + new_height,
    )
    if (fallback.size[0], fallback.size[1]) != (target_w, target_h):
        fallback = fallback.resized((target_w, target_h))
    return fallback


def create_speaker_cut_clip(
    full_video: VideoFileClip,
    clip: VideoFileClip,
    transcript_data: Dict,
    clip_start_s: float,
    clip_end_s: float,
    target_w: int,
    target_h: int,
    video_path: Optional[Path] = None,
) -> VideoFileClip:
    """Backward-compatible alias for :func:`create_directed_clip`."""
    return create_directed_clip(
        full_video,
        clip,
        transcript_data,
        clip_start_s,
        clip_end_s,
        target_w,
        target_h,
        video_path=video_path,
    )


EMOJI_KEYWORDS = {
    # Finance & Money
    "money": "🤑", "rich": "🤑", "wealth": "🤑", "cash": "💵", "dollars": "💵", "crypto": "🪙", "bitcoin": "🪙",
    "buy": "🛍️", "sell": "📉", "earn": "💸", "invest": "📈", "stock": "📈", "cost": "💳", "price": "💰", "budget": "💰",
    
    # Brain, Thinking & Ideas
    "idea": "🧠", "ideas": "🧠", "think": "🧠", "mind": "🧠", "smart": "🧠", "brain": "🧠", "concept": "💡", "learn": "🎓",
    "study": "📚", "school": "🏫", "class": "🏫", "question": "❓", "secret": "🤫", "focus": "🎯", "know": "🤓",
    
    # Speed, Energy & Action
    "fast": "⚡", "speed": "⚡", "quick": "⚡", "run": "⚡", "energy": "🔥", "fire": "🔥", "hot": "🔥", "power": "🔋",
    "strong": "💪", "action": "🎬", "work": "💼", "build": "🛠️", "create": "🎨", "play": "🎮",
    
    # Success & Achievement
    "win": "🏆", "winner": "🏆", "success": "📈", "champion": "🏆", "goal": "🥅", "accomplish": "🥇", "first": "1️⃣",
    "best": "👑", "king": "👑", "queen": "👑", "leader": "👑", "top": "🔝",
    
    # Growth & Movement
    "grow": "📈", "growth": "📈", "up": "⬆️", "rocket": "🚀", "fly": "✈️", "travel": "✈️", "car": "🚗",
    
    # Feelings & People
    "happy": "😊", "sad": "😢", "angry": "😡", "love": "❤️", "hate": "💔", "friend": "🤝", "team": "🤝",
    "laugh": "😂", "lol": "😂", "funny": "😂", "scared": "😱", "shocked": "😱", "surprised": "😲",
    
    # Miscellaneous high-retention words
    "world": "🌍", "country": "🗺️", "time": "⏱️", "clock": "⏰", "watch": "⌚", "phone": "📱", "computer": "💻",
    "camera": "📷", "video": "🎥", "music": "🎵", "song": "🎵", "food": "🍔", "drink": "🥤", "coffee": "☕"
}


def get_emoji_for_word(text: str) -> Optional[str]:
    """Look up keyword in emoji dictionary and return emoji or None."""
    cleaned = text.lower().strip(".,!?;:\"'()[]{}*-_")
    if cleaned in EMOJI_KEYWORDS:
        return EMOJI_KEYWORDS[cleaned]
    for key, emoji in EMOJI_KEYWORDS.items():
        if key in cleaned or cleaned in key:
            return emoji
    return None


def create_karaoke_subtitles(
    relevant_words: List[Dict],
    video_width: int,
    video_height: int,
    template: Dict,
    font_family: str,
    layout_timeline: Optional[List] = None,
) -> List[TextClip]:
    """Create karaoke-style subtitles with word-by-word highlighting."""
    from .layout_director import caption_position_y_at_time

    subtitle_clips = []
    processor = VideoProcessor(
        font_family, template["font_size"], template["font_color"]
    )

    calculated_font_size = get_scaled_font_size(template["font_size"], video_width)
    default_position_y = template.get("position_y", 0.75)
    highlight_color = template.get("highlight_color", "#FFD700")
    normal_color = template["font_color"]
    max_text_width = get_subtitle_max_width(video_width)
    horizontal_padding = max(40, int(video_width * 0.06))

    words_per_group = 3
    from .subtitle_compositor import is_premium_template, create_premium_karaoke_clips

    is_opus = is_premium_template(template)

    if is_opus:
        try:
            premium_clips = create_premium_karaoke_clips(
                relevant_words,
                video_width,
                video_height,
                template,
                processor.font_path,
                position_y=template.get("position_y", 0.82),
                layout_timeline=layout_timeline,
            )
            if premium_clips:
                logger.info(f"Created {len(premium_clips)} premium PIL subtitle clips")
                return premium_clips
        except Exception as exc:
            logger.warning(f"Premium subtitle compositor failed, falling back: {exc}")

    def measure_word_group_width(word_group: List[Dict], font_size: int) -> List[int]:
        widths: List[int] = []
        for word in word_group:
            text = word["text"].upper() if is_opus else word["text"]
            temp_clip = TextClip(
                text=text,
                font=processor.font_path,
                font_size=font_size,
                color=normal_color,
                stroke_color=template.get("stroke_color", "black"),
                stroke_width=template.get("stroke_width", 1),
                method="label",
            )
            widths.append(temp_clip.size[0] if temp_clip.size else 50)
            temp_clip.close()
        return widths

    for group_idx in range(0, len(relevant_words), words_per_group):
        word_group = relevant_words[group_idx : group_idx + words_per_group]
        if not word_group:
            continue

        group_start = word_group[0]["start"]
        group_end = word_group[-1]["end"]

        # For each word in the group, create a highlighted version
        for word_idx, current_word in enumerate(word_group):
            word_start = current_word["start"]
            word_end = current_word["end"]
            if word_idx + 1 < len(word_group):
                word_duration = float(word_group[word_idx + 1]["start"]) - word_start
            else:
                word_duration = word_end - word_start
            word_duration = max(0.05, word_duration)

            if word_duration < 0.05:
                continue

            visible_group = word_group[: word_idx + 1]

            try:
                word_clips_for_composite = []
                font_size_for_group = calculated_font_size
                word_widths = measure_word_group_width(visible_group, font_size_for_group)
                space_width = font_size_for_group * 0.28
                total_width = sum(word_widths) + space_width * (len(visible_group) - 1)

                if total_width > max_text_width and total_width > 0:
                    shrink_ratio = max_text_width / total_width
                    font_size_for_group = max(
                        20, int(font_size_for_group * shrink_ratio)
                    )
                    word_widths = measure_word_group_width(
                        visible_group, font_size_for_group
                    )
                    space_width = font_size_for_group * 0.28
                    total_width = sum(word_widths) + space_width * (len(visible_group) - 1)

                # Second pass: create positioned clips
                current_x = max(horizontal_padding, (video_width - total_width) / 2)
                text_height = 40

                # Pre-calculate vertical position based on max word height in group
                max_w_height = 40
                for w in visible_group:
                    t_text = w["text"].upper() if is_opus else w["text"]
                    temp_c = TextClip(
                        text=t_text,
                        font=processor.font_path,
                        font_size=font_size_for_group,
                        method="label"
                    )
                    max_w_height = max(max_w_height, temp_c.size[1] if temp_c.size else 40)
                    temp_c.close()

                position_y = (
                    caption_position_y_at_time(word_start, layout_timeline)
                    if layout_timeline
                    else default_position_y
                )
                vertical_position = get_safe_vertical_position(
                    video_height, max_w_height, position_y
                )

                for w_idx, word in enumerate(visible_group):
                    is_current = w_idx == word_idx
                    
                    # Opus Style Highlights (Yellow active, Green for active key terms with emojis)
                    color = normal_color
                    if is_current:
                        if is_opus and get_emoji_for_word(word["text"]) and template.get("secondary_highlight"):
                            color = template["secondary_highlight"]
                        else:
                            color = highlight_color
                            
                    # Scale multiplier for MrBeast/Standard Pop highlights
                    size_multiplier = 1.1 if (is_current and not is_opus) else 1.0
                    word_text = word["text"].upper() if is_opus else word["text"]

                    # 1. Render Vector Drop Shadow underneath
                    if template.get("shadow"):
                        shadow_offset_x = 4
                        shadow_offset_y = 4
                        if isinstance(template.get("shadow_offset"), tuple):
                            shadow_offset_x, shadow_offset_y = template["shadow_offset"]
                            
                        # If active bouncing pop is active, scale the shadow size too!
                        shadow_size_multiplier = 1.25 if (is_current and is_opus) else size_multiplier
                        
                        shadow_clip = (
                            TextClip(
                                text=word_text,
                                font=processor.font_path,
                                font_size=int(font_size_for_group * shadow_size_multiplier),
                                color="#000000",
                                stroke_color="#000000",
                                stroke_width=template.get("stroke_width", 1) + 1,
                                method="label",
                            )
                            .with_duration(word_duration)
                            .with_start(word_start)
                        )
                        
                        if is_current and is_opus:
                            pop_width = shadow_clip.size[0] if shadow_clip.size else word_widths[w_idx]
                            pop_height = shadow_clip.size[1] if shadow_clip.size else max_w_height
                            dx = (pop_width - word_widths[w_idx]) / 2
                            dy = (pop_height - max_w_height) / 2
                            shadow_x = int(current_x - dx + shadow_offset_x)
                            shadow_y = int(vertical_position - dy + shadow_offset_y)
                        else:
                            shadow_x = int(current_x + shadow_offset_x)
                            shadow_y = int(vertical_position + shadow_offset_y)
                            
                        shadow_clip = shadow_clip.with_position((shadow_x, shadow_y))
                        word_clips_for_composite.append(shadow_clip)

                    # 2. Render Text Clip (Main)
                    if is_current and is_opus:
                        # Bouncing Typography: Pop for first 0.12s (1.25x size), settle to 1.0x
                        pop_duration = min(0.12, word_duration)
                        rest_duration = word_duration - pop_duration

                        # Pop Clip (1.25x)
                        word_clip_pop = (
                            TextClip(
                                text=word_text,
                                font=processor.font_path,
                                font_size=int(font_size_for_group * 1.25),
                                color=color,
                                stroke_color=template.get("stroke_color", "black"),
                                stroke_width=template.get("stroke_width", 2),
                                method="label",
                            )
                            .with_duration(pop_duration)
                            .with_start(word_start)
                        )
                        pop_width = word_clip_pop.size[0] if word_clip_pop.size else word_widths[w_idx]
                        pop_height = word_clip_pop.size[1] if word_clip_pop.size else max_w_height
                        dx = (pop_width - word_widths[w_idx]) / 2
                        dy = (pop_height - max_w_height) / 2

                        word_clip_pop = word_clip_pop.with_position(
                            (int(current_x - dx), int(vertical_position - dy))
                        )
                        word_clips_for_composite.append(word_clip_pop)

                        # Settle Clip (1.0x)
                        if rest_duration > 0.01:
                            word_clip_settle = (
                                TextClip(
                                    text=word_text,
                                    font=processor.font_path,
                                    font_size=font_size_for_group,
                                    color=color,
                                    stroke_color=template.get("stroke_color", "black"),
                                    stroke_width=template.get("stroke_width", 2),
                                    method="label",
                                )
                                .with_duration(rest_duration)
                                .with_start(word_start + pop_duration)
                            )
                            word_clip_settle = word_clip_settle.with_position(
                                (int(current_x), vertical_position)
                            )
                            word_clips_for_composite.append(word_clip_settle)
                    else:
                        # Standard rendering for non-current words or general templates
                        word_clip = (
                            TextClip(
                                text=word_text,
                                font=processor.font_path,
                                font_size=int(font_size_for_group * size_multiplier),
                                color=color,
                                stroke_color=template.get("stroke_color", "black"),
                                stroke_width=template.get("stroke_width", 1),
                                method="label",
                            )
                            .with_duration(word_duration)
                            .with_start(word_start)
                        )
                        word_clip = word_clip.with_position(
                            (int(current_x), vertical_position)
                        )
                        word_clips_for_composite.append(word_clip)

                    # 3. Render AI-Matched Emoji Overlay above active word
                    emoji = get_emoji_for_word(word["text"])
                    if emoji and is_current and is_opus:
                        emoji_font_size = int(font_size_for_group * 1.3)
                        emoji_clip = (
                            TextClip(
                                text=emoji,
                                font=processor.font_path,
                                font_size=emoji_font_size,
                                method="label",
                            )
                            .with_duration(word_duration)
                            .with_start(word_start)
                        )
                        emoji_w = emoji_clip.size[0] if emoji_clip.size else 40
                        emoji_h = emoji_clip.size[1] if emoji_clip.size else 40
                        
                        word_center_x = current_x + word_widths[w_idx] / 2
                        emoji_x = int(word_center_x - emoji_w / 2)
                        emoji_y = int(vertical_position - emoji_h - 15) # 15px gap above
                        
                        emoji_clip = emoji_clip.with_position((emoji_x, emoji_y))
                        word_clips_for_composite.append(emoji_clip)

                    current_x += word_widths[w_idx] + space_width

                subtitle_clips.extend(word_clips_for_composite)

            except Exception as e:
                logger.warning(
                    f"Failed to create karaoke subtitle for word '{current_word['text']}': {e}"
                )
                continue

    logger.info(f"Created {len(subtitle_clips)} premium karaoke subtitle elements")
    return subtitle_clips


def create_pop_subtitles(
    relevant_words: List[Dict],
    video_width: int,
    video_height: int,
    template: Dict,
    font_family: str,
) -> List[TextClip]:
    """Create pop-style subtitles where each word pops in."""
    subtitle_clips = []
    processor = VideoProcessor(
        font_family, template["font_size"], template["font_color"]
    )

    calculated_font_size = get_scaled_font_size(template["font_size"], video_width)
    position_y = template.get("position_y", 0.75)
    max_text_width = get_subtitle_max_width(video_width)

    words_per_group = 3

    for group_idx in range(0, len(relevant_words), words_per_group):
        word_group = relevant_words[group_idx : group_idx + words_per_group]
        if not word_group:
            continue

        # Show the full group text
        group_text = " ".join(w["text"] for w in word_group)
        group_start = word_group[0]["start"]
        group_end = word_group[-1]["end"]
        group_duration = group_end - group_start

        if group_duration < 0.1:
            continue

        try:
            # Create main text clip
            text_clip = (
                TextClip(
                    text=group_text,
                    font=processor.font_path,
                    font_size=calculated_font_size,
                    color=template["font_color"],
                    stroke_color=template.get("stroke_color", "black"),
                    stroke_width=template.get("stroke_width", 2),
                    method="caption",
                    size=(max_text_width, None),
                    text_align="center",
                    interline=6,
                )
                .with_duration(group_duration)
                .with_start(group_start)
            )

            text_height = text_clip.size[1] if text_clip.size else 40
            vertical_position = get_safe_vertical_position(
                video_height, text_height, position_y
            )
            text_clip = text_clip.with_position(("center", vertical_position))

            subtitle_clips.append(text_clip)

        except Exception as e:
            logger.warning(f"Failed to create pop subtitle: {e}")
            continue

    logger.info(f"Created {len(subtitle_clips)} pop subtitle elements")
    return subtitle_clips


def create_fade_subtitles(
    relevant_words: List[Dict],
    video_width: int,
    video_height: int,
    template: Dict,
    font_family: str,
) -> List[TextClip]:
    """Create fade-style subtitles with smooth transitions."""
    subtitle_clips = []
    processor = VideoProcessor(
        font_family, template["font_size"], template["font_color"]
    )

    calculated_font_size = get_scaled_font_size(template["font_size"], video_width)
    position_y = template.get("position_y", 0.75)
    has_background = template.get("background", False)
    background_color = template.get("background_color", "#00000080")
    max_text_width = get_subtitle_max_width(video_width)

    words_per_group = 4

    for group_idx in range(0, len(relevant_words), words_per_group):
        word_group = relevant_words[group_idx : group_idx + words_per_group]
        if not word_group:
            continue

        group_text = " ".join(w["text"] for w in word_group)
        group_start = word_group[0]["start"]
        group_end = word_group[-1]["end"]
        group_duration = group_end - group_start

        if group_duration < 0.1:
            continue

        try:
            # Create text clip
            text_clip = TextClip(
                text=group_text,
                font=processor.font_path,
                font_size=calculated_font_size,
                color=template["font_color"],
                stroke_color=template.get("stroke_color")
                if template.get("stroke_color")
                else None,
                stroke_width=template.get("stroke_width", 0),
                method="caption",
                size=(max_text_width, None),
                text_align="center",
                interline=6,
            )

            text_height = text_clip.size[1] if text_clip.size else 40
            text_width = text_clip.size[0] if text_clip.size else 200
            vertical_position = get_safe_vertical_position(
                video_height, text_height, position_y
            )

            # Add background if specified
            if has_background and background_color:
                padding = 10
                # Parse background color (handle alpha)
                bg_color_hex = (
                    background_color[:7]
                    if len(background_color) > 7
                    else background_color
                )

                bg_clip = (
                    ColorClip(
                        size=(text_width + padding * 2, text_height + padding),
                        color=tuple(
                            int(bg_color_hex[i : i + 2], 16) for i in (1, 3, 5)
                        ),
                    )
                    .with_duration(group_duration)
                    .with_start(group_start)
                )

                bg_clip = bg_clip.with_position(
                    ("center", vertical_position - padding // 2)
                )

                # Apply fade to background
                fade_duration = min(0.2, group_duration / 4)
                bg_clip = (
                    bg_clip.with_effects(
                        [CrossFadeIn(fade_duration), CrossFadeOut(fade_duration)]
                    )
                    if group_duration > 0.5
                    else bg_clip
                )

                subtitle_clips.append(bg_clip)

            # Apply timing and position to text
            text_clip = text_clip.with_duration(group_duration).with_start(group_start)
            text_clip = text_clip.with_position(("center", vertical_position))

            subtitle_clips.append(text_clip)

        except Exception as e:
            logger.warning(f"Failed to create fade subtitle: {e}")
            continue

    logger.info(f"Created {len(subtitle_clips)} fade subtitle elements")
    return subtitle_clips


def create_optimized_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    add_subtitles: bool = True,
    font_family: str = "THEBOLDFONT",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "default",
    output_format: str = "vertical",
    highlight_color: Optional[str] = None,
    background_color: Optional[str] = None,
) -> bool:
    """Create clip with optional subtitles. output_format: 'vertical' (9:16) or 'original' (keep source size)."""
    try:
        duration = end_time - start_time
        if duration <= 0:
            logger.error(f"Invalid clip duration: {duration:.1f}s")
            return False

        keep_original = output_format == "original"
        logger.info(
            f"Creating clip: {start_time:.1f}s - {end_time:.1f}s ({duration:.1f}s) "
            f"subtitles={add_subtitles} template '{caption_template}' format={'original' if keep_original else 'vertical'}"
        )

        # Fast path: no subtitles + original = ffmpeg stream copy (no re-encoding)
        if not add_subtitles and keep_original:
            import subprocess
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss", str(start_time),
                    "-i", str(video_path),
                    "-t", str(duration),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error(f"ffmpeg stream copy failed: {result.stderr}")
                return False
            logger.info(f"Successfully created clip (stream copy): {output_path}")
            return True

        # Load and process video
        video = VideoFileClip(str(video_path))

        if start_time >= video.duration:
            logger.error(
                f"Start time {start_time}s exceeds video duration {video.duration:.1f}s"
            )
            video.close()
            return False

        end_time = min(end_time, video.duration)
        clip = video.subclipped(start_time, end_time)
        relative_layout_timeline = None

        if keep_original:
            # No face detection, no crop, no resize - use trimmed clip as-is
            processed_clip = clip
            target_width = round_to_even(processed_clip.w)
            target_height = round_to_even(processed_clip.h)
            if (target_width, target_height) != (processed_clip.w, processed_clip.h):
                processed_clip = processed_clip.resized((target_width, target_height))
            cropped_clip = None
        else:
            # Vertical 9:16: dynamic speaker cuts, or face-centred crop fallback
            src_w, src_h = video.size
            # Determine target 9:16 dimensions from the source video
            if src_w / src_h > 9 / 16:
                _crop_h = round_to_even(src_h)
                _crop_w = round_to_even(int(src_h * (9 / 16)))
            else:
                _crop_w = round_to_even(src_w)
                _crop_h = round_to_even(int(src_w / (9 / 16)))
            target_width, target_height = _crop_w, _crop_h
            output_target_w, output_target_h = 1080, 1920

            transcript_data = load_cached_transcript_data(video_path)
            has_speakers = bool(
                transcript_data
                and transcript_data.get("utterances")
            )

            layout_ctx = None
            if has_speakers:
                layout_ctx = prepare_directed_layout(
                    video,
                    transcript_data,
                    start_time,
                    end_time,
                    video_path=video_path,
                )
                from .layout_director import timeline_to_clip_relative

                relative_layout_timeline = timeline_to_clip_relative(
                    layout_ctx.timeline, layout_ctx.clip_start_ms
                )

            if has_speakers:
                processed_clip = create_directed_clip(
                    video,
                    clip,
                    transcript_data,
                    start_time,
                    end_time,
                    target_width,
                    target_height,
                    video_path=video_path,
                    layout_ctx=layout_ctx,
                )
            else:
                # Single-speaker or no diarisation: static face-centred crop
                x_offset, y_offset, new_width, new_height = detect_optimal_crop_region(
                    video, start_time, end_time, target_ratio=9 / 16
                )
                processed_clip = clip.cropped(
                    x1=x_offset, y1=y_offset,
                    x2=x_offset + new_width, y2=y_offset + new_height,
                )
                if (processed_clip.size[0], processed_clip.size[1]) != (target_width, target_height):
                    processed_clip = processed_clip.resized((target_width, target_height))

            if (processed_clip.size[0], processed_clip.size[1]) != (output_target_w, output_target_h):
                processed_clip = processed_clip.resized((output_target_w, output_target_h))
                target_width, target_height = output_target_w, output_target_h

            cropped_clip = processed_clip
        final_clips = [processed_clip]
        template = get_template(caption_template)
        from .subtitle_compositor import is_premium_template

        use_pil_premium = add_subtitles and (
            template.get("pill_style") or is_premium_template(template)
        )
        use_ass_karaoke = (
            add_subtitles
            and template.get("animation") == "karaoke"
            and not use_pil_premium
        )
        ass_available = False
        if use_ass_karaoke:
            from .ass_captions import ass_burn_available

            ass_available = ass_burn_available()
            if not ass_available:
                logger.warning("ASS/libass unavailable — falling back to MoviePy karaoke")

        if add_subtitles and (use_pil_premium or not (use_ass_karaoke and ass_available)):
            subtitle_clips = create_assemblyai_subtitles(
                video_path,
                start_time,
                end_time,
                target_width,
                target_height,
                font_family,
                font_size,
                font_color,
                caption_template,
                highlight_color=highlight_color,
                background_color=background_color,
                layout_timeline=relative_layout_timeline,
            )
            final_clips.extend(subtitle_clips)

        # Compose and encode
        final_clip = (
            CompositeVideoClip(final_clips) if len(final_clips) > 1 else processed_clip
        )
        source_fps = clip.fps if clip.fps and clip.fps > 0 else 30

        processor = VideoProcessor(font_family, font_size, font_color)
        encoding_settings = processor.get_optimal_encoding_settings("high")

        encode_target = output_path
        temp_nosubs_path: Optional[Path] = None
        if use_ass_karaoke and ass_available:
            temp_nosubs_path = output_path.with_suffix(".nosubs.tmp.mp4")
            encode_target = temp_nosubs_path

        final_clip.write_videofile(
            str(encode_target),
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            logger=None,
            fps=source_fps,
            **encoding_settings,
        )

        if use_ass_karaoke and ass_available and temp_nosubs_path:
            from .ass_captions import burn_ass_subtitles, generate_ass_from_words

            transcript_data = load_cached_transcript_data(video_path)
            relevant_words = (
                get_words_in_range(transcript_data, start_time, end_time)
                if transcript_data
                else []
            )
            effective_template = {
                **template,
                "font_size": int(font_size) if font_size else int(template["font_size"]),
                "font_color": font_color or template["font_color"],
                "font_family": font_family or template["font_family"],
            }
            ass_content = generate_ass_from_words(
                relevant_words,
                effective_template,
                target_width,
                target_height,
                font_family=font_family,
                font_size=font_size,
                font_color=font_color,
            )
            if ass_content and burn_ass_subtitles(
                temp_nosubs_path, ass_content, output_path
            ):
                temp_nosubs_path.unlink(missing_ok=True)
                logger.info("Burned ASS karaoke subtitles onto clip")
            else:
                logger.warning("ASS burn failed — delivering clip without subtitles")
                temp_nosubs_path.replace(output_path)

        # Cleanup
        if final_clip is not processed_clip:
            final_clip.close()
        if processed_clip is not cropped_clip:
            processed_clip.close()
        if cropped_clip is not None:
            cropped_clip.close()
        clip.close()
        video.close()

        logger.info(f"Successfully created clip: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create clip: {e}")
        return False


def create_clips_from_segments(
    video_path: Path,
    segments: List[Dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "default",
    output_format: str = "vertical",
    add_subtitles: bool = True,
) -> List[Dict[str, Any]]:
    """Create optimized video clips from segments with template support."""
    logger.info(
        f"Creating {len(segments)} clips subtitles={add_subtitles} template '{caption_template}'"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_info = []

    for i, segment in enumerate(segments):
        try:
            # Debug log the segment data
            logger.info(
                f"Processing segment {i + 1}: start='{segment.get('start_time')}', end='{segment.get('end_time')}'"
            )

            start_seconds = parse_timestamp_to_seconds(segment["start_time"])
            end_seconds = parse_timestamp_to_seconds(segment["end_time"])

            duration = end_seconds - start_seconds
            logger.info(
                f"Segment {i + 1} duration: {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)"
            )

            if duration <= 0:
                logger.warning(
                    f"Skipping clip {i + 1}: invalid duration {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)"
                )
                continue

            clip_filename = f"clip_{i + 1}_{segment['start_time'].replace(':', '')}-{segment['end_time'].replace(':', '')}.mp4"
            clip_path = output_dir / clip_filename

            success = create_optimized_clip(
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
            )

            if success:
                clip_info = {
                    "clip_id": i + 1,
                    "filename": clip_filename,
                    "path": str(clip_path),
                    "start_time": segment["start_time"],
                    "end_time": segment["end_time"],
                    "duration": duration,
                    "text": segment["text"],
                    "relevance_score": segment["relevance_score"],
                    "reasoning": segment["reasoning"],
                    # Include virality data if available
                    "virality_score": segment.get("virality_score", 0),
                    "hook_score": segment.get("hook_score", 0),
                    "engagement_score": segment.get("engagement_score", 0),
                    "value_score": segment.get("value_score", 0),
                    "shareability_score": segment.get("shareability_score", 0),
                    "hook_type": segment.get("hook_type"),
                }
                clips_info.append(clip_info)
                logger.info(f"Created clip {i + 1}: {duration:.1f}s")
            else:
                logger.error(f"Failed to create clip {i + 1}")

        except Exception as e:
            logger.error(f"Error processing clip {i + 1}: {e}")

    logger.info(f"Successfully created {len(clips_info)}/{len(segments)} clips")
    return clips_info


def get_available_transitions() -> List[str]:
    """Get list of available transition video files."""
    transitions_dir = Path(__file__).parent.parent / "transitions"
    if not transitions_dir.exists():
        logger.warning("Transitions directory not found")
        return []

    transition_files = []
    for file_path in transitions_dir.glob("*.mp4"):
        transition_files.append(str(file_path))

    logger.info(f"Found {len(transition_files)} transition files")
    return transition_files


def apply_transition_effect(
    clip1_path: Path, clip2_path: Path, transition_path: Path, output_path: Path
) -> bool:
    """Apply transition effect between two clips using a transition video."""
    clip1 = None
    clip2 = None
    transition = None
    clip1_tail = None
    clip2_intro = None
    clip2_remainder = None
    intro_segment = None
    final_clip = None

    try:
        from moviepy import VideoFileClip, CompositeVideoClip, concatenate_videoclips

        # Load clips
        clip1 = VideoFileClip(str(clip1_path))
        clip2 = VideoFileClip(str(clip2_path))
        transition = VideoFileClip(str(transition_path))

        # Keep the transition window within both clips so the output still matches
        # the current clip's duration and metadata.
        transition_duration = min(1.5, transition.duration, clip1.duration, clip2.duration)
        if transition_duration <= 0:
            logger.warning("Transition duration is zero, skipping transition effect")
            return False

        transition = transition.subclipped(0, transition_duration)

        # Resize transition to match clip dimensions
        clip_size = clip2.size
        transition = transition.resized(clip_size)

        # Build a transition intro from the previous clip tail over the first
        # part of the current clip so the exported file keeps clip2's duration.
        clip1_tail_start = max(0, clip1.duration - transition_duration)
        clip1_tail = clip1.subclipped(clip1_tail_start, clip1.duration).with_effects(
            [FadeOut(transition_duration)]
        )
        clip2_intro = clip2.subclipped(0, transition_duration).with_effects(
            [FadeIn(transition_duration)]
        )

        intro_segment = CompositeVideoClip(
            [clip1_tail, clip2_intro, transition], size=clip_size
        ).with_duration(transition_duration)
        if clip2_intro.audio is not None:
            intro_segment = intro_segment.with_audio(clip2_intro.audio)

        final_segments = [intro_segment]
        if clip2.duration > transition_duration:
            clip2_remainder = clip2.subclipped(transition_duration, clip2.duration)
            final_segments.append(clip2_remainder)

        final_clip = (
            concatenate_videoclips(final_segments, method="compose")
            if len(final_segments) > 1
            else intro_segment
        )

        # Write output
        processor = VideoProcessor()
        encoding_settings = processor.get_optimal_encoding_settings("high")

        final_clip.write_videofile(
            str(output_path),
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            logger=None,
            **encoding_settings,
        )

        logger.info(f"Applied transition effect: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error applying transition effect: {e}")
        return False
    finally:
        for clip in (
            final_clip,
            intro_segment,
            clip2_remainder,
            clip2_intro,
            clip1_tail,
            transition,
            clip2,
            clip1,
        ):
            if clip is not None:
                try:
                    clip.close()
                except Exception:
                    pass


def create_clips_with_transitions(
    video_path: Path,
    segments: List[Dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    caption_template: str = "default",
    output_format: str = "vertical",
    add_subtitles: bool = True,
) -> List[Dict[str, Any]]:
    """Create standalone video clips without inter-clip transitions.

    Kept as a backward-compatible wrapper for older call sites.
    """
    logger.info(
        f"Creating {len(segments)} standalone clips subtitles={add_subtitles} template '{caption_template}'"
    )
    logger.info(
        "Inter-clip transitions are disabled for standalone SupoClip exports"
    )
    return create_clips_from_segments(
        video_path,
        segments,
        output_dir,
        font_family,
        font_size,
        font_color,
        caption_template,
        output_format,
        add_subtitles,
    )


# Backward compatibility functions
def get_video_transcript_with_assemblyai(path: Path) -> str:
    """Backward compatibility wrapper."""
    return get_video_transcript(path)


def create_9_16_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    subtitle_text: str = "",
) -> bool:
    """Backward compatibility wrapper."""
    return create_optimized_clip(
        video_path, start_time, end_time, output_path, add_subtitles=bool(subtitle_text)
    )
