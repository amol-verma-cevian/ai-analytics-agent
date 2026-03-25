import os


class Settings:
    PROJECT_NAME: str = "AI Analytics Briefing Agent"
    VERSION: str = "1.0.0"

    # LLM Provider — set LLM_PROVIDER to "openai" or "anthropic"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Anthropic (alternative)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # Redis (for ARQ job queue)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Whisper (for voice-to-text)
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # Thresholds
    ANOMALY_ORDER_DROP_PCT: float = 20.0
    ANOMALY_CANCELLATION_SPIKE_PCT: float = 30.0
    ANOMALY_COMPLAINT_THRESHOLD: int = 8
    CONFIDENCE_FALLBACK_THRESHOLD: float = 1.5  # avg eval score below this = fallback

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
