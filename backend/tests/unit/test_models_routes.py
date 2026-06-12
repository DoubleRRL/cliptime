import contextlib
import json

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.routes import models as models_module
from src.api.routes.models import (
    MODEL_CATALOG,
    PullRequest,
    _fit_for_system,
    _is_catalog_model_installed,
    _normalize_ollama_name,
    _ollama_root_url,
    _parse_ollama_info,
    _psutil_system_specs,
    _system_specs,
    get_installed_models,
    get_model_recommendations,
    pull_model,
)
from src.config import Config, set_config_override


def _build_request(user_id: str = "user-1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"user_id", user_id.encode("utf-8"))],
        }
    )


@pytest.fixture()
def unsigned_config():
    config = Config()
    config.backend_auth_secret = None
    config.require_signed_auth = False
    set_config_override(config)
    yield config
    set_config_override(None)


def test_fit_for_system_thresholds():
    assert _fit_for_system(8, 16) == "great"
    assert _fit_for_system(16, 16) == "ok"
    assert _fit_for_system(16, 13) == "tight"
    assert _fit_for_system(32, 8) == "not_recommended"


def test_ollama_root_url_strips_v1_suffix(unsigned_config):
    unsigned_config.ollama_base_url = "http://my-ollama:11434/v1"
    assert _ollama_root_url() == "http://my-ollama:11434"


def test_ollama_root_url_defaults_to_localhost(unsigned_config, monkeypatch):
    unsigned_config.ollama_base_url = None
    monkeypatch.setattr(models_module, "_running_in_docker", lambda: False)
    assert _ollama_root_url() == "http://localhost:11434"


def test_ollama_root_url_in_docker(unsigned_config, monkeypatch):
    unsigned_config.ollama_base_url = None
    monkeypatch.setattr(models_module, "_running_in_docker", lambda: True)
    assert _ollama_root_url() == "http://host.docker.internal:11434"


def test_psutil_system_specs_shape():
    specs = _psutil_system_specs()
    assert specs["cpu_count"] >= 1
    assert specs["total_ram_gb"] > 0
    assert isinstance(specs["apple_silicon"], bool)
    assert specs["spec_source"] == "psutil"


def test_parse_ollama_info_extracts_host_ram_and_gpu():
    payload = {
        "compute": {
            "available_runners": ["cpu", "metal"],
            "system_compute": {
                "cpu_cores": 8,
                "total_memory": 16 * 1024**3,
            },
            "supported_gpus": [
                {
                    "name": "Apple M2",
                    "total_memory": 16 * 1024**3,
                }
            ],
        }
    }
    specs = _parse_ollama_info(payload)
    assert specs is not None
    assert specs["total_ram_gb"] == 16.0
    assert specs["cpu_count"] == 8
    assert specs["apple_silicon"] is True
    assert specs["has_gpu"] is True
    assert specs["gpu_name"] == "Apple M2"
    assert specs["spec_source"] == "ollama"


def test_parse_ollama_info_windows_nvidia():
    payload = {
        "compute": {
            "available_runners": ["cpu", "cuda_v12"],
            "system_compute": {
                "cpu_cores": 12,
                "total_memory": 32 * 1024**3,
            },
            "supported_gpus": [
                {
                    "name": "NVIDIA GeForce RTX 3060",
                    "total_memory": 12 * 1024**3,
                }
            ],
        }
    }
    specs = _parse_ollama_info(payload)
    assert specs is not None
    assert specs["total_ram_gb"] == 32.0
    assert specs["apple_silicon"] is False
    assert specs["gpu_name"] == "NVIDIA GeForce RTX 3060"
    assert specs["gpu_vram_gb"] == 12.0


