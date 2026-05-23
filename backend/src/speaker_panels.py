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

PANEL_CACHE_VERSION = 1


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
    x: int, y: int, w: int, h: int, fw: int, fh: int, pad_x: float = 0.35, pad_y: float = 0.25
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


def calibrate_speaker_panels(
    video_clip,
    transcript_data: Dict,
    *,
    max_samples_per_speaker: int = 4,
) -> Dict[str, Dict[str, int]]:
    """
    Build ``{speaker_id: {x, y, w, h}}`` panel map from diarized utterances.

    Samples face detections during each speaker's turns and takes the median
    expanded bounding box as that speaker's fixed panel.
    """
    utterances = transcript_data.get("utterances") or []
    if not utterances:
        return {}

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

    if len(speaker_times) < 2:
        return {}

    fw, fh = video_clip.size
    panel_samples: Dict[str, List[Dict[str, int]]] = {spk: [] for spk in speaker_times}

    for speaker, times in speaker_times.items():
        for t in times:
            try:
                frame = video_clip.get_frame(t)
                faces = _detect_faces_in_frame(frame)
                if not faces:
                    continue
                # Pick face closest to horizontal slot center for this speaker
                slot_idx = sorted(speaker_times.keys()).index(speaker)
                slot_center_x = (slot_idx + 0.5) * (fw / len(speaker_times))
                best = min(
                    faces,
                    key=lambda b: abs((b[0] + b[2] / 2) - slot_center_x),
                )
                panel_samples[speaker].append(_expand_bbox(*best, fw, fh))
            except Exception as exc:
                logger.debug("Panel sample failed for %s at %.2fs: %s", speaker, t, exc)

    panels: Dict[str, Dict[str, int]] = {}
    missing: List[str] = []
    for speaker, samples in panel_samples.items():
        panel = _median_panel(samples)
        if panel:
            panels[speaker] = panel
        else:
            missing.append(speaker)

    if missing:
        fallback = _slot_panels(len(speaker_times), fw, fh)
        ordered = sorted(speaker_times.keys())
        for idx, speaker in enumerate(ordered):
            if speaker not in panels and idx < len(fallback):
                panels[speaker] = fallback[idx]
                logger.info(
                    "Speaker %s using slot fallback panel x=%s w=%s",
                    speaker,
                    panels[speaker]["x"],
                    panels[speaker]["w"],
                )

    for speaker, panel in panels.items():
        logger.info(
            "Speaker panel %s → x=%s y=%s w=%s h=%s",
            speaker,
            panel["x"],
            panel["y"],
            panel["w"],
            panel["h"],
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


def panel_to_vertical_crop(
    panel: Dict[str, int],
    src_w: int,
    src_h: int,
) -> Tuple[int, int, int, int]:
    """Crop a speaker panel region to 9:16, centered within the panel."""
    px, py, pw, ph = panel["x"], panel["y"], panel["w"], panel["h"]
    crop_h = ph
    crop_w = round_to_even(int(crop_h * 9 / 16))
    if crop_w > pw:
        crop_w = round_to_even(pw)
        crop_h = round_to_even(int(crop_w * 16 / 9))
    cx = px + pw // 2
    cy = py + ph // 2
    x1 = max(px, min(cx - crop_w // 2, px + pw - crop_w))
    y1 = max(py, min(cy - crop_h // 2, py + ph - crop_h))
    x1 = max(0, min(x1, src_w - crop_w))
    y1 = max(0, min(y1, src_h - crop_h))
    return x1, y1, x1 + crop_w, y1 + crop_h


def round_to_even(value: int) -> int:
    return value if value % 2 == 0 else value - 1
