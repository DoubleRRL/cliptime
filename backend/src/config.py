from dotenv import load_dotenv
import os

load_dotenv()

_config_override = None


class Config:
    def __init__(self):
        self.openai_api_key = self._get_optional_env("OPENAI_API_KEY")
        self.anthropic_api_key = self._get_optional_env("ANTHROPIC_API_KEY")
        self.google_api_key = self._get_optional_env("GOOGLE_API_KEY")
        self.ollama_base_url = self._get_optional_env("OLLAMA_BASE_URL")
        self.ollama_api_key = self._get_optional_env("OLLAMA_API_KEY")

        self.llm = self._get_optional_env("LLM") or self._infer_default_llm()
        self.assembly_ai_api_key = os.getenv("ASSEMBLY_AI_API_KEY")

        self.max_video_duration = int(os.getenv("MAX_VIDEO_DURATION", "5400"))
        self.output_dir = os.getenv("OUTPUT_DIR", "outputs")

        self.max_clips = int(os.getenv("MAX_CLIPS", "10"))
        self.clip_duration = int(os.getenv("CLIP_DURATION", "30"))  # seconds

        self.temp_dir = os.getenv("TEMP_DIR", "temp")
        self.storage_host_path = self._get_optional_env("STORAGE_HOST_PATH")

        # Redis configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = self._get_optional_env("REDIS_PASSWORD")

        # Fail-safe: queued tasks should not stay queued forever
        self.queued_task_timeout_seconds = int(
            os.getenv("QUEUED_TASK_TIMEOUT_SECONDS", "180")
        )
        self.processing_task_timeout_seconds = int(
            os.getenv("PROCESSING_TASK_TIMEOUT_SECONDS", "14400")
        )
        self.worker_max_jobs = int(os.getenv("WORKER_MAX_JOBS", "1"))
        self.worker_job_timeout_seconds = int(
            os.getenv("WORKER_JOB_TIMEOUT_SECONDS", "21600")
        )

        self.backend_auth_secret = self._get_optional_env("BACKEND_AUTH_SECRET")
        # Signed-header auth is an optional hardening layer: enabled whenever a
        # shared secret is configured (frontend signs with the same secret).
        self.require_signed_auth = self.backend_auth_secret is not None
        self.auth_signature_ttl_seconds = int(
            os.getenv("AUTH_SIGNATURE_TTL_SECONDS", "300")
        )
        self.cors_origins = self._get_csv_env(
            "CORS_ORIGINS",
            [
                "http://localhost:3000",
                "http://sp.localhost:3000",
            ],
        )
        self.app_base_url = (
            self._get_optional_env("NEXT_PUBLIC_APP_URL") or "http://localhost:3000"
        ).rstrip("/")
        self.discord_feedback_webhook_url = self._get_optional_env("DISCORD_FEEDBACK_WEBHOOK_URL")
        self.default_processing_mode = os.getenv("DEFAULT_PROCESSING_MODE", "quality")
        self.fast_mode_max_clips = int(os.getenv("FAST_MODE_MAX_CLIPS", "4"))
        self.balanced_mode_max_clips = int(os.getenv("BALANCED_MODE_MAX_CLIPS", "7"))
        self.quality_mode_max_clips = int(os.getenv("QUALITY_MODE_MAX_CLIPS", "14"))
        self.quality_mode_max_micro = int(os.getenv("QUALITY_MODE_MAX_MICRO", "8"))
        self.quality_mode_max_deep = int(os.getenv("QUALITY_MODE_MAX_DEEP", "6"))
        self.fast_mode_transcript_model = os.getenv(
            "FAST_MODE_TRANSCRIPT_MODEL", "nano"
        )
        self.default_caption_template = os.getenv(
            "DEFAULT_CAPTION_TEMPLATE", "riverside"
        )
        self.transcript_window_seconds = int(
            os.getenv("TRANSCRIPT_WINDOW_SECONDS", "300")
        )
        self.transcript_window_overlap = int(
            os.getenv("TRANSCRIPT_WINDOW_OVERLAP", "30")
        )
        self.analysis_max_windows = int(os.getenv("ANALYSIS_MAX_WINDOWS", "12"))
        self.local_llm_concurrency = int(os.getenv("LOCAL_LLM_CONCURRENCY", "1"))
        self.micro_per_window = int(os.getenv("MICRO_PER_WINDOW", "3"))
        self.deep_per_window = int(os.getenv("DEEP_PER_WINDOW", "2"))
        self.ollama_num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
        self.signal_first_analysis = self._get_bool_env("SIGNAL_FIRST_ANALYSIS", False)
        self.assemblyai_sentiment_entities = self._get_bool_env(
            "ASSEMBLYAI_SENTIMENT_ENTITIES", False
        )
        self.signal_patch_pad_seconds = int(os.getenv("SIGNAL_PATCH_PAD_SECONDS", "45"))
        self.signal_patch_max_chars = int(os.getenv("SIGNAL_PATCH_MAX_CHARS", "1500"))
        # Number of clips rendered concurrently per task
        self.parallel_clip_renders = max(
            1, int(os.getenv("PARALLEL_CLIP_RENDERS", "2"))
        )
        # Host machine RAM for model recommendations when Ollama /api/info is unavailable
        # (common in Docker, where psutil reports container memory instead).
        host_ram = self._get_optional_env("HOST_TOTAL_RAM_GB")
        self.host_total_ram_gb = float(host_ram) if host_ram else None

    @staticmethod
    def _get_optional_env(name: str):
        value = os.getenv(name)
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _get_bool_env(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def _get_csv_env(name: str, default: list[str]) -> list[str]:
        value = os.getenv(name)
        if not value:
            return default
        return [item.strip() for item in value.split(",") if item.strip()]

    def _infer_default_llm(self) -> str:
        """
        Infer a usable default model based on whichever API key is present.
        Falls back to Google for backward compatibility.
        """
        if self.google_api_key:
            return "google-gla:gemini-3-flash-preview"
        if self.openai_api_key:
            return "openai:gpt-5.2"
        if self.anthropic_api_key:
            return "anthropic:claude-4-sonnet"
        return "google-gla:gemini-3-flash-preview"


def get_config() -> Config:
    override = _config_override
    if override is not None:
        return override
    return Config()


def set_config_override(config: Config | None) -> None:
    global _config_override
    _config_override = config
