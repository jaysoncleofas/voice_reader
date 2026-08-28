"""HTTP endpoints for the voice library and for cloned-voice synthesis."""

import mimetypes
from pathlib import Path

from fastapi import Body, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from nicegui import app as nicegui_app

from app.auth import current_user
from app.config import settings
from app.deps import engine, library
from app.services import AudioError, LibraryError, SynthesisError
from app.services import ratelimit

# Keep uploads sane: a reference clip is seconds of speech, not a podcast.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _suffix_for(upload: UploadFile) -> str:
    if upload.filename and "." in upload.filename:
        return Path(upload.filename).suffix
    return mimetypes.guess_extension(upload.content_type or "") or ".webm"


def _require_user():
    """The signed-in account, or a 401. Every route below is account-scoped."""
    user = current_user()
    if user is None:
        raise HTTPException(401, "Sign in first.")
    return user


def _enforce(verdict) -> None:
    """429 when a limit is exceeded, with the window in the message."""
    if not verdict.allowed:
        raise HTTPException(429, verdict.message)


def register() -> None:
    """Attach the API routes to the NiceGUI FastAPI app."""

    @nicegui_app.get("/api/voices")
    def list_voices() -> dict:
        return {"voices": [v.as_dict() for v in library.list(_require_user().id)]}

    @nicegui_app.post("/api/voices")
    async def create_voice(
        name: str = Form("My voice"),
        file: UploadFile = File(...),
    ) -> dict:
        user = _require_user()
        _enforce(ratelimit.upload(str(user.id)))
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "That recording is too large.")
        try:
            voice = library.add(user.id, name, data, _suffix_for(file))
        except LibraryError as exc:
            raise HTTPException(400, str(exc)) from exc
        except AudioError as exc:
            raise HTTPException(500, str(exc)) from exc
        return voice.as_dict()

    @nicegui_app.get("/api/voices/{voice_id}/sample")
    def voice_sample(voice_id: str) -> FileResponse:
        voice = library.get(_require_user().id, voice_id)
        if not voice:
            raise HTTPException(404, "No such voice.")
        # Private: a reference clip is one account's audio, never shared caches.
        return FileResponse(
            voice.sample_path, media_type="audio/wav",
            headers={"Cache-Control": f"private, max-age={settings.cache_ttl}"},
        )

    @nicegui_app.delete("/api/voices/{voice_id}")
    def delete_voice(voice_id: str) -> dict:
        if not library.delete(_require_user().id, voice_id):
            raise HTTPException(404, "No such voice.")
        return {"deleted": voice_id}

    @nicegui_app.post("/api/speak")
    async def speak(payload: dict = Body(...)) -> FileResponse:
        user = _require_user()
        # Synthesis pins a core for ~10s on a shared box; throttle it hardest.
        _enforce(ratelimit.speak(str(user.id)))
        voice = library.get(user.id, str(payload.get("voice_id", "")))
        if not voice:
            raise HTTPException(404, "No such voice.")
        try:
            clip = await engine.synthesize(
                str(payload.get("text", "")),
                voice.sample_path,
                str(payload.get("language") or "") or None,
            )
        except SynthesisError as exc:
            raise HTTPException(503, str(exc)) from exc
        # Content-addressed by text+voice+language, so it never goes stale.
        return FileResponse(
            clip, media_type="audio/wav",
            headers={"Cache-Control": f"private, max-age={settings.asset_max_age}, immutable"},
        )

    @nicegui_app.get("/api/tts/status")
    def tts_status() -> dict:
        from app.cache import healthy
        return {
            "enabled": engine.enabled,
            "ready": engine.ready,
            "model": engine.model_name,
            "error": engine.load_error,
            "cache": healthy(),
        }
