"""Model management API: discover installed Ollama models, recommend models
for the host system, and install new models with streamed progress."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import os
import platform

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ...config import get_config
from ..deps import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["models"])

OLLAMA_PREFIX = "ollama:"

# Curated catalog of models that work well for transcript analysis.
# min_ram_gb is the practical minimum host memory for comfortable inference.
# Gemma 4 requires Ollama 0.20+ (ollama pull gemma4:e4b).
MODEL_CATALOG: List[Dict[str, Any]] = [
    {
        "tag": "qwen3:4b",
        "display_name": "Qwen 3 4B",
        "params_b": 4,
        "download_gb": 2.5,
        "min_ram_gb": 8,
        "speed": "fast",
        "quality": "good",
        "description": "Fast Qwen 3 tier. Strong JSON output and reliable clip picks on 8 GB machines.",
    },
    {
        "tag": "qwen3:8b",
        "display_name": "Qwen 3 8B",
        "params_b": 8,
        "download_gb": 5.2,
        "min_ram_gb": 16,
        "speed": "medium",
        "quality": "good",
        "description": "Top pick for 16 GB machines. Best balance of JSON reliability and clip quality.",
    },
    {
        "tag": "gemma4:e2b",
        "display_name": "Gemma 4 E2B",
        "params_b": 2,
        "download_gb": 7.2,
        "min_ram_gb": 8,
        "speed": "fast",
        "quality": "good",
        "description": "Google's newest edge model. Quick clip picks on 8 GB machines.",
    },
    {
        "tag": "gemma4:e4b",
        "display_name": "Gemma 4 E4B",
        "params_b": 4,
        "download_gb": 9.6,
        "min_ram_gb": 16,
        "speed": "medium",
        "quality": "good",
        "description": "Top pick for 16 GB laptops. Strong hook detection and concise JSON output.",
    },
    {
        "tag": "gemma4:26b",
        "display_name": "Gemma 4 26B MoE",
        "params_b": 26,
        "download_gb": 18.0,
        "min_ram_gb": 24,
        "speed": "medium",
        "quality": "great",
        "description": "MoE architecture — near-flagship quality with lighter active inference.",
    },
    {
        "tag": "gemma4:31b",
        "display_name": "Gemma 4 31B",
        "params_b": 31,
        "download_gb": 20.0,
        "min_ram_gb": 32,
        "speed": "slow",
        "quality": "great",
        "description": "Maximum local quality for clip analysis on workstation-class RAM.",
    },
    {
        "tag": "llama3.2:3b",
        "display_name": "Llama 3.2 3B",
        "params_b": 3,
        "download_gb": 2.0,
        "min_ram_gb": 8,
        "speed": "fast",
        "quality": "basic",
        "description": "Small and quick. Good fallback for short videos on low-RAM machines.",
    },
    {
        "tag": "llama3.1:8b",
        "display_name": "Llama 3.1 8B",
        "params_b": 8,
        "download_gb": 4.9,
        "min_ram_gb": 16,
        "speed": "medium",
        "quality": "good",
        "description": "Reliable JSON output and solid clip selection on 16 GB machines.",
    },
    {
        "tag": "qwen2.5:7b",
        "display_name": "Qwen 2.5 7B",
        "params_b": 7,
        "download_gb": 4.7,
        "min_ram_gb": 16,
        "speed": "medium",
        "quality": "good",
        "description": "Strong reasoning for its size. Alternative if Gemma under-delivers.",
    },
    {
        "tag": "qwen2.5:14b",
        "display_name": "Qwen 2.5 14B",
        "params_b": 14,
        "download_gb": 9.0,
        "min_ram_gb": 24,
        "speed": "slow",
        "quality": "great",
        "description": "Noticeably better segment picking. Needs 24 GB+ RAM.",
    },
    {
        "tag": "mistral:7b",
        "display_name": "Mistral 7B",
        "params_b": 7,
        "download_gb": 4.1,
        "min_ram_gb": 16,
        "speed": "fast",
        "quality": "good",
        "description": "Fast and dependable. A lighter legacy alternative.",
    },
]

GEMMA4_DEFAULT_TAG = "gemma4:e4b"
QUALITY_RANK = {"basic": 0, "good": 1, "great": 2}


def _normalize_ollama_name(name: str) -> str:
    """Map Ollama tag aliases to catalog tags."""
    base = name.split(":latest")[0]
    if base == "gemma4":
        return GEMMA4_DEFAULT_TAG
    return base


def _catalog_priority(tag: str) -> int:
    """Prefer Qwen 3, then Gemma 4, when quality and fit are tied."""
    if tag.startswith("qwen3:"):
        return 3
    if tag.startswith("gemma4:"):
        return 2
    return 0


def _is_catalog_model_installed(installed_names: set[str], catalog_tag: str) -> bool:
    return any(
        _normalize_ollama_name(name) == catalog_tag or name == catalog_tag
        for name in installed_names
    )


def _pick_best_model(recommendations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    comfortable = [r for r in recommendations if r["fit"] in {"great", "ok"}]
    if not comfortable:
        return None
    return max(
        comfortable,
        key=lambda r: (
            QUALITY_RANK[r["quality"]],
            _catalog_priority(r["tag"]),
            r["min_ram_gb"],
        ),
    )


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("PYTHONPATH") == "/app"


def _ollama_root_url() -> str:
    """Resolve the Ollama server root URL (without /v1 suffix)."""
    config = get_config()
    base = config.ollama_base_url
    if base:
        return base.rstrip("/").removesuffix("/v1")
    if _running_in_docker():
        return "http://host.docker.internal:11434"
    return "http://localhost:11434"


def _psutil_system_specs() -> Dict[str, Any]:
    config = get_config()
    machine = platform.machine()
    system_name = platform.system()
    total_ram_gb = config.host_total_ram_gb

    try:
        import psutil

        total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        spec_source = "psutil"
    except ImportError:
        logger.warning("psutil not installed; using configured or default RAM for recommendations")
        if total_ram_gb is None:
            total_ram_gb = 16.0
        spec_source = "configured" if config.host_total_ram_gb else "default"

    return {
        "platform": system_name.lower(),
        "machine": machine,
        "cpu_count": os.cpu_count() or 1,
        "total_ram_gb": total_ram_gb,
        "apple_silicon": machine in {"arm64", "aarch64"} and system_name == "Darwin",
        "has_gpu": False,
        "gpu_name": None,
        "gpu_vram_gb": None,
        "spec_source": spec_source,
    }


def _parse_ollama_info(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    compute = payload.get("compute") or {}
    system_compute = compute.get("system_compute") or compute.get("system") or {}
    total_memory = system_compute.get("total_memory") or 0
    if not total_memory:
        return None

    cpu_cores = system_compute.get("cpu_cores") or os.cpu_count() or 1
    total_ram_gb = round(total_memory / (1024**3), 1)

    gpus = compute.get("supported_gpus") or []
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    has_gpu = False
    if gpus:
        primary = gpus[0]
        gpu_name = primary.get("name")
        gpu_memory = primary.get("total_memory") or 0
        if gpu_memory:
            gpu_vram_gb = round(gpu_memory / (1024**3), 1)
        has_gpu = bool(gpu_name or gpu_vram_gb)

    runners = compute.get("available_runners") or []
    apple_silicon = any(
        runner in {"metal", "metal_avx", "metal_avx2"} for runner in runners
    )

    return {
        "platform": platform.system().lower(),
        "machine": platform.machine(),
        "cpu_count": int(cpu_cores),
        "total_ram_gb": total_ram_gb,
        "apple_silicon": apple_silicon,
        "has_gpu": has_gpu,
        "gpu_name": gpu_name,
        "gpu_vram_gb": gpu_vram_gb,
        "spec_source": "ollama",
    }


async def _fetch_ollama_system_info() -> Optional[Dict[str, Any]]:
    url = f"{_ollama_root_url()}/api/info"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError, TypeError) as exc:
        logger.info("Ollama system info not available at %s: %s", url, exc)
        return None

    if not isinstance(payload, dict):
        return None
    return _parse_ollama_info(payload)


async def _system_specs() -> Dict[str, Any]:
    ollama_specs = await _fetch_ollama_system_info()
    if ollama_specs:
        return ollama_specs
    specs = _psutil_system_specs()
    config = get_config()
    if config.host_total_ram_gb:
        specs["total_ram_gb"] = config.host_total_ram_gb
        specs["spec_source"] = "configured"
    return specs


def _fit_for_system(min_ram_gb: float, total_ram_gb: float) -> str:
    if total_ram_gb >= min_ram_gb * 1.5:
        return "great"
    if total_ram_gb >= min_ram_gb:
        return "ok"
    if total_ram_gb >= min_ram_gb * 0.75:
        return "tight"
    return "not_recommended"


async def _fetch_installed_models() -> Optional[List[Dict[str, Any]]]:
    """Return installed Ollama models, or None when Ollama is unreachable."""
    url = f"{_ollama_root_url()}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        logger.info("Ollama not reachable at %s: %s", url, exc)
        return None

    models = []
    for entry in payload.get("models", []):
        details = entry.get("details") or {}
        models.append(
            {
                "name": entry.get("name", ""),
                "model": f"{OLLAMA_PREFIX}{entry.get('name', '')}",
                "size_gb": round((entry.get("size") or 0) / (1024**3), 1),
                "parameter_size": details.get("parameter_size"),
                "quantization": details.get("quantization_level"),
                "modified_at": entry.get("modified_at"),
            }
        )
    return models


@router.get("/installed")
async def get_installed_models(request: Request):
    """List installed Ollama models plus the configured default model."""
    get_current_user_id(request)
    config = get_config()

    installed = await _fetch_installed_models()
    cloud_models = []
    if config.google_api_key:
        cloud_models.append(
            {"model": "google-gla:gemini-3-flash-preview", "display_name": "Gemini 3 Flash (cloud)"}
        )
    if config.openai_api_key:
        cloud_models.append({"model": "openai:gpt-5.2", "display_name": "GPT-5.2 (cloud)"})
    if config.anthropic_api_key:
        cloud_models.append(
            {"model": "anthropic:claude-4-sonnet", "display_name": "Claude 4 Sonnet (cloud)"}
        )

    return {
        "ollama_available": installed is not None,
        "ollama_url": _ollama_root_url(),
        "installed": installed or [],
        "cloud_models": cloud_models,
        "default_model": config.llm,
    }


@router.get("/recommendations")
async def get_model_recommendations(request: Request):
    """Recommend Ollama models based on the host system's resources."""
    get_current_user_id(request)

    specs = await _system_specs()
    installed = await _fetch_installed_models()
    installed_names = {m["name"] for m in installed} if installed else set()

    recommendations = []
    for entry in MODEL_CATALOG:
        fit = _fit_for_system(entry["min_ram_gb"], specs["total_ram_gb"])
        is_installed = _is_catalog_model_installed(installed_names, entry["tag"])
        recommendations.append(
            {
                **entry,
                "model": f"{OLLAMA_PREFIX}{entry['tag']}",
                "fit": fit,
                "installed": is_installed,
            }
        )

    best = _pick_best_model(recommendations)

    return {
        "system": specs,
        "ollama_available": installed is not None,
        "recommendations": recommendations,
        "best_pick": best["model"] if best else None,
    }


class PullRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)


@router.post("/pull")
async def pull_model(body: PullRequest, request: Request):
    """Install an Ollama model, streaming progress as Server-Sent Events."""
    get_current_user_id(request)

    import re

    model_tag = body.model.strip().removeprefix(OLLAMA_PREFIX)
    if not re.match(r"^[A-Za-z0-9._/-]+(:[A-Za-z0-9._-]+)?$", model_tag):
        raise HTTPException(status_code=400, detail="Invalid model tag")

    root_url = _ollama_root_url()

    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{root_url}/api/pull",
                    json={"model": model_tag, "stream": True},
                ) as response:
                    if response.status_code != 200:
                        detail = (await response.aread()).decode("utf-8", "replace")
                        yield {
                            "event": "error",
                            "data": json.dumps(
                                {"error": f"Ollama returned {response.status_code}: {detail[:300]}"}
                            ),
                        }
                        return

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if payload.get("error"):
                            yield {
                                "event": "error",
                                "data": json.dumps({"error": payload["error"]}),
                            }
                            return

                        status = payload.get("status", "")
                        total = payload.get("total") or 0
                        completed = payload.get("completed") or 0
                        percent = round(completed / total * 100, 1) if total else None

                        yield {
                            "event": "progress",
                            "data": json.dumps(
                                {
                                    "status": status,
                                    "total": total,
                                    "completed": completed,
                                    "percent": percent,
                                }
                            ),
                        }

                        if status == "success":
                            yield {
                                "event": "done",
                                "data": json.dumps({"model": f"{OLLAMA_PREFIX}{model_tag}"}),
                            }
                            return
        except httpx.HTTPError as exc:
            logger.error("Model pull failed for %s: %s", model_tag, exc)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": f"Could not reach Ollama at {root_url}. Is it running?"}
                ),
            }

    return EventSourceResponse(event_generator())
