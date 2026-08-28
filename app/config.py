"""Application settings, overridable through environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DATA_DIR = BASE_DIR.parent / "data"


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    title: str = os.getenv("VOICE_TITLE", "Voice Reader")
    host: str = os.getenv("VOICE_HOST", "0.0.0.0")
    port: int = int(os.getenv("VOICE_PORT", "8080"))
    dark: bool = _flag("VOICE_DARK", "false")
    reload: bool = _flag("VOICE_RELOAD", "false")

    # Chrome fills the browser voice list asynchronously, so the page polls for it.
    voice_poll_attempts: int = 10
    voice_poll_interval: float = 0.3

    static_url: str = "/assets"
    static_dir: Path = STATIC_DIR

    # Where recorded voice samples live. Mounted as a Docker volume so the
    # library survives image rebuilds.
    data_dir: Path = Path(os.getenv("VOICE_DATA_DIR", str(DEFAULT_DATA_DIR)))

    # Reference clips are normalised to this shape before cloning.
    sample_rate: int = 24_000

    # A usable cloning reference needs a few seconds of clean speech.
    min_sample_seconds: float = 4.0
    max_sample_seconds: float = 40.0

    # Voice cloning model. Loaded lazily on first synthesis, then cached.
    tts_model: str = os.getenv("VOICE_TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    tts_language: str = os.getenv("VOICE_TTS_LANGUAGE", "en")
    tts_enabled: bool = _flag("VOICE_TTS_ENABLED", "true")

    @property
    def voices_dir(self) -> Path:
        return self.data_dir / "voices"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"


settings = Settings()
