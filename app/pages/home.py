"""Home: type a sentence and hear it read aloud.

Two engines sit behind one dropdown - the browser's built-in Web Speech voices,
and any voices recorded on the Voices page, which are cloned server-side.
"""

import asyncio
import json
from collections import Counter, defaultdict

from nicegui import ui

from app.config import settings
from app.deps import library
from app.pages.layout import field, page_shell
from app.services import cancel_script, speak_script
from app.services.languages import options as language_options

# Distinguishes browser voice keys from cloned-voice ids in the dropdown.
BROWSER_PREFIX = "browser:"


def register() -> None:
    """Register the home page route."""

    @ui.page("/")
    def home() -> None:
        # The dropdown is keyed by stable ids, not display text: two recordings
        # may share a name, and a text key would make one of them unreachable.
        stored: list = []
        browser_voices: list[str] = []

        with page_shell("/") as user:
            if user is None:
                return
            with ui.element("div").classes("flex flex-col gap-1 mb-6"):
                ui.label("Home").classes("page-title")
                ui.label("Type a sentence, choose a voice, and press Listen.").classes("page-sub")

            with ui.element("div").classes("flex flex-col gap-5"):
                with field("Your text"):
                    text = ui.textarea(
                        placeholder="Type a sentence here...",
                    ).props("outlined rows=4").classes("w-full")

                with ui.row().classes("w-full items-end gap-4 flex-nowrap"):
                    with field("Voice"):
                        voice_select = ui.select([]) \
                            .props("outlined dense options-dense dropdown-icon=unfold_more").classes("w-full")
                    with ui.element("div").classes("field w-52 shrink-0") as language_field:
                        ui.label("Language").classes("field-label")
                        language = ui.select(
                            language_options(), value=settings.tts_language,
                        ).props("outlined dense options-dense dropdown-icon=unfold_more") \
                            .classes("w-full")

                    with ui.column().classes("gap-1 w-44 shrink-0"):
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.label("Speed").classes("text-xs font-medium").style("color:var(--muted)")
                            ui.space()
                            speed_value = ui.label("1.0x").classes("text-xs tabular-nums") \
                                .style("color:var(--faint)")
                        rate = ui.slider(min=0.5, max=2, step=0.1, value=1) \
                            .props("dense").classes("w-full")
                        speed_value.bind_text_from(rate, "value", lambda v: f"{v:.1f}x")

                ui.element("div").classes("hairline")

                with ui.row().classes("w-full items-center gap-3"):
                    listen_btn = ui.button("Listen", icon="volume_up") \
                        .props("unelevated no-caps").classes("btn-solid")
                    stop_btn = ui.button("Stop", icon="stop") \
                        .props("flat no-caps").classes("btn-outline")
                    ui.space()
                    status = ui.label("").classes("text-xs text-right").style("color:var(--faint)")

        def build_options() -> dict[str, str]:
            """Map option key -> display text. Cloned voices key on their id."""
            counts = Counter(voice.name for voice in stored)
            seen: dict[str, int] = defaultdict(int)
            options: dict[str, str] = {}
            for voice in stored:
                seen[voice.name] += 1
                # Number them only when a name is actually reused.
                shown = f"{voice.name} {seen[voice.name]}" if counts[voice.name] > 1 else voice.name
                options[voice.id] = f"{shown} (cloned)"
            options.update({BROWSER_PREFIX + name: name for name in browser_voices})
            return options

        def sync_language_visibility() -> None:
            """Browser voices carry their own language, so the picker is for clones."""
            selected = voice_select.value or ""
            language_field.set_visibility(
                bool(selected) and not selected.startswith(BROWSER_PREFIX))

        def refresh_select(keep: str | None = None) -> None:
            available = build_options()
            voice_select.options = available
            if keep and keep in available:
                voice_select.value = keep
            elif voice_select.value not in available:
                voice_select.value = next(iter(available), None)
            voice_select.update()
            sync_language_visibility()

        async def load_voices() -> None:
            await ui.context.client.connected()
            stored.clear()
            stored.extend(library.list(user.id))
            refresh_select()

            # Chrome populates the voice list asynchronously, so poll a few times.
            names: list[str] = []
            for _ in range(settings.voice_poll_attempts):
                try:
                    names = await ui.run_javascript("window.__voiceList()", timeout=5.0) or []
                except Exception:
                    names = []
                if names:
                    break
                await asyncio.sleep(settings.voice_poll_interval)

            browser_voices.clear()
            browser_voices.extend(names)
            refresh_select(voice_select.value)

            if stored:
                status.text = f"{len(stored)} recorded, {len(names)} browser voices."
            elif names:
                status.text = f"{len(names)} browser voices available."
            else:
                status.text = "No voices reported by this browser."

        async def speak() -> None:
            sentence = (text.value or "").strip()
            if not sentence:
                ui.notify("Please type something first.", type="warning")
                return

            selected = voice_select.value or ""
            if selected and not selected.startswith(BROWSER_PREFIX):
                status.text = "Generating speech in your voice - this can take a while..."
                result = await ui.run_javascript(
                    f"return await window.__speakCloned("
                    f"{json.dumps(selected)}, {json.dumps(sentence)}, {float(rate.value)}, "
                    f"{json.dumps(language.value or settings.tts_language)});",
                    timeout=600.0,
                )
                if not (result or {}).get("ok"):
                    message = (result or {}).get("error", "Synthesis failed.")
                    status.text = message
                    ui.notify(message, type="negative")
                    return
                status.text = "Speaking in your voice..."
                return

            browser_voice = selected[len(BROWSER_PREFIX):] if selected else ""
            await ui.run_javascript(speak_script(sentence, browser_voice, rate.value))
            status.text = "Speaking..."

        async def stop() -> None:
            await ui.run_javascript(cancel_script())
            status.text = "Stopped."

        voice_select.on_value_change(lambda _: sync_language_visibility())
        listen_btn.on_click(speak)
        stop_btn.on_click(stop)
        ui.timer(0.1, load_voices, once=True)
