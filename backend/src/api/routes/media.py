"""
Media API routes (fonts, transitions, uploads).
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Any, cast
import logging
import uuid
import aiofiles

from ...config import get_config
from ..deps import get_current_user_id
from ...utils.async_helpers import run_in_thread
import base64

from ...speaker_panels import detect_face_panels_from_frame, detect_face_panels_from_video
from ...font_registry import (
    FONTS_DIR,
    SUPPORTED_FONT_EXTENSIONS,
    build_user_font_stem,
    find_font_path,
    get_available_fonts as list_available_fonts,
    get_user_fonts_dir,
    sanitize_font_stem,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["media"])

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB
MAX_FONT_BYTES = 10 * 1024 * 1024  # 10 MB
UPLOAD_CHUNK_SIZE = 1024 * 1024


async def _stream_upload_to_path(upload: UploadFile, target: Path, max_bytes: int) -> None:
    """Write an upload to disk in chunks, enforcing a size limit."""
    written = 0
    async with aiofiles.open(target, "wb") as out:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                await out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum size of {max_bytes // (1024 * 1024)} MB",
                )
            await out.write(chunk)


@router.get("/fonts")
async def get_available_fonts_route(request: Request):
    """Get list of available fonts."""
    try:
        user_id = get_current_user_id(request)
        if not FONTS_DIR.exists():
            return {"fonts": [], "message": "Fonts directory not found"}

        fonts = list_available_fonts(user_id=user_id)
        logger.info(f"Found {len(fonts)} available fonts")
        return {"fonts": fonts}

    except Exception as e:
        logger.error(f"Error retrieving fonts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving fonts: {str(e)}")


@router.get("/fonts/{font_name}")
async def get_font_file(font_name: str, request: Request):
    """Serve a specific font file."""
    try:
        user_id = get_current_user_id(request)
        font_path = find_font_path(font_name, user_id=user_id)

        if not font_path:
            raise HTTPException(status_code=404, detail="Font not found")

        media_type = "font/ttf" if font_path.suffix.lower() == ".ttf" else "font/otf"

        return FileResponse(
            path=str(font_path),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=31536000"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving font {font_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving font: {str(e)}")


@router.post("/fonts/upload")
async def upload_font(
    request: Request,
    uploaded_file: UploadFile = File(..., alias="file"),
):
    """Upload a custom .ttf/.otf font so it appears in the font picker."""
    try:
        user_id = get_current_user_id(request)

        if not uploaded_file.filename:
            raise HTTPException(status_code=400, detail="Missing file name")

        uploaded_filename = uploaded_file.filename or "font.ttf"
        extension = Path(uploaded_filename).suffix.lower()
        if extension not in SUPPORTED_FONT_EXTENSIONS:
            raise HTTPException(
                status_code=400, detail="Only .ttf and .otf fonts are supported"
            )

        user_fonts_dir = get_user_fonts_dir(user_id)
        user_fonts_dir.mkdir(parents=True, exist_ok=True)

        original_stem = sanitize_font_stem(uploaded_filename)
        stored_stem = build_user_font_stem(user_id, original_stem)
        target_path = user_fonts_dir / f"{stored_stem}{extension}"
        suffix = 2
        while target_path.exists():
            target_path = user_fonts_dir / f"{stored_stem}-{suffix}{extension}"
            suffix += 1

        await _stream_upload_to_path(uploaded_file, target_path, MAX_FONT_BYTES)

        logger.info(f"Uploaded font: {target_path.name}")

        return {
            "font": {
                "name": target_path.stem,
                "display_name": original_stem.replace("-", " ")
                .replace("_", " ")
                .title(),
                "filename": target_path.name,
                "format": extension.lstrip("."),
                "scope": "user",
            },
            "message": "Font uploaded successfully",
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading font: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading font: {str(e)}")


@router.get("/transitions")
async def get_available_transitions():
    """Get list of available transition effects."""
    try:
        from ...video_utils import get_available_transitions

        transitions = get_available_transitions()

        transition_info = []
        for transition_path in transitions:
            transition_file = Path(transition_path)
            transition_info.append(
                {
                    "name": transition_file.stem,
                    "display_name": transition_file.stem.replace("_", " ")
                    .replace("-", " ")
                    .title(),
                }
            )

        logger.info(f"Found {len(transition_info)} available transitions")
        return {"transitions": transition_info}

    except Exception as e:
        logger.error(f"Error retrieving transitions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving transitions: {str(e)}"
        )


@router.get("/caption-templates")
async def get_caption_templates():
    """Get available caption templates.

    Returns a stable default list if optional template module is unavailable.
    """
    default_templates = [
        {
            "id": "default",
            "name": "Default",
            "description": "Clean subtitle style",
            "animation": "none",
            "font_family": "TikTokSans-Regular",
            "font_size": 24,
            "font_color": "#FFFFFF",
        }
    ]

    try:
        from ...caption_templates import get_template_info

        templates = get_template_info()
        return {"templates": templates or default_templates}
    except Exception:
        return {"templates": default_templates}
def _analyze_preview_frame(content: bytes) -> dict:
    """Decode a JPEG/PNG frame and detect speaker panel regions."""
    import cv2
    import numpy as np

    arr = np.frombuffer(content, dtype=np.uint8)
    frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise ValueError("Could not decode image frame")

    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    fh, fw = frame_rgb.shape[:2]
    panels = detect_face_panels_from_frame(frame_rgb)

    return {
        "frame_width": fw,
        "frame_height": fh,
        "panels": panels,
        "default_panel_index": 0,
    }


def _process_preview_video(video_path: Path, seek_seconds: float) -> dict:
    """Extract preview frame + speaker panels from uploaded video."""
    import cv2

    panels, fw, fh, primary_frame = detect_face_panels_from_video(
        video_path, seek_seconds=seek_seconds
    )
    ok, encoded = cv2.imencode(
        ".jpg",
        cv2.cvtColor(primary_frame, cv2.COLOR_RGB2BGR),
        [int(cv2.IMWRITE_JPEG_QUALITY), 85],
    )
    if not ok:
        raise ValueError("Could not encode preview thumbnail")

    thumbnail_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
    return {
        "frame_width": fw,
        "frame_height": fh,
        "panels": panels,
        "default_panel_index": 0,
        "thumbnail_base64": thumbnail_b64,
        "seek_seconds": seek_seconds,
    }


@router.post("/media/preview-layout")
async def preview_layout(request: Request):
    """Upload video (or JPEG frame) and detect speaker layout for caption preview."""
    try:
        get_current_user_id(request)
        form_data = await request.form()

        seek_raw = form_data.get("seek_seconds", "300")
        try:
            seek_seconds = float(seek_raw)
        except (TypeError, ValueError):
            seek_seconds = 300.0

        video_file = cast(Any, form_data.get("video"))
        frame_file = cast(Any, form_data.get("frame"))

        if getattr(video_file, "filename", None) and hasattr(video_file, "read"):
            upload = cast(UploadFile, video_file)
            upload_filename = upload.filename or "upload.mp4"
            file_extension = Path(upload_filename).suffix.lower() or ".mp4"
            if file_extension not in ALLOWED_VIDEO_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported video format. Use one of: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}",
                )
            uploads_dir = Path(get_config().temp_dir) / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            video_path = uploads_dir / unique_filename

            await _stream_upload_to_path(upload, video_path, MAX_UPLOAD_BYTES)

            layout = await run_in_thread(_process_preview_video, video_path, seek_seconds)
            layout["video_path"] = f"upload://{unique_filename}"
            logger.info(
                "Preview layout (video): %sx%s, %s panel(s), seek=%ss",
                layout["frame_width"],
                layout["frame_height"],
                len(layout["panels"]),
                seek_seconds,
            )
            return layout

        if getattr(frame_file, "filename", None) and hasattr(frame_file, "read"):
            frame = cast(UploadFile, frame_file)
            content = await frame.read()
            if len(content) > 2 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Frame image must be under 2MB")
            result = await run_in_thread(_analyze_preview_frame, content)
            logger.info(
                "Preview layout (frame): %sx%s, %s panel(s)",
                result["frame_width"],
                result["frame_height"],
                len(result["panels"]),
            )
            return result

        raise HTTPException(status_code=400, detail="Provide a video or frame image")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error analyzing preview layout: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Error analyzing preview layout: {exc}"
        ) from exc


@router.post("/upload")
async def upload_video(request: Request):
    """Upload a video to the server."""
    try:
        get_current_user_id(request)

        # Get the form data
        form_data = await request.form()
        video_file = cast(Any, form_data.get("video"))

        if not getattr(video_file, "filename", None) or not hasattr(video_file, "read"):
            raise HTTPException(status_code=400, detail="No video file provided")

        upload = cast(UploadFile, video_file)
        upload_filename = upload.filename or "upload.mp4"

        file_extension = Path(upload_filename).suffix.lower() or ".mp4"
        if file_extension not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported video format. Use one of: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}",
            )

        uploads_dir = Path(get_config().temp_dir) / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        unique_filename = f"{uuid.uuid4()}{file_extension}"
        video_path = uploads_dir / unique_filename

        await _stream_upload_to_path(upload, video_path, MAX_UPLOAD_BYTES)

        logger.info(f"✅ Video uploaded successfully to: {video_path}")

        return {
            "message": "Video uploaded successfully",
            "video_path": f"upload://{unique_filename}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading video: {str(e)}")
