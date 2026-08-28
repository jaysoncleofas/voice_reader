"""Voice cloning backed by Coqui XTTS-v2.

The model is multi-gigabyte and takes a while to load, so it is pulled in lazily
on the first synthesis and then kept in memory. Inference is CPU-bound and
blocking, so it runs in a worker thread to keep the UI responsive, and finished
clips are cached by content hash - re-reading the same sentence is instant.
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# XTTS-v2 ships under the Coqui Public Model License; acknowledging it
# up front stops the loader from blocking on an interactive prompt.
os.environ.setdefault("COQUI_TOS_AGREED", "1")


class SynthesisError(RuntimeError):
    """Raised when speech could not be generated."""


class CloningEngine:
    """Wraps the cloning model with lazy loading and an on-disk clip cache."""

    def __init__(self, model_name: str, language: str, cache_dir: Path, enabled: bool = True) -> None:
        self.model_name = model_name
        self.language = language
        self.cache_dir = cache_dir
        self.enabled = enabled
        self._model = None
        self._lock = asyncio.Lock()
        self._load_error: str | None = None
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _load_model(self):
        """Import and construct the model. Blocking - always call in a thread."""
        from TTS.api import TTS  # imported lazily: heavy, and optional at dev time

        logger.info("Loading cloning model %s ...", self.model_name)
        model = TTS(self.model_name)
        logger.info("Cloning model ready.")
        return model

    async def ensure_loaded(self) -> None:
        if not self.enabled:
            raise SynthesisError("Voice cloning is disabled (VOICE_TTS_ENABLED=false).")
        if self._model is not None:
            return
        async with self._lock:
            if self._model is not None:
                return
            try:
                self._model = await asyncio.to_thread(self._load_model)
                self._load_error = None
            except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
                self._load_error = str(exc)
                logger.exception("Could not load the cloning model")
                raise SynthesisError(f"Could not load the cloning model: {exc}") from exc

    def _cache_path(self, text: str, speaker_wav: Path) -> Path:
        key = hashlib.sha256(
            "\x00".join([self.model_name, self.language, str(speaker_wav), text]).encode()
        ).hexdigest()[:32]
        # Bucketed by voice id (the sample's folder) so deleting a voice can
        # reclaim everything ever rendered for it.
        bucket = self.cache_dir / speaker_wav.parent.name
        bucket.mkdir(parents=True, exist_ok=True)
        return bucket / f"{key}.wav"

    def _synthesize(self, text: str, speaker_wav: Path, destination: Path) -> None:
        """Blocking inference - always call in a thread."""
        self._model.tts_to_file(
            text=text,
            speaker_wav=str(speaker_wav),
            language=self.language,
            file_path=str(destination),
        )

    async def synthesize(self, text: str, speaker_wav: Path) -> Path:
        """Render `text` in the voice of `speaker_wav`, returning a WAV path."""
        text = (text or "").strip()
        if not text:
            raise SynthesisError("There is no text to read.")
        if not speaker_wav.is_file():
            raise SynthesisError("That voice's reference recording is missing.")

        cached = self._cache_path(text, speaker_wav)
        if cached.is_file():
            return cached

        await self.ensure_loaded()
        partial = cached.with_suffix(".partial.wav")
        try:
            await asyncio.to_thread(self._synthesize, text, speaker_wav, partial)
            partial.replace(cached)  # publish atomically so readers never see a partial file
        except Exception as exc:  # noqa: BLE001
            partial.unlink(missing_ok=True)
            if isinstance(exc, SynthesisError):
                raise
            logger.exception("Synthesis failed")
            raise SynthesisError(f"Synthesis failed: {exc}") from exc
        return cached
