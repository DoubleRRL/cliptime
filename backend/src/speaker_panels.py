"""
Per-speaker panel calibration for widescreen multi-host layouts.

Detects (or loads cached) fixed bounding boxes for each diarized speaker, then
crops that panel to 9:16 when that speaker is active — OpusClip-style.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

PANEL_CACHE_VERSION = 4

# Ignore detections in top band (Riverside "Created on Riverside" watermark).
WATERMARK_ZONE_FRAC = 0.10
# Riverside columns frame speakers toward the inner column edge.
SLOT_INNER_EDGE_FRAC = 0.65


def _detect_faces_in_frame(frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Return list of (x, y, w, h) face boxes in frame coordinates."""
    boxes: List[Tuple[int, int, int, int]] = []
    fh, fw = frame.shape[:2]

    try:
        import mediapipe as mp  # type: ignore

        mp_fd = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.35
        )
        results = mp_fd.process(frame)
        mp_fd.close()
        if results.detections:
            for det in results.detections:
                bbox = det.location_data.relative_bounding_box
                x = max(0, int(bbox.xmin * fw))
                y = max(0, int(bbox.ymin * fh))
                w = max(1, int(bbox.width * fw))
                h = max(1, int(bbox.height * fh))
                boxes.append((x, y, w, h))
            return boxes
    except Exception:
        pass

    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30)
    )
    for (fx, fy, fww, fhh) in faces:
        boxes.append((int(fx), int(fy), int(fww), int(fhh)))
    return boxes


def _expand_bbox(
    x: int, y: int, w: int, h: int, fw: int, fh: int, pad_x: float = 1.2, pad_y: float = 0.75
) -> Dict[str, int]:
    """Expand a face box into a speaker panel with padding, clamped to frame."""
    pad_w = int(w * pad_x)
    pad_h = int(h * pad_y)
    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(fw, x + w + pad_w)
    y2 = min(fh, y + h + pad_h)
    return {"x": x1, "y": y1, "w": max(1, x2 - x1), "h": max(1, y2 - y1)}


def _median_panel(boxes: List[Dict[str, int]]) -> Optional[Dict[str, int]]:
    if not boxes:
        return None
    return {
        "x": int(np.median([b["x"] for b in boxes])),
        "y": int(np.median([b["y"] for b in boxes])),
        "w": int(np.median([b["w"] for b in boxes])),
        "h": int(np.median([b["h"] for b in boxes])),
    }


def _panel_label(index: int, total: int) -> str:
    if total <= 1:
        return "Speaker"
    positions = ["left", "center-left", "center-right", "right"]
    pos = positions[min(index, len(positions) - 1)]
    return f"Speaker {index + 1} ({pos})"


