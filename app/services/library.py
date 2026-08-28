"""The voice library: recorded samples stored on disk, one folder per voice.

Layout under the data directory::

    voices/
      <voice-id>/
        meta.json     name, creation time, sample length
        sample.wav    normalised reference clip used for cloning
        source.<ext>  the untouched browser recording

Audio lives on the filesystem rather than in a database: the files are large,
always read whole, and handed straight to ffmpeg and the model by path.
"""

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.audio import duration_seconds, to_wav

META_NAME = "meta.json"
SAMPLE_NAME = "sample.wav"


class LibraryError(RuntimeError):
    """Raised when a recording cannot be stored."""


@dataclass(frozen=True)
class StoredVoice:
    id: str
    name: str
    created_at: str
    duration: float
    directory: Path

    @property
    def sample_path(self) -> Path:
        return self.directory / SAMPLE_NAME

    @property
    def label(self) -> str:
        """How this voice appears in the dropdown."""
        # Not "(my voice)": the default name is already "My voice", which would
        # read "My voice (my voice)".
        return f"{self.name} (cloned)"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "created_at": self.created_at,
            "duration": round(self.duration, 1),
        }


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "voice"


class VoiceLibrary:
    """Filesystem-backed collection of recorded reference voices."""

    def __init__(self, root: Path, sample_rate: int, min_seconds: float,
                 max_seconds: float, cache_root: Path | None = None) -> None:
        self.root = root
        self.cache_root = cache_root
        self.sample_rate = sample_rate
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[StoredVoice]:
        voices = [v for d in sorted(self.root.iterdir()) if d.is_dir() for v in (self._load(d),) if v]
        return sorted(voices, key=lambda v: v.created_at)

    def get(self, voice_id: str) -> StoredVoice | None:
        directory = self.root / voice_id
        return self._load(directory) if directory.is_dir() else None

    def by_label(self, label: str) -> StoredVoice | None:
        return next((v for v in self.list() if v.label == label), None)

    def add(self, name: str, data: bytes, suffix: str = ".webm") -> StoredVoice:
        """Store a raw browser recording and its normalised reference clip."""
        name = (name or "").strip() or "My voice"
        if not data:
            raise LibraryError("The recording is empty.")

        voice_id = f"{_slug(name)}-{uuid.uuid4().hex[:6]}"
        directory = self.root / voice_id
        directory.mkdir(parents=True, exist_ok=True)

        try:
            source = directory / f"source{suffix}"
            source.write_bytes(data)
            to_wav(source, directory / SAMPLE_NAME, self.sample_rate)

            seconds = duration_seconds(directory / SAMPLE_NAME)
            if seconds < self.min_seconds:
                raise LibraryError(
                    f"That clip is only {seconds:.1f}s long - record at least "
                    f"{self.min_seconds:.0f}s so the model has enough to work with."
                )
            if seconds > self.max_seconds:
                raise LibraryError(
                    f"That clip is {seconds:.0f}s long - keep it under "
                    f"{self.max_seconds:.0f}s for the best results."
                )

            voice = StoredVoice(
                id=voice_id,
                name=name,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                duration=seconds,
                directory=directory,
            )
            self._write_meta(voice)
            return voice
        except Exception:
            # Never leave a half-written voice behind.
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def delete(self, voice_id: str) -> bool:
        directory = self.root / voice_id
        if not directory.is_dir():
            return False
        shutil.rmtree(directory, ignore_errors=True)
        if self.cache_root:
            # Otherwise every clip ever rendered for this voice leaks.
            shutil.rmtree(self.cache_root / voice_id, ignore_errors=True)
        return True

    def _write_meta(self, voice: StoredVoice) -> None:
        (voice.directory / META_NAME).write_text(
            json.dumps(
                {"id": voice.id, "name": voice.name,
                 "created_at": voice.created_at, "duration": voice.duration},
                indent=2,
            )
        )

    def _load(self, directory: Path) -> StoredVoice | None:
        meta_file = directory / META_NAME
        if not meta_file.is_file() or not (directory / SAMPLE_NAME).is_file():
            return None
        try:
            meta = json.loads(meta_file.read_text())
        except json.JSONDecodeError:
            return None
        return StoredVoice(
            id=meta.get("id", directory.name),
            name=meta.get("name", directory.name),
            created_at=meta.get("created_at", ""),
            duration=float(meta.get("duration", 0.0)),
            directory=directory,
        )
