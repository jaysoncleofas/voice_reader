"""Audio helpers built on ffmpeg.

Browsers hand us whatever MediaRecorder produced (usually WebM/Opus), while the
cloning model wants plain mono PCM, so every upload is normalised on arrival.
"""

import json
import shutil
import subprocess
from pathlib import Path


class AudioError(RuntimeError):
    """Raised when ffmpeg is missing or cannot process a recording."""


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise AudioError(f"{name} is not installed in this environment")
    return path


def to_wav(source: Path, destination: Path, sample_rate: int) -> None:
    """Transcode `source` into mono 16-bit PCM WAV at `sample_rate`."""
    result = subprocess.run(
        [
            _tool("ffmpeg"), "-y",
            "-i", str(source),
            "-ac", "1",
            "-ar", str(sample_rate),
            "-c:a", "pcm_s16le",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-3:]
        raise AudioError("ffmpeg failed to convert the recording: " + " ".join(tail))


def duration_seconds(path: Path) -> float:
    """Length of an audio file in seconds, or 0.0 if it cannot be determined."""
    result = subprocess.run(
        [
            _tool("ffprobe"), "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0