async def test_system_specs_prefers_ollama_info(unsigned_config, monkeypatch):
    async def fake_ollama_info():
        return {
            "platform": "darwin",
            "machine": "arm64",
            "cpu_count": 8,
            "total_ram_gb": 16.0,
            "apple_silicon": True,
            "has_gpu": True,
            "gpu_name": "Apple GPU",
            "gpu_vram_gb": 16.0,
            "spec_source": "ollama",
        }

    monkeypatch.setattr(models_module, "_fetch_ollama_system_info", fake_ollama_info)
    specs = await _system_specs()
    assert specs["spec_source"] == "ollama"
    assert specs["total_ram_gb"] == 16.0


def test_model_catalog_entries_are_complete():
    for entry in MODEL_CATALOG:
        assert entry["tag"]
        assert entry["min_ram_gb"] > 0
        assert entry["quality"] in {"basic", "good", "great"}


async def test_get_installed_models_with_ollama(unsigned_config, monkeypatch):
    unsigned_config.google_api_key = "g-key"
    unsigned_config.openai_api_key = None
    unsigned_config.anthropic_api_key = None

    async def fake_fetch():
        return [
            {
                "name": "llama3.1:8b",
                "model": "ollama:llama3.1:8b",
                "size_gb": 4.9,
                "parameter_size": "8B",
                "quantization": "Q4_K_M",
                "modified_at": "2026-01-01",
            }
        ]

    monkeypatch.setattr(models_module, "_fetch_installed_models", fake_fetch)

    result = await get_installed_models(_build_request())
    assert result["ollama_available"] is True
    assert result["installed"][0]["name"] == "llama3.1:8b"
    assert any("gemini" in m["model"] for m in result["cloud_models"])


async def test_get_installed_models_without_ollama(unsigned_config, monkeypatch):
    unsigned_config.google_api_key = None
    unsigned_config.openai_api_key = None
    unsigned_config.anthropic_api_key = None

    async def fake_fetch():
        return None

    monkeypatch.setattr(models_module, "_fetch_installed_models", fake_fetch)

    result = await get_installed_models(_build_request())
    assert result["ollama_available"] is False
    assert result["installed"] == []
    assert result["cloud_models"] == []


def test_normalize_ollama_name_maps_gemma4_default():
    assert _normalize_ollama_name("gemma4:latest") == "gemma4:e4b"
    assert _normalize_ollama_name("gemma4") == "gemma4:e4b"
    assert _normalize_ollama_name("qwen2.5:7b") == "qwen2.5:7b"


def test_is_catalog_model_installed_matches_aliases():
    installed = {"gemma4", "gemma4:latest", "qwen2.5:7b"}
    assert _is_catalog_model_installed(installed, "gemma4:e4b") is True
    assert _is_catalog_model_installed(installed, "llama3.1:8b") is False


@pytest.mark.parametrize(
    ("total_ram_gb", "expected_best_tag", "heavy_fit"),
    [
        (8.0, "qwen3:4b", "not_recommended"),
        (16.0, "qwen3:8b", "not_recommended"),
        (32.0, "gemma4:31b", "ok"),
    ],
)
async def test_recommendations_best_pick_by_ram_tier(
    unsigned_config, monkeypatch, total_ram_gb, expected_best_tag, heavy_fit
):
    async def fake_fetch():
        return []

    async def fake_specs():
        return {
            "platform": "linux",
            "machine": "x86_64",
            "cpu_count": 8,
            "total_ram_gb": total_ram_gb,
            "apple_silicon": False,
            "has_gpu": False,
            "gpu_name": None,
            "gpu_vram_gb": None,
            "spec_source": "psutil",
        }

    monkeypatch.setattr(models_module, "_fetch_installed_models", fake_fetch)
    monkeypatch.setattr(models_module, "_system_specs", fake_specs)

    result = await get_model_recommendations(_build_request())
    assert result["best_pick"] == f"ollama:{expected_best_tag}"
    by_tag = {rec["tag"]: rec for rec in result["recommendations"]}
    assert by_tag["gemma4:31b"]["fit"] == heavy_fit


