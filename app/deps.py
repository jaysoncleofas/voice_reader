"""Shared, process-wide service instances."""

from app.config import settings
from app.services import CloningEngine, VoiceLibrary

library = VoiceLibrary(
    root=settings.voices_dir,
    sample_rate=settings.sample_rate,
    min_seconds=settings.min_sample_seconds,
    max_seconds=settings.max_sample_seconds,
    cache_root=settings.cache_dir,
)

engine = CloningEngine(
    model_name=settings.tts_model,
    language=settings.tts_language,
    cache_dir=settings.cache_dir,
    enabled=settings.tts_enabled,
)
