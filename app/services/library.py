"""The voice library: metadata in Postgres, audio on the filesystem.

Audio files are large and always read whole, so they stay on disk and are handed
to ffmpeg and the model by path. Postgres holds only what needs querying -
which account a voice belongs to, its name, length, and creation time.

    voices/<voice-id>/
      sample.wav    normalised reference clip used for cloning
      source.<ext>  the untouched browser recording

Every method takes a user_id and filters on it, so one account can never read
or delete another's voices.
"""

import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.db import cursor
from app.services.audio import duration_seconds, to_wav

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


def _iso(value) -> str:
    return value.isoformat(timespec="seconds") if isinstance(value, datetime) else str(value or "")


class VoiceLibrary:
    """Per-account collection of recorded reference voices."""

    def __init__(self, root: Path, sample_rate: int, min_seconds: float,
                 max_seconds: float, cache_root: Path | None = None) -> None:
        self.root = root
        self.cache_root = cache_root
        self.sample_rate = sample_rate
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def _voice(self, row) -> StoredVoice:
        return StoredVoice(
            id=row[0], name=row[1], duration=float(row[2] or 0),
            created_at=_iso(row[3]), directory=self.root / row[0],
        )

    def list(self, user_id: int) -> list[StoredVoice]:
        with cursor() as cur:
            cur.execute(
                "SELECT id, name, duration, created_at FROM voices "
                "WHERE user_id = %s ORDER BY created_at",
                (user_id,),
            )
            return [self._voice(row) for row in cur.fetchall()]

    def get(self, user_id: int, voice_id: str) -> StoredVoice | None:
        with cursor() as cur:
            cur.execute(
                "SELECT id, name, duration, created_at FROM voices "
                "WHERE user_id = %s AND id = %s",
                (user_id, voice_id),
            )
            row = cur.fetchone()
        return self._voice(row) if row else None

    def add(self, user_id: int, name: str, data: bytes, suffix: str = ".webm") -> StoredVoice:
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

            with cursor() as cur:
                cur.execute(
                    "INSERT INTO voices (id, user_id, name, duration) "
                    "VALUES (%s, %s, %s, %s) RETURNING created_at",
                    (voice_id, user_id, name, seconds),
                )
                created = cur.fetchone()[0]
            return StoredVoice(voice_id, name, _iso(created), seconds, directory)
        except Exception:
            # Never leave a half-written voice behind.
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def delete(self, user_id: int, voice_id: str) -> bool:
        with cursor() as cur:
            cur.execute(
                "DELETE FROM voices WHERE user_id = %s AND id = %s RETURNING id",
                (user_id, voice_id),
            )
            if not cur.fetchone():
                return False
        shutil.rmtree(self.root / voice_id, ignore_errors=True)
        if self.cache_root:
            # Otherwise every clip ever rendered for this voice leaks.
            shutil.rmtree(self.cache_root / voice_id, ignore_errors=True)
        return True