async def test_recommendations_mark_installed_and_pick_best(
    unsigned_config, monkeypatch
):
    async def fake_fetch():
        return [{"name": "llama3.1:8b", "model": "ollama:llama3.1:8b", "size_gb": 4.9}]

    monkeypatch.setattr(models_module, "_fetch_installed_models", fake_fetch)
    async def fake_specs():
        return {
            "platform": "darwin",
            "machine": "arm64",
            "cpu_count": 8,
            "total_ram_gb": 16.0,
            "apple_silicon": True,
            "has_gpu": False,
            "gpu_name": None,
            "gpu_vram_gb": None,
            "spec_source": "psutil",
        }

    monkeypatch.setattr(models_module, "_system_specs", fake_specs)

    result = await get_model_recommendations(_build_request())
    by_tag = {rec["tag"]: rec for rec in result["recommendations"]}

    assert by_tag["llama3.1:8b"]["installed"] is True
    assert by_tag["llama3.2:3b"]["fit"] == "great"
    assert by_tag["gemma4:31b"]["fit"] == "not_recommended"
    assert result["best_pick"] == "ollama:qwen3:8b"
    assert result["ollama_available"] is True


async def test_pull_model_rejects_invalid_tag(unsigned_config):
    with pytest.raises(HTTPException) as exc:
        await pull_model(
            PullRequest(model="ollama:bad tag; rm -rf /"), _build_request()
        )
    assert exc.value.status_code == 400


class _FakeStreamResponse:
    def __init__(self, status_code: int, lines: list[str]):
        self.status_code = status_code
        self._lines = lines

    async def aread(self):
        return b"boom"

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAsyncClient:
    def __init__(self, response: _FakeStreamResponse | None = None, error: Exception | None = None):
        self._response = response
        self._error = error

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @contextlib.asynccontextmanager
    async def stream(self, *args, **kwargs):
        if self._error:
            raise self._error
        yield self._response


async def _collect_events(response):
    events = []
    async for event in response.body_iterator:
        events.append(event)
    return events


async def test_pull_model_streams_progress_and_done(unsigned_config, monkeypatch):
    lines = [
        json.dumps({"status": "downloading", "total": 100, "completed": 50}),
        json.dumps({"status": "success"}),
    ]
    monkeypatch.setattr(
        models_module.httpx,
        "AsyncClient",
        _FakeAsyncClient(_FakeStreamResponse(200, lines)),
    )

    response = await pull_model(PullRequest(model="llama3.2:3b"), _build_request())
    events = await _collect_events(response)

    assert any(e.get("event") == "progress" for e in events)
    done = [e for e in events if e.get("event") == "done"]
    assert done and json.loads(done[0]["data"])["model"] == "ollama:llama3.2:3b"


async def test_pull_model_reports_ollama_error_payload(unsigned_config, monkeypatch):
    lines = [json.dumps({"error": "no such model"})]
    monkeypatch.setattr(
        models_module.httpx,
        "AsyncClient",
        _FakeAsyncClient(_FakeStreamResponse(200, lines)),
    )

    response = await pull_model(PullRequest(model="nope:1b"), _build_request())
    events = await _collect_events(response)

    assert events[-1]["event"] == "error"
    assert "no such model" in events[-1]["data"]


async def test_pull_model_handles_unreachable_ollama(unsigned_config, monkeypatch):
    monkeypatch.setattr(
        models_module.httpx,
        "AsyncClient",
        _FakeAsyncClient(error=httpx.ConnectError("refused")),
    )

    response = await pull_model(PullRequest(model="llama3.2:3b"), _build_request())
    events = await _collect_events(response)

    assert events[-1]["event"] == "error"
    assert "Could not reach Ollama" in events[-1]["data"]


async def test_pull_model_handles_non_200_status(unsigned_config, monkeypatch):
    monkeypatch.setattr(
        models_module.httpx,
        "AsyncClient",
        _FakeAsyncClient(_FakeStreamResponse(500, [])),
    )

    response = await pull_model(PullRequest(model="llama3.2:3b"), _build_request())
    events = await _collect_events(response)

    assert events[-1]["event"] == "error"
    assert "500" in events[-1]["data"]