def detect_face_panels_from_frame(frame: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect speaker panel regions from a single frame (no diarization).

    Clusters detected faces left-to-right and expands each into a padded panel.
    Falls back to a single full-frame panel when no faces are found.
    """
    fh, fw = frame.shape[:2]
    faces = _detect_faces_in_frame(frame)

    if not faces:
        return [{"id": "1", "label": "Speaker", "x": 0, "y": 0, "w": fw, "h": fh}]

    faces_sorted = sorted(faces, key=lambda b: b[0] + b[2] / 2)
    merge_threshold = max(40, int(fw * 0.15))
    clusters: List[List[Tuple[int, int, int, int]]] = []

    for face in faces_sorted:
        center_x = face[0] + face[2] / 2
        merged = False
        for cluster in clusters:
            cluster_center = sum(f[0] + f[2] / 2 for f in cluster) / len(cluster)
            if abs(center_x - cluster_center) <= merge_threshold:
                cluster.append(face)
                merged = True
                break
        if not merged:
            clusters.append([face])

    clusters.sort(key=lambda c: sum(f[0] + f[2] / 2 for f in c) / len(c))

    panels: List[Dict[str, int]] = []
    for idx, cluster in enumerate(clusters):
        best = max(cluster, key=lambda b: b[2] * b[3])
        panel = _expand_bbox(*best, fw, fh)
        panels.append(
            {
                "id": str(idx + 1),
                "label": _panel_label(idx, len(clusters)),
                **panel,
            }
        )

    return panels


def _merge_panel_detections(all_panels: List[List[Dict[str, Any]]], fw: int, fh: int) -> List[Dict[str, Any]]:
    """Merge panel lists from multiple frames by horizontal position."""
    if not all_panels:
        return [{"id": "1", "label": "Speaker", "x": 0, "y": 0, "w": fw, "h": fh}]

    flat: List[Dict[str, Any]] = []
    for panels in all_panels:
        flat.extend(panels)

    if not flat:
        return [{"id": "1", "label": "Speaker", "x": 0, "y": 0, "w": fw, "h": fh}]

    flat.sort(key=lambda p: p["x"] + p["w"] / 2)
    merge_threshold = max(40, int(fw * 0.15))
    merged: List[Dict[str, Any]] = []

    for panel in flat:
        center = panel["x"] + panel["w"] / 2
        matched = False
        for bucket in merged:
            bucket_center = bucket["x"] + bucket["w"] / 2
            if abs(center - bucket_center) <= merge_threshold:
                bucket["x"] = int((bucket["x"] + panel["x"]) / 2)
                bucket["y"] = int((bucket["y"] + panel["y"]) / 2)
                bucket["w"] = int((bucket["w"] + panel["w"]) / 2)
                bucket["h"] = int((bucket["h"] + panel["h"]) / 2)
                matched = True
                break
        if not matched:
            merged.append(dict(panel))

    merged.sort(key=lambda p: p["x"] + p["w"] / 2)
    for idx, panel in enumerate(merged):
        panel["id"] = str(idx + 1)
        panel["label"] = _panel_label(idx, len(merged))
    return merged


def detect_face_panels_from_video(
    video_path: Path,
    seek_seconds: float = 300.0,
    num_samples: int = 3,
) -> tuple[List[Dict[str, Any]], int, int, np.ndarray]:
    """
    Sample frames around ``seek_seconds`` and detect speaker panels.

    Returns (panels, frame_width, frame_height, primary_frame_rgb).
    """
    import subprocess
    import json
    import tempfile

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise ValueError("Could not probe video dimensions")

    info = json.loads(probe.stdout or "{}")
    streams = info.get("streams") or [{}]
    fw = int(streams[0].get("width") or 0)
    fh = int(streams[0].get("height") or 0)
    duration = float((info.get("format") or {}).get("duration") or 0)
    if fw <= 0 or fh <= 0:
        raise ValueError("Video has no readable dimensions")

    seek = max(1.0, min(float(seek_seconds), max(duration - 1.0, 1.0)))
    offsets = [seek - 2.0, seek, seek + 2.0][:num_samples]
    offsets = [max(0.5, min(o, max(duration - 0.5, 0.5))) for o in offsets]

    panel_sets: List[List[Dict[str, Any]]] = []
    primary_frame: Optional[np.ndarray] = None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for idx, offset in enumerate(offsets):
            frame_path = tmp / f"frame_{idx}.jpg"
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(offset),
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(frame_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 or not frame_path.exists():
                continue
            frame_bgr = cv2.imread(str(frame_path))
            if frame_bgr is None:
                continue
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            if idx == 1 or primary_frame is None:
                primary_frame = frame_rgb
            panel_sets.append(detect_face_panels_from_frame(frame_rgb))

    if primary_frame is None:
        raise ValueError("Could not extract preview frame from video")

    panels = _merge_panel_detections(panel_sets, fw, fh)
    return panels, fw, fh, primary_frame


def _slot_panels(num_speakers: int, fw: int, fh: int) -> List[Dict[str, int]]:
    """Fallback: equal horizontal slots across the frame."""
    if num_speakers <= 0:
        return []
    slot_w = fw // num_speakers
    panels = []
    for i in range(num_speakers):
        panels.append({"x": i * slot_w, "y": 0, "w": slot_w, "h": fh})
    return panels


def _filter_watermark_faces(
    faces: List[Tuple[int, int, int, int]],
    frame_h: int,
) -> List[Tuple[int, int, int, int]]:
    """Drop face boxes whose center sits in the top watermark band."""
    cutoff = frame_h * WATERMARK_ZONE_FRAC
    return [f for f in faces if (f[1] + f[3] / 2) > cutoff]


def _slot_inner_face_cx(panel: Dict[str, int]) -> int:
    """Heuristic face x toward the inner edge of a Riverside column."""
    px, pw = panel["x"], panel["w"]
    return int(px + pw * SLOT_INNER_EDGE_FRAC)


def bind_speakers_to_columns(
    seating_map: Dict[str, int],
    src_w: int,
    src_h: int,
) -> Dict[str, Dict[str, int]]:
    """
    Map diarization labels to left/right Riverside columns by median face x.

    Returns ``{speaker_id: panel_dict}`` with x/w/h and provisional face center.
    """
    if len(seating_map) < 2:
        return {}

    half_w = src_w // 2
    left_slot = {"x": 0, "y": 0, "w": half_w, "h": src_h}
    right_slot = {"x": half_w, "y": 0, "w": half_w, "h": src_h}

    ordered = sorted(seating_map.items(), key=lambda item: item[1])
    slots = [left_slot, right_slot]
    panels: Dict[str, Dict[str, int]] = {}

    for idx, (speaker, face_x) in enumerate(ordered[:2]):
        slot = slots[min(idx, 1)]
        panel = dict(slot)
        panel["face_cx"] = int(face_x)
        panel["face_cy"] = int(src_h * 0.38)
        panels[str(speaker)] = panel

    return panels


def sample_speaker_seating_from_utterances(
    video_clip,
    transcript_data: Dict,
    *,
    max_samples_per_speaker: int = 4,
) -> Dict[str, int]:
    """Return ``{speaker_id: median_face_center_x}`` from utterance midpoints."""
    utterances = transcript_data.get("utterances") or []
    speaker_times: Dict[str, List[float]] = {}
    for utt in utterances:
        speaker = utt.get("speaker")
        if not speaker:
            continue
        bucket = speaker_times.setdefault(str(speaker), [])
        if len(bucket) >= max_samples_per_speaker:
            continue
        start_s = utt.get("start", 0) / 1000.0
        end_s = utt.get("end", 0) / 1000.0
        mid = max(0.0, min((start_s + end_s) / 2.0, video_clip.duration - 0.05))
        bucket.append(mid)

    seating: Dict[str, List[int]] = {}
    for speaker, times in speaker_times.items():
        for t in times:
            try:
                frame = video_clip.get_frame(t)
                fh, _fw = frame.shape[:2]
                faces = _filter_watermark_faces(_detect_faces_in_frame(frame), fh)
                if not faces:
                    continue
                best = max(faces, key=lambda b: b[2] * b[3])
                fx, fy, fw_box, fh_box = best
                seating.setdefault(speaker, []).append(int(fx + fw_box / 2))
            except Exception as exc:
                logger.debug("Seating sample failed for %s at %.2fs: %s", speaker, t, exc)

    return {
        speaker: int(np.median(xs))
        for speaker, xs in seating.items()
        if xs
    }


def _best_face_in_slot(
    faces: List[Tuple[int, int, int, int]],
    slot_x: int,
    slot_w: int,
) -> Optional[Tuple[int, int, int, int]]:
    """Pick largest face whose center falls inside the horizontal slot."""
    slot_x2 = slot_x + slot_w
    in_slot = [
        f
        for f in faces
        if slot_x <= f[0] + f[2] / 2 <= slot_x2
    ]
    candidates = in_slot or faces
    if not candidates:
        return None
    return max(candidates, key=lambda b: b[2] * b[3])


def calibrate_speaker_panels(
    video_clip,
    transcript_data: Dict,
    *,
    max_samples_per_speaker: int = 4,
) -> Dict[str, Dict[str, int]]:
    """
    Build ``{speaker_id: panel}`` using spatial left/right column assignment.

    Speakers are mapped to Riverside columns by median face x, not label order.
    """
    fw, fh = video_clip.size
    seating_map = sample_speaker_seating_from_utterances(
        video_clip,
        transcript_data,
        max_samples_per_speaker=max_samples_per_speaker,
    )
    if len(seating_map) < 2:
        return {}

    panels = bind_speakers_to_columns(seating_map, fw, fh)
    if not panels:
        return {}

    speaker_times: Dict[str, List[float]] = {}
    for utt in transcript_data.get("utterances") or []:
        speaker = utt.get("speaker")
        if not speaker or str(speaker) not in panels:
            continue
        spk = str(speaker)
        bucket = speaker_times.setdefault(spk, [])
        if len(bucket) >= max_samples_per_speaker:
            continue
        start_s = utt.get("start", 0) / 1000.0
        end_s = utt.get("end", 0) / 1000.0
        mid = max(0.0, min((start_s + end_s) / 2.0, video_clip.duration - 0.05))
        bucket.append(mid)

    for speaker, panel in panels.items():
        slot = {"x": panel["x"], "y": panel["y"], "w": panel["w"], "h": panel["h"]}
        xs: List[int] = []
        ys: List[int] = []
        for t in speaker_times.get(speaker, []):
            try:
                frame = video_clip.get_frame(t)
                fh_frame, _ = frame.shape[:2]
                faces = _filter_watermark_faces(_detect_faces_in_frame(frame), fh_frame)
                best = _best_face_in_slot(faces, slot["x"], slot["w"])
                if best:
                    fx, fy, fw_box, fh_box = best
                    xs.append(int(fx + fw_box / 2))
                    ys.append(int(fy + fh_box / 2))
            except Exception as exc:
                logger.debug("Panel sample failed for %s at %.2fs: %s", speaker, t, exc)

        if xs:
            panel["face_cx"] = int(np.median(xs))
            panel["face_cy"] = int(np.median(ys))
        else:
            panel["face_cx"] = _slot_inner_face_cx(panel)
            panel["face_cy"] = int(fh * 0.38)

        logger.info(
            "Speaker panel %s → slot x=%s w=%s face=(%s,%s)",
            speaker,
            panel["x"],
            panel["w"],
            panel.get("face_cx"),
            panel.get("face_cy"),
        )

    return panels


def load_cached_speaker_panels(video_path: Path) -> Optional[Dict[str, Dict[str, int]]]:
    cache_path = video_path.with_suffix(".speaker_panel_cache.json")
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text())
        if payload.get("version") != PANEL_CACHE_VERSION:
            return None
        return payload.get("panels") or None
    except Exception:
        return None


def cache_speaker_panels(video_path: Path, panels: Dict[str, Dict[str, int]]) -> None:
    cache_path = video_path.with_suffix(".speaker_panel_cache.json")
    cache_path.write_text(
        json.dumps(
            {"version": PANEL_CACHE_VERSION, "panels": panels},
            indent=2,
        )
    )


def get_or_calibrate_panels(video_clip, transcript_data: Dict, video_path: Path) -> Dict[str, Dict[str, int]]:
    cached = load_cached_speaker_panels(video_path)
    if cached:
        logger.info("Loaded cached speaker panels for %s speakers", len(cached))
        return cached
    panels = calibrate_speaker_panels(video_clip, transcript_data)
    if panels:
        cache_speaker_panels(video_path, panels)
    return panels


def is_portrait_source(src_w: int, src_h: int) -> bool:
    """True when source is already portrait (9:16 or taller)."""
    if src_h <= 0:
        return False
    return (src_w / src_h) <= (9 / 16) + 0.02


def default_riverside_panels(src_w: int, src_h: int) -> Dict[str, Dict[str, int]]:
    """Fallback equal columns for Riverside 1280×720-style dual-feed layouts."""
    half_w = src_w // 2
    left = {
        "x": 0,
        "y": 0,
        "w": half_w,
        "h": src_h,
        "face_cx": int(half_w * SLOT_INNER_EDGE_FRAC),
        "face_cy": int(src_h * 0.38),
    }
    right = {
        "x": half_w,
        "y": 0,
        "w": half_w,
        "h": src_h,
        "face_cx": half_w + int(half_w * SLOT_INNER_EDGE_FRAC),
        "face_cy": int(src_h * 0.38),
    }
    return {"A": left, "B": right}


def resolve_speaker_panel(
    speaker: Optional[str],
    panels: Dict[str, Dict[str, int]],
    seating_map: Optional[Dict[str, int]] = None,
    src_w: int = 1280,
    src_h: int = 720,
) -> Optional[Dict[str, int]]:
    """Resolve the panel for ``speaker``, using spatial seating as fallback."""
    if speaker and speaker in panels:
        return panels[speaker]
    if speaker and seating_map and speaker in seating_map:
        bound = bind_speakers_to_columns({speaker: seating_map[speaker]}, src_w, src_h)
        if speaker in bound:
            return bound[speaker]
    if panels:
        if speaker and seating_map:
            target_x = seating_map.get(speaker)
            if target_x is not None:
                return min(
                    panels.values(),
                    key=lambda p: abs(p.get("face_cx", p["x"]) - target_x),
                )
        return next(iter(panels.values()))
    return None


def face_center_in_slot(
    video_clip,
    t_s: float,
    panel: Dict[str, int],
) -> Optional[Tuple[int, int]]:
    """Detect face center inside a speaker column at ``t_s``."""
    try:
        frame = video_clip.get_frame(t_s)
    except Exception:
        return None
    fh, _ = frame.shape[:2]
    faces = _filter_watermark_faces(_detect_faces_in_frame(frame), fh)
    best = _best_face_in_slot(faces, panel["x"], panel["w"])
    if not best:
        return None
    fx, fy, fw_box, fh_box = best
    return int(fx + fw_box / 2), int(fy + fh_box / 2)


def is_riverside_dual_feed(
    src_w: int,
    src_h: int,
    panels: Dict[str, Dict[str, int]],
) -> bool:
    """
    True for Riverside downloads: landscape container with two portrait camera columns.

    Example: 1280×720 with two 640×720 feeds side-by-side.
    """
    if src_h <= 0 or src_w <= src_h:
        return False
    if len(panels) == 2:
        half_w = src_w / 2
        for panel in panels.values():
            pw, ph = panel.get("w", 0), panel.get("h", 0)
            if ph <= 0 or pw / ph < 0.85:
                return False
            if abs(pw - half_w) > src_w * 0.08:
                return False
        return True
    if len(panels) == 1:
        return False
    # Dimension heuristic when panels are not yet calibrated
    half_w = src_w / 2
    return half_w / src_h >= 0.85


def riverside_slot_crop(
    panel: Dict[str, int],
    src_w: int,
    src_h: int,
    *,
    face_cx: Optional[int] = None,
    face_cy: Optional[int] = None,
    use_full_column: bool = False,
) -> Tuple[int, int, int, int]:
    """
    Crop a Riverside camera column to 9:16 using full slot height (no extra zoom).

    Centers horizontally on the calibrated or detected face; optionally uses the
    entire column when face detection fails.
    """
    px, py, pw, ph = panel["x"], panel["y"], panel["w"], panel["h"]
    if use_full_column:
        x1 = max(0, min(px, src_w - pw))
        y1 = max(0, min(py, src_h - ph))
        return x1, y1, x1 + pw, y1 + ph

    cx = face_cx if face_cx is not None else panel.get("face_cx", _slot_inner_face_cx(panel))
    crop_h = round_to_even(ph)
    crop_w = round_to_even(int(crop_h * 9 / 16))
    if crop_w > pw:
        crop_w = round_to_even(pw)
        crop_h = round_to_even(int(crop_w * 16 / 9))
    x1 = cx - crop_w // 2
    x1 = max(px, min(x1, px + pw - crop_w))
    y1 = max(py, min(py, py + ph - crop_h))
    x1 = max(0, min(x1, src_w - crop_w))
    y1 = max(0, min(y1, src_h - crop_h))
    return x1, y1, x1 + crop_w, y1 + crop_h


def riverside_dual_half_crop(
    panel: Dict[str, int],
    src_w: int,
    src_h: int,
    target_w: int,
    target_h: int,
    *,
    face_cx: Optional[int] = None,
    face_cy: Optional[int] = None,
) -> Tuple[int, int, int, int]:
    """
    Crop a Riverside column for a stacked dual half (e.g. 1080×960).

    Uses the widest cover-fit rect matching ``target_w/target_h`` inside the
    column so uniform resize does not stretch faces horizontally.
    """
    px, py, pw, ph = panel["x"], panel["y"], panel["w"], panel["h"]
    cx = face_cx if face_cx is not None else panel.get("face_cx", _slot_inner_face_cx(panel))
    cy = face_cy if face_cy is not None else panel.get("face_cy", int(ph * 0.38))

    target_aspect = target_w / max(target_h, 1)
    slot_aspect = pw / max(ph, 1)

    if slot_aspect >= target_aspect:
        crop_h = round_to_even(ph)
        crop_w = round_to_even(int(crop_h * target_aspect))
    else:
        crop_w = round_to_even(pw)
        crop_h = round_to_even(int(crop_w / target_aspect))

    if crop_w > pw:
        crop_w = round_to_even(pw)
        crop_h = round_to_even(int(crop_w / target_aspect))
    if crop_h > ph:
        crop_h = round_to_even(ph)
        crop_w = round_to_even(int(crop_h * target_aspect))

    x1 = cx - crop_w // 2
    x1 = max(px, min(x1, px + pw - crop_w))
    y1 = cy - int(crop_h * 0.38)
    y1 = max(py, min(y1, py + ph - crop_h))
    x1 = max(0, min(x1, src_w - crop_w))
    y1 = max(0, min(y1, src_h - crop_h))
    return x1, y1, x1 + crop_w, y1 + crop_h


def face_in_panel(
    faces: List[Tuple[int, int, int, int]],
    panel: Dict[str, int],
    *,
    frame_h: Optional[int] = None,
) -> bool:
    """Return True when a face is detected inside a speaker column."""
    filtered = faces
    if frame_h is not None:
        filtered = _filter_watermark_faces(faces, frame_h)
    return _best_face_in_slot(filtered, panel["x"], panel["w"]) is not None


def fit_portrait_crop(
    panel: Dict[str, int],
    src_w: int,
    src_h: int,
    *,
    face_cx: Optional[int] = None,
    face_cy: Optional[int] = None,
) -> Tuple[int, int, int, int]:
    """
    Crop a speaker slot to 9:16 with apr23-style head+shoulders framing.

    Uses nearly full frame height, centers on face with headroom, caps max zoom.
    """
    px, py, pw, ph = panel["x"], panel["y"], panel["w"], panel["h"]
    cx = face_cx if face_cx is not None else panel.get("face_cx", px + pw // 2)
    cy = face_cy if face_cy is not None else panel.get("face_cy", int(src_h * 0.38))

    if is_portrait_source(src_w, src_h):
        crop_w = round_to_even(src_w)
        crop_h = round_to_even(int(crop_w * 16 / 9))
        if crop_h > src_h:
            crop_h = round_to_even(src_h)
            crop_w = round_to_even(int(crop_h * 9 / 16))
        x1 = max(0, min(round_to_even(cx - crop_w // 2), src_w - crop_w))
        y1 = max(0, min(round_to_even(cy - int(crop_h * 0.38)), src_h - crop_h))
        return x1, y1, x1 + crop_w, y1 + crop_h

    crop_h = round_to_even(min(src_h, int(src_h * 0.92)))
    crop_w = round_to_even(int(crop_h * 9 / 16))

    min_crop_w = round_to_even(int(pw * 0.55))
    if crop_w < min_crop_w:
        crop_w = min(min_crop_w, pw, src_w)
        crop_w = round_to_even(crop_w)
        crop_h = round_to_even(int(crop_w * 16 / 9))
        if crop_h > src_h:
            crop_h = round_to_even(src_h)
            crop_w = round_to_even(int(crop_h * 9 / 16))

    if crop_w > pw:
        crop_w = round_to_even(min(pw, src_w))
        crop_h = round_to_even(int(crop_w * 16 / 9))

    x1 = cx - crop_w // 2
    x1 = max(px, min(x1, px + pw - crop_w))
    x1 = max(0, min(x1, src_w - crop_w))

    y1 = cy - int(crop_h * 0.38)
    y1 = max(py, min(y1, py + ph - crop_h))
    y1 = max(0, min(y1, src_h - crop_h))

    return x1, y1, x1 + crop_w, y1 + crop_h


def panel_to_vertical_crop(
    panel: Dict[str, int],
    src_w: int,
    src_h: int,
) -> Tuple[int, int, int, int]:
    """Crop a speaker panel region to 9:16."""
    return fit_portrait_crop(panel, src_w, src_h)


def round_to_even(value: int) -> int:
    return value if value % 2 == 0 else value - 1
