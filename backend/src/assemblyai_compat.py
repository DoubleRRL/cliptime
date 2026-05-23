"""
Compatibility layer for AssemblyAI API migration: speech_model -> speech_models.

The hosted API now requires `speech_models` (e.g. universal-3-pro). Older SDK
versions only expose deprecated `speech_model` (best/nano) on TranscriptRequest.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_PATCH_APPLIED = False


def speech_models_for_mode(speech_model: str = "best") -> List[str]:
    """Map internal mode names to AssemblyAI speech_models priority list."""
    if speech_model == "nano":
        return ["universal-2"]
    return ["universal-3-pro", "universal-2"]


def _serialize_request(request) -> dict:
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_none=True, by_alias=True)
    return request.dict(exclude_none=True, by_alias=True)


def _apply_speech_models(payload: dict) -> dict:
    """Replace deprecated speech_model with required speech_models array."""
    updated = dict(payload)
    legacy = updated.pop("speech_model", None)

    if "speech_models" in updated and updated["speech_models"]:
        return updated

    if legacy is not None:
        legacy_value = getattr(legacy, "value", legacy)
        legacy_str = str(legacy_value).lower()
        if legacy_str in {"nano", "universal-2"}:
            updated["speech_models"] = ["universal-2"]
        else:
            updated["speech_models"] = ["universal-3-pro", "universal-2"]
    else:
        updated["speech_models"] = ["universal-3-pro", "universal-2"]

    return updated


def apply_assemblyai_api_patch() -> None:
    """Monkey-patch create_transcript once so API payloads use speech_models."""
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    import assemblyai.api as api

    original_create = api.create_transcript

    def patched_create_transcript(client, request):
        payload = _apply_speech_models(_serialize_request(request))
        response = client.post(
            api.ENDPOINT_TRANSCRIPT,
            json=payload,
        )
        from assemblyai import types

        if response.status_code != 200:
            raise types.TranscriptError(
                f"failed to transcribe url {request.audio_url}: {api._get_error_message(response)}",
                response.status_code,
            )
        return types.TranscriptResponse.parse_obj(response.json())

    api.create_transcript = patched_create_transcript
    _PATCH_APPLIED = True
    logger.info("Applied AssemblyAI speech_models API compatibility patch")
