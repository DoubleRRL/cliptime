"""
Riverside-style layout director: solo speaker crops and dual stacked portrait segments.

Switches between single-speaker 9:16 crops and vertical dual-stack layouts based on
reaction/overlap heuristics (laughter text, overlapping speech, post-punchline windows).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from moviepy import CompositeVideoClip, VideoFileClip

from .speaker_panels import (
    _detect_faces_in_frame,
    _filter_watermark_faces,
    _slot_inner_face_cx,
    face_center_in_slot,
    face_in_panel,
    fit_portrait_crop,
    is_portrait_source,
    is_riverside_dual_feed,
    panel_to_vertical_crop,
    resolve_speaker_panel,
    riverside_dual_half_crop,
    riverside_slot_crop,
    round_to_even,
)

logger = logging.getLogger(__name__)

DUAL_MIN_MS = 1500
DUAL_MAX_MS = 4000
OVERLAP_WINDOW_MS = 400
DUAL_PAD_MS = 300
PORTRAIT_SAMPLE_INTERVAL_S = 0.5
VISUAL_DUAL_SAMPLE_INTERVAL_S = 0.35
VISUAL_DUAL_MIN_CONSECUTIVE = 3

REACTION_RE = re.compile(
    r"\b(laugh(?:s|ing|ed|ter)?|haha+|lol|\[laughter\])\b",
    re.IGNORECASE,
)


@dataclass
class LayoutSegment:
    start_ms: int
    end_ms: int
    mode: str  # "solo" | "dual" | "pass_through"
    speaker: Optional[str] = None


def caption_position_y_at_time(
    t_s: float,
    timeline: List[LayoutSegment],
    *,
    solo_y: float = 0.77,
    dual_y: float = 0.50,
) -> float:
    """Return subtitle Y fraction for clip-relative time ``t_s`` (seconds)."""
    t_ms = int(t_s * 1000)
    for seg in timeline:
        if seg.start_ms <= t_ms < seg.end_ms:
            return dual_y if seg.mode == "dual" else solo_y
    return solo_y


def timeline_to_clip_relative(
    timeline: List[LayoutSegment],
    clip_start_ms: int,
) -> List[LayoutSegment]:
    """Convert absolute-ms timeline segments to clip-relative ms."""
    return [
        LayoutSegment(
            max(0, seg.start_ms - clip_start_ms),
            max(0, seg.end_ms - clip_start_ms),
            seg.mode,
            seg.speaker,
        )
        for seg in timeline
    ]


def _scale_timeline_to_duration(
    timeline: List[LayoutSegment],
    target_duration_ms: int,
) -> List[LayoutSegment]:
    """Scale clip-relative layout segments to match encoded span duration."""
    if target_duration_ms <= 0 or not timeline:
        return []
    source_end = max(seg.end_ms for seg in timeline)
    if source_end <= 0 or source_end == target_duration_ms:
        return [
            LayoutSegment(
                max(0, min(seg.start_ms, target_duration_ms)),
                max(0, min(seg.end_ms, target_duration_ms)),
                seg.mode,
                seg.speaker,
            )
            for seg in timeline
            if seg.end_ms > seg.start_ms
        ]
    ratio = target_duration_ms / source_end
    scaled: List[LayoutSegment] = []
    for seg in timeline:
        seg_start = int(seg.start_ms * ratio)
        seg_end = int(seg.end_ms * ratio)
        seg_start = max(0, min(seg_start, target_duration_ms))
        seg_end = max(seg_start, min(seg_end, target_duration_ms))
        if seg_end <= seg_start:
            continue
        scaled.append(
            LayoutSegment(seg_start, seg_end, seg.mode, seg.speaker)
        )
    return scaled


def remap_layout_timeline_to_output(
    span_durations_ms: Sequence[int],
    span_timelines: Sequence[List[LayoutSegment]],
) -> List[LayoutSegment]:
    """Merge per-span clip-relative timelines onto tight-cut output time (ms from 0).

    ``span_durations_ms`` must be encoded output duration per span (not source keep-span ms).
    """
    output: List[LayoutSegment] = []
    offset_ms = 0
    for span_index, (span_duration, timeline) in enumerate(
        zip(span_durations_ms, span_timelines)
    ):
        if span_duration <= 0:
            continue
        if span_duration < DUAL_MIN_MS:
            speaker = None
            for seg in timeline:
                if seg.speaker:
                    speaker = seg.speaker
                    break
            output.append(
                LayoutSegment(offset_ms, offset_ms + span_duration, "solo", speaker)
            )
            offset_ms += span_duration
            continue

        span_timeline = _scale_timeline_to_duration(list(timeline), span_duration)
        span_timeline = fill_layout_timeline_gaps(
            span_timeline,
            span_duration,
            default_mode="solo",
        )
        if not span_timeline:
            span_timeline = [
                LayoutSegment(0, span_duration, "solo"),
            ]

        if span_index > 0 and output and span_timeline:
            first = span_timeline[0]
            if first.mode == "dual" and output[-1].mode == "dual":
                span_timeline = [
                    LayoutSegment(0, min(1, span_duration), "solo", first.speaker),
                    *(
                        [
                            LayoutSegment(
                                max(1, first.start_ms),
                                first.end_ms,
                                first.mode,
                                first.speaker,
                            )
                        ]
                        if first.end_ms > 1
                        else []
                    ),
                    *span_timeline[1:],
                ]
                span_timeline = fill_layout_timeline_gaps(
                    span_timeline,
                    span_duration,
                    default_mode="solo",
                )

        for seg in span_timeline:
            seg_start = max(0, min(seg.start_ms, span_duration))
            seg_end = max(seg_start, min(seg.end_ms, span_duration))
            if seg_end <= seg_start:
                continue
            output.append(
                LayoutSegment(
                    offset_ms + seg_start,
                    offset_ms + seg_end,
                    seg.mode,
                    seg.speaker,
                )
            )
        offset_ms += span_duration
    return output


def fill_layout_timeline_gaps(
    timeline: List[LayoutSegment],
    total_duration_ms: int,
    *,
    default_mode: str = "solo",
) -> List[LayoutSegment]:
    """Ensure timeline covers ``[0, total_duration_ms)`` with no uncovered ranges."""
    if total_duration_ms <= 0:
        return []
    if not timeline:
        return [LayoutSegment(0, total_duration_ms, default_mode)]

    sorted_segs = sorted(timeline, key=lambda seg: seg.start_ms)
    filled: List[LayoutSegment] = []
    cursor = 0
    last_mode = default_mode
    last_speaker: Optional[str] = None

    for seg in sorted_segs:
        seg_start = max(0, min(seg.start_ms, total_duration_ms))
        seg_end = max(seg_start, min(seg.end_ms, total_duration_ms))
        if seg_end <= seg_start:
            continue
        if seg_start > cursor:
            filled.append(
                LayoutSegment(cursor, seg_start, last_mode, last_speaker)
            )
        filled.append(
            LayoutSegment(seg_start, seg_end, seg.mode, seg.speaker)
        )
        cursor = seg_end
        last_mode = seg.mode
        last_speaker = seg.speaker

    if cursor < total_duration_ms:
        filled.append(
            LayoutSegment(cursor, total_duration_ms, last_mode, last_speaker)
        )

    if not filled:
        return [LayoutSegment(0, total_duration_ms, default_mode)]

    merged: List[LayoutSegment] = [filled[0]]
    for seg in filled[1:]:
        prev = merged[-1]
        if seg.mode == prev.mode and seg.speaker == prev.speaker:
            prev.end_ms = seg.end_ms
        else:
            merged.append(seg)
    return merged


def _clamp_ms(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def _merge_windows(
    windows: List[Tuple[int, int]],
    clip_start_ms: int,
    clip_end_ms: int,
) -> List[Tuple[int, int]]:
    """Merge overlapping dual windows and enforce minimum duration."""
    if not windows:
        return []

    clamped = [
        (
            _clamp_ms(start - DUAL_PAD_MS, clip_start_ms, clip_end_ms),
            _clamp_ms(end + DUAL_PAD_MS, clip_start_ms, clip_end_ms),
        )
        for start, end in windows
        if end > start
    ]
    clamped.sort(key=lambda w: w[0])

    merged: List[Tuple[int, int]] = []
    for start, end in clamped:
        if not merged or start > merged[-1][1] + 200:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    result: List[Tuple[int, int]] = []
    for start, end in merged:
        if end - start < DUAL_MIN_MS:
            center = (start + end) // 2
            half = DUAL_MIN_MS // 2
            start = _clamp_ms(center - half, clip_start_ms, clip_end_ms)
            end = _clamp_ms(center + half, clip_start_ms, clip_end_ms)
        if end > start:
            result.append((start, end))
    return result


def _in_dual_window(t_ms: int, dual_windows: List[Tuple[int, int]]) -> bool:
    return any(start <= t_ms < end for start, end in dual_windows)


def _speaker_at(t_ms: int, turns: List[Dict[str, Any]]) -> Optional[str]:
    for turn in turns:
        if turn["start_ms"] <= t_ms < turn["end_ms"]:
            return turn.get("speaker")
    return turns[-1].get("speaker") if turns else None


def detect_dual_moments(
    transcript_data: Dict[str, Any],
    clip_start_ms: int,
    clip_end_ms: int,
) -> List[Tuple[int, int]]:
    """Return merged dual-layout windows within the clip range."""
    words = [
        w
        for w in (transcript_data.get("words") or [])
        if w.get("start", 0) < clip_end_ms and w.get("end", 0) > clip_start_ms
    ]
    utterances = [
        u
        for u in (transcript_data.get("utterances") or [])
        if u.get("start", 0) < clip_end_ms and u.get("end", 0) > clip_start_ms
    ]

    speakers = {str(w.get("speaker")) for w in words if w.get("speaker")}

    windows: List[Tuple[int, int]] = []

    if len(speakers) >= 2:
        # Overlapping speech: two speakers active within OVERLAP_WINDOW_MS
        for i, w1 in enumerate(words):
            spk1 = w1.get("speaker")
            if not spk1:
                continue
            for w2 in words[i + 1 :]:
                spk2 = w2.get("speaker")
                if not spk2 or spk1 == spk2:
                    continue
                if w2["start"] - w1["start"] > OVERLAP_WINDOW_MS:
                    break
                overlap_start = max(w1["start"], w2["start"])
                overlap_end = min(w1["end"], w2["end"])
                if overlap_end > overlap_start or abs(w2["start"] - w1["start"]) <= OVERLAP_WINDOW_MS:
                    windows.append(
                        (
                            min(w1["start"], w2["start"]),
                            max(w1["end"], w2["end"]),
                        )
                    )

    # Laughter / reaction keywords in utterances
    for utt in utterances:
        if REACTION_RE.search(utt.get("text") or ""):
            windows.append((utt["start"], utt["end"]))

    merged = _merge_windows(windows, clip_start_ms, clip_end_ms)
    return [(s, min(e, s + DUAL_MAX_MS)) for s, e in merged]


def detect_visual_dual_moments(
    full_video: VideoFileClip,
    clip_start_ms: int,
    clip_end_ms: int,
    panels: Dict[str, Dict[str, int]],
) -> List[Tuple[int, int]]:
    """
    Sample the clip for frames where both speaker columns contain a visible face.

    Works even when transcript diarization only tags one speaker (e.g. monologue
    + shared laugh).
    """
    if len(panels) < 2 or clip_end_ms <= clip_start_ms:
        return []

    clip_start_s = clip_start_ms / 1000.0
    clip_end_s = clip_end_ms / 1000.0
    ordered = ordered_speakers_from_panels(panels)[:2]

    raw_windows: List[Tuple[int, int]] = []
    run_start_ms: Optional[int] = None
    consecutive = 0
    t = clip_start_s

    while t < clip_end_s:
        t_ms = int(t * 1000)
        if validate_dual_frame(full_video, t, panels):
            if run_start_ms is None:
                run_start_ms = t_ms
            consecutive += 1
        else:
            if consecutive >= VISUAL_DUAL_MIN_CONSECUTIVE and run_start_ms is not None:
                raw_windows.append((run_start_ms, t_ms))
            run_start_ms = None
            consecutive = 0
        t += VISUAL_DUAL_SAMPLE_INTERVAL_S

    if consecutive >= VISUAL_DUAL_MIN_CONSECUTIVE and run_start_ms is not None:
        raw_windows.append((run_start_ms, clip_end_ms))

    merged = _merge_windows(raw_windows, clip_start_ms, clip_end_ms)
    logger.info(
        "Visual dual windows: %s (speakers %s)",
        len(merged),
        ordered,
    )
    return [(s, min(e, s + DUAL_MAX_MS)) for s, e in merged]


def classify_portrait_frame(frame: np.ndarray) -> str:
    """
    Classify a portrait frame layout.

    Returns ``dual`` when faces occupy distinct top/bottom halves, else ``solo``.
    """
    fh, fw = frame.shape[:2]
    faces = _detect_faces_in_frame(frame)
    if len(faces) < 2:
        return "solo"

    centers = [(fx + w / 2, fy + h / 2) for fx, fy, w, h in faces]
    top_faces = [c for c in centers if c[1] < fh * 0.45]
    bottom_faces = [c for c in centers if c[1] > fh * 0.55]
    if top_faces and bottom_faces:
        return "dual"
    return "solo"


def build_portrait_layout_timeline(
    full_video: VideoFileClip,
    clip_start_s: float,
    clip_end_s: float,
) -> List[LayoutSegment]:
    """Sample portrait source frames and build pass-through layout segments."""
    clip_start_ms = int(clip_start_s * 1000)
    clip_end_ms = int(clip_end_s * 1000)
    segments: List[LayoutSegment] = []

    t = clip_start_s
    current_mode: Optional[str] = None
    seg_start_s = clip_start_s

    while t < clip_end_s:
        try:
            frame = full_video.get_frame(t)
            mode = classify_portrait_frame(frame)
        except Exception as exc:
            logger.debug("Portrait frame sample failed at %.2fs: %s", t, exc)
            mode = current_mode or "solo"

        if current_mode is not None and mode != current_mode:
            segments.append(
                LayoutSegment(
                    start_ms=int(seg_start_s * 1000),
                    end_ms=int(t * 1000),
                    mode="pass_through",
                    speaker=None,
                )
            )
            seg_start_s = t
        current_mode = mode
        t += PORTRAIT_SAMPLE_INTERVAL_S

    if current_mode is not None and seg_start_s < clip_end_s:
        segments.append(
            LayoutSegment(
                start_ms=int(seg_start_s * 1000),
                end_ms=clip_end_ms,
                mode="pass_through",
                speaker=None,
            )
        )

    if not segments:
        segments.append(
            LayoutSegment(
                start_ms=clip_start_ms,
                end_ms=clip_end_ms,
                mode="pass_through",
            )
        )
    return segments


def validate_dual_frame(
    full_video: VideoFileClip,
    t_s: float,
    panels: Dict[str, Dict[str, int]],
) -> bool:
    """True when both speaker columns contain a visible face at ``t_s``."""
    ordered = ordered_speakers_from_panels(panels)
    if len(ordered) < 2:
        return False
    try:
        frame = full_video.get_frame(t_s)
        fh, _ = frame.shape[:2]
        faces = _filter_watermark_faces(_detect_faces_in_frame(frame), fh)
    except Exception:
        return False
    return all(face_in_panel(faces, panels[spk], frame_h=fh) for spk in ordered[:2])


def build_layout_timeline(
    transcript_data: Dict[str, Any],
    clip_start_ms: int,
    clip_end_ms: int,
    *,
    src_w: int,
    src_h: int,
    full_video: Optional[VideoFileClip] = None,
    panels: Optional[Dict[str, Dict[str, int]]] = None,
) -> List[LayoutSegment]:
    """Build solo/dual layout timeline for landscape sources."""
    from .video_utils import build_speaker_turns

    turns = build_speaker_turns(transcript_data, clip_start_ms, clip_end_ms)
    if not turns:
        turns = [
            {
                "speaker": None,
                "start_ms": clip_start_ms,
                "end_ms": clip_end_ms,
            }
        ]

    dual_windows = detect_dual_moments(transcript_data, clip_start_ms, clip_end_ms)
    if full_video is not None and panels:
        visual_windows = detect_visual_dual_moments(
            full_video, clip_start_ms, clip_end_ms, panels
        )
        dual_windows = _merge_windows(
            dual_windows + visual_windows, clip_start_ms, clip_end_ms
        )
        dual_windows = [(s, min(e, s + DUAL_MAX_MS)) for s, e in dual_windows]

    breakpoints = {clip_start_ms, clip_end_ms}
    for turn in turns:
        breakpoints.add(turn["start_ms"])
        breakpoints.add(turn["end_ms"])
    for start, end in dual_windows:
        breakpoints.add(_clamp_ms(start, clip_start_ms, clip_end_ms))
        breakpoints.add(_clamp_ms(end, clip_start_ms, clip_end_ms))

    ordered = sorted(breakpoints)
    raw: List[LayoutSegment] = []
    for i in range(len(ordered) - 1):
        start_ms, end_ms = ordered[i], ordered[i + 1]
        if end_ms <= start_ms:
            continue
        mid = (start_ms + end_ms) // 2
        turn = _speaker_at(mid, turns)
        use_dual = _in_dual_window(mid, dual_windows)
        if use_dual and full_video is not None and panels:
            if not validate_dual_frame(full_video, mid / 1000.0, panels):
                use_dual = False
        if use_dual:
            raw.append(LayoutSegment(start_ms, end_ms, "dual"))
        else:
            raw.append(
                LayoutSegment(
                    start_ms,
                    end_ms,
                    "solo",
                    speaker=turn,
                )
            )

    if not raw:
        return [
            LayoutSegment(clip_start_ms, clip_end_ms, "solo", turns[0].get("speaker"))
        ]

    merged: List[LayoutSegment] = [raw[0]]
    for seg in raw[1:]:
        prev = merged[-1]
        if seg.mode == prev.mode and seg.speaker == prev.speaker:
            prev.end_ms = seg.end_ms
        else:
            merged.append(seg)

    logger.info(
        "Layout timeline: %s segments (%s dual, %s solo)",
        len(merged),
        sum(1 for s in merged if s.mode == "dual"),
        sum(1 for s in merged if s.mode == "solo"),
    )
    return merged


def ordered_speakers_from_panels(panels: Dict[str, Dict[str, int]]) -> List[str]:
    """Return speaker ids left-to-right by panel slot position."""
    return sorted(panels.keys(), key=lambda spk: panels[spk].get("x", 0))


def render_pass_through_segment(
    full_video: VideoFileClip,
    t_start: float,
    t_end: float,
    target_w: int,
    target_h: int,
) -> Optional[VideoFileClip]:
    """Full-frame segment for portrait Riverside exports (no sub-crop)."""
    if t_end - t_start <= 0:
        return None
    seg = full_video.subclipped(t_start, t_end)
    if (seg.size[0], seg.size[1]) != (target_w, target_h):
        seg = seg.resized((target_w, target_h))
    return seg


def _riverside_crop_for_panel(
    full_video: VideoFileClip,
    panel: Dict[str, int],
    t_start: float,
    t_end: float,
    src_w: int,
    src_h: int,
) -> Tuple[int, int, int, int]:
    """Resolve a Riverside column crop, preferring per-segment face detection."""
    mid_t = (t_start + t_end) / 2.0
    center = face_center_in_slot(full_video, mid_t, panel)
    if center:
        return riverside_slot_crop(
            panel, src_w, src_h, face_cx=center[0], face_cy=center[1]
        )

    if panel.get("face_cx") is not None:
        return riverside_slot_crop(
            panel,
            src_w,
            src_h,
            face_cx=panel.get("face_cx"),
            face_cy=panel.get("face_cy"),
        )

    inner_panel = dict(panel)
    inner_panel["face_cx"] = _slot_inner_face_cx(panel)
    return riverside_slot_crop(inner_panel, src_w, src_h)


def _riverside_crop_for_dual_half(
    full_video: VideoFileClip,
    panel: Dict[str, int],
    t_start: float,
    t_end: float,
    src_w: int,
    src_h: int,
    out_w: int,
    half_h: int,
) -> Tuple[int, int, int, int]:
    """Cover-fit crop for one stacked dual half with per-segment face detection."""
    mid_t = (t_start + t_end) / 2.0
    center = face_center_in_slot(full_video, mid_t, panel)
    face_cx = center[0] if center else panel.get("face_cx")
    face_cy = center[1] if center else panel.get("face_cy")
    return riverside_dual_half_crop(
        panel,
        src_w,
        src_h,
        out_w,
        half_h,
        face_cx=face_cx,
        face_cy=face_cy,
    )


def render_riverside_solo_segment(
    full_video: VideoFileClip,
    t_start: float,
    t_end: float,
    speaker: Optional[str],
    panels: Dict[str, Dict[str, int]],
    src_w: int,
    src_h: int,
    target_w: int,
    target_h: int,
    seating_map: Optional[Dict[str, int]] = None,
) -> Optional[VideoFileClip]:
    """Scale a Riverside camera column to 9:16 without double-cropping."""
    if t_end - t_start <= 0:
        return None

    panel = resolve_speaker_panel(
        speaker, panels, seating_map=seating_map, src_w=src_w, src_h=src_h
    )
    if panel is None:
        return None

    x1, y1, x2, y2 = _riverside_crop_for_panel(
        full_video, panel, t_start, t_end, src_w, src_h
    )
    seg = full_video.subclipped(t_start, t_end).cropped(x1=x1, y1=y1, x2=x2, y2=y2)
    if (seg.size[0], seg.size[1]) != (target_w, target_h):
        seg = seg.resized((target_w, target_h))
    return seg


def render_riverside_dual_stack_segment(
    full_video: VideoFileClip,
    t_start: float,
    t_end: float,
    panels: Dict[str, Dict[str, int]],
    src_w: int,
    src_h: int,
    out_w: int,
    out_h: int,
    seating_map: Optional[Dict[str, int]] = None,
) -> Optional[VideoFileClip]:
    """Stack two Riverside camera columns vertically (apr23 dual layout)."""
    if t_end - t_start <= 0 or len(panels) < 2:
        return None

    ordered = ordered_speakers_from_panels(panels)
    half_h = round_to_even(out_h // 2)
    segments: List[VideoFileClip] = []

    for spk in ordered[:2]:
        panel = panels[spk]
        x1, y1, x2, y2 = _riverside_crop_for_dual_half(
            full_video, panel, t_start, t_end, src_w, src_h, out_w, half_h
        )
        seg = (
            full_video.subclipped(t_start, t_end)
            .cropped(x1=x1, y1=y1, x2=x2, y2=y2)
            .resized((out_w, half_h))
        )
        segments.append(seg)

    composite = CompositeVideoClip(
        [
            segments[0].with_position((0, 0)),
            segments[1].with_position((0, half_h)),
        ],
        size=(out_w, out_h),
    ).with_duration(segments[0].duration)
    if segments[0].audio is not None:
        composite = composite.with_audio(segments[0].audio)
    return composite


def render_solo_segment(
    full_video: VideoFileClip,
    t_start: float,
    t_end: float,
    speaker: Optional[str],
    panels: Dict[str, Dict[str, int]],
    src_w: int,
    src_h: int,
    target_w: int,
    target_h: int,
    seating_map: Optional[Dict[str, int]] = None,
) -> Optional[VideoFileClip]:
    """Crop active speaker to apr23-style 9:16."""
    if t_end - t_start <= 0:
        return None

    if panels and speaker and speaker in panels:
        x1, y1, x2, y2 = panel_to_vertical_crop(panels[speaker], src_w, src_h)
    elif panels and len(panels) == 1:
        only_panel = next(iter(panels.values()))
        x1, y1, x2, y2 = panel_to_vertical_crop(only_panel, src_w, src_h)
    else:
        face_cx = src_w // 2
        if speaker and seating_map and speaker in seating_map:
            face_cx = seating_map[speaker]
        panel = {
            "x": 0,
            "y": 0,
            "w": src_w,
            "h": src_h,
            "face_cx": face_cx,
            "face_cy": int(src_h * 0.38),
        }
        x1, y1, x2, y2 = fit_portrait_crop(panel, src_w, src_h)

    seg = full_video.subclipped(t_start, t_end).cropped(x1=x1, y1=y1, x2=x2, y2=y2)
    if (seg.size[0], seg.size[1]) != (target_w, target_h):
        seg = seg.resized((target_w, target_h))
    return seg


def render_dual_stack_segment(
    full_video: VideoFileClip,
    t_start: float,
    t_end: float,
    panels: Dict[str, Dict[str, int]],
    src_w: int,
    src_h: int,
    out_w: int,
    out_h: int,
) -> Optional[VideoFileClip]:
    """Stack two speaker crops vertically (Riverside dual layout)."""
    if t_end - t_start <= 0 or len(panels) < 2:
        return None

    ordered = ordered_speakers_from_panels(panels)
    panel_top = panels[ordered[0]]
    panel_bottom = panels[ordered[1]]
    half_h = round_to_even(out_h // 2)

    x1a, y1a, x2a, y2a = panel_to_vertical_crop(panel_top, src_w, src_h)
    x1b, y1b, x2b, y2b = panel_to_vertical_crop(panel_bottom, src_w, src_h)

    seg_a = (
        full_video.subclipped(t_start, t_end)
        .cropped(x1=x1a, y1=y1a, x2=x2a, y2=y2a)
        .resized((out_w, half_h))
    )
    seg_b = (
        full_video.subclipped(t_start, t_end)
        .cropped(x1=x1b, y1=y1b, x2=x2b, y2=y2b)
        .resized((out_w, half_h))
    )

    composite = CompositeVideoClip(
        [seg_a.with_position((0, 0)), seg_b.with_position((0, half_h))],
        size=(out_w, out_h),
    ).with_duration(seg_a.duration)
    if seg_a.audio is not None:
        composite = composite.with_audio(seg_a.audio)
    return composite


def dual_stack_half_height(out_h: int) -> int:
    """Return even half-height for dual stack layout tests."""
    return round_to_even(out_h // 2)
