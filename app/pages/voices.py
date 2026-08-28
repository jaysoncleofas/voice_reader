"""Voices: the saved voice library, shown as a table with a create dialog."""

import json
import time
from datetime import datetime

from nicegui import ui

from app.deps import library
from app.pages.layout import field, page_shell
from app.services.prompts import passage_at

DIALOG_DESC = (
    "Record a sample of your voice and it becomes available on the Home page. "
    "Read the passage below in your normal speaking voice, all the way to the end."
)


def _created(value: str) -> str:
    """ISO timestamp -> 'Aug 28, 2026'."""
    try:
        return datetime.fromisoformat(value).strftime("%b %-d, %Y")
    except (TypeError, ValueError):
        return "-"


def register() -> None:
    """Register the voices page route."""

    @ui.page("/voices")
    def voices_page() -> None:
        recording = {"active": False}
        playing: dict = {"id": None}
        passage = {"index": 0}
        started = {"at": 0.0}

        with page_shell("/voices"):
            with ui.row().classes("w-full items-center justify-between mb-6 gap-4"):
                ui.label("Voices").classes("page-title")
                create_btn = ui.button("Create voice", icon="add") \
                    .props("unelevated no-caps").classes("btn-solid")

            @ui.refreshable
            def voice_table() -> None:
                voices = library.list()
                if not voices:
                    with ui.element("div").classes("empty-state"):
                        ui.label("No voices yet.")
                        ui.label("Record one to hear your own text read back to you.") \
                            .classes("text-xs mt-1")
                    return

                with ui.element("div").classes("tbl"):
                    with ui.element("div").classes("tbl-head"):
                        ui.label("Name").classes("col-name")
                        ui.label("Created").classes("col-date")
                        ui.label("Length").classes("col-len")
                        ui.element("div").classes("col-act").style("width:5.5rem")
                    for voice in voices:
                        with ui.element("div").classes("tbl-row"):
                            with ui.element("div").classes("col-name flex items-center gap-3"):
                                ui.label(voice.name).classes("truncate")
                                ui.label("cloned").classes("badge badge-ok")
                            ui.label(_created(voice.created_at)).classes("col-date")
                            ui.label(f"{voice.duration:.0f}s").classes("col-len")
                            with ui.element("div").classes("col-act"):
                                is_playing = playing["id"] == voice.id
                                ui.button(icon="stop" if is_playing else "play_arrow",
                                          on_click=lambda _, v=voice: preview(v.id)) \
                                    .props("flat dense round") \
                                    .classes("btn-ghost playing" if is_playing else "btn-ghost")
                                ui.button(icon="delete",
                                          on_click=lambda _, v=voice: confirm_delete(v)) \
                                    .props("flat dense round").classes("btn-ghost")

            voice_table()

        # ---- create dialog -------------------------------------------------

        with ui.dialog() as dialog, ui.element("div").classes("dlg flex flex-col gap-4"):
            ui.label("Create voice").classes("dlg-title")
            ui.label(DIALOG_DESC).classes("dlg-desc")

            with field("Name"):
                name_input = ui.input(value="My voice") \
                    .props("outlined dense").classes("w-full")

            with ui.element("div").classes("passage-card flex flex-col gap-2"):
                with ui.row().classes("w-full items-center gap-2"):
                    passage_title = ui.label("").classes("passage-label")
                    ui.space()
                    shuffle_btn = ui.button("Another passage", icon="shuffle") \
                        .props("flat dense no-caps").classes("btn-ghost")
                passage_text = ui.label("").classes("passage-text")

            dialog_status = ui.label("").classes("text-xs").style("color:var(--faint)")

            with ui.row().classes("w-full items-center justify-end gap-2 pt-1"):
                cancel_btn = ui.button("Cancel").props("flat no-caps").classes("btn-outline")
                record_btn = ui.button("Start recording", icon="mic") \
                    .props("unelevated no-caps").classes("btn-solid")

        # ---- delete confirmation ------------------------------------------

        with ui.dialog() as confirm, ui.element("div").classes("dlg flex flex-col gap-4"):
            ui.label("Delete voice").classes("dlg-title")
            confirm_text = ui.label("").classes("dlg-desc")
            with ui.row().classes("w-full items-center justify-end gap-2 pt-1"):
                ui.button("Cancel", on_click=confirm.close).props("flat no-caps").classes("btn-outline")
                delete_btn = ui.button("Delete").props("unelevated no-caps").classes("btn-danger")

        pending: dict = {}

        def confirm_delete(voice) -> None:
            pending["voice"] = voice
            confirm_text.text = (
                f"“{voice.name}” and everything generated with it will be "
                "permanently removed. This cannot be undone."
            )
            confirm.open()

        def do_delete() -> None:
            voice = pending.get("voice")
            confirm.close()
            if voice and library.delete(voice.id):
                voice_table.refresh()
                ui.notify("Voice deleted.")

        async def preview(voice_id: str) -> None:
            """Play a reference clip, or stop it if that row is already sounding."""
            if playing["id"] == voice_id:
                await ui.run_javascript("window.__stopAll();")
                playing["id"] = None
                voice_table.refresh()
                return

            playing["id"] = voice_id
            voice_table.refresh()
            url = f"/api/voices/{voice_id}/sample"
            result = await ui.run_javascript(
                f"return await window.__playUrl({json.dumps(url)});", timeout=600.0)

            # A different row may have taken over while this clip was playing.
            if playing["id"] == voice_id:
                playing["id"] = None
                voice_table.refresh()
            if not (result or {}).get("ok"):
                ui.notify((result or {}).get("error", "Playback failed."), type="negative")

        # ---- passage + recording -------------------------------------------

        def show_passage() -> None:
            current = passage_at(passage["index"])
            passage_title.text = f"Read aloud - about {current.approx_seconds} seconds"
            passage_text.text = current.text

        def next_passage() -> None:
            passage["index"] += 1
            show_passage()

        def tick() -> None:
            dialog_status.text = (
                f"Recording... {time.monotonic() - started['at']:.0f}s - keep reading to the end.")

        elapsed = ui.timer(0.25, tick, active=False)

        def reset_dialog() -> None:
            recording["active"] = False
            elapsed.active = False
            record_btn.text = "Start recording"
            record_btn.props("unelevated no-caps")
            record_btn.classes(remove="btn-danger", add="btn-solid")
            record_btn.update()
            dialog_status.text = ""

        def open_dialog() -> None:
            reset_dialog()
            show_passage()
            dialog.open()

        async def close_dialog() -> None:
            if recording["active"]:
                await ui.run_javascript("return await window.__recStop();", timeout=30.0)
            reset_dialog()
            dialog.close()

        async def toggle_record() -> None:
            if not recording["active"]:
                result = await ui.run_javascript("return await window.__recStart();", timeout=30.0)
                if not (result or {}).get("ok"):
                    dialog_status.text = (result or {}).get("error", "Could not start recording.")
                    return
                recording["active"] = True
                started["at"] = time.monotonic()
                elapsed.active = True
                record_btn.text = "Stop and save"
                record_btn.classes(remove="btn-solid", add="btn-danger")
                record_btn.update()
                return

            recording["active"] = False
            elapsed.active = False
            record_btn.text = "Start recording"
            record_btn.classes(remove="btn-danger", add="btn-solid")
            record_btn.update()

            result = await ui.run_javascript("return await window.__recStop();", timeout=30.0)
            if not (result or {}).get("ok"):
                dialog_status.text = (result or {}).get("error", "Recording failed.")
                return

            dialog_status.text = f"Captured {result.get('seconds', 0):.0f}s - saving..."
            name = (name_input.value or "My voice").strip()
            saved = await ui.run_javascript(
                f"return await window.__recUpload({json.dumps(name)});", timeout=60.0)
            if not (saved or {}).get("ok"):
                dialog_status.text = (saved or {}).get("error", "Could not save the recording.")
                return

            voice = saved.get("voice") or {}
            voice_table.refresh()
            dialog.close()
            reset_dialog()
            ui.notify(f"Saved “{voice.get('name')}”.", type="positive")

        create_btn.on_click(open_dialog)
        cancel_btn.on_click(close_dialog)
        record_btn.on_click(toggle_record)
        shuffle_btn.on_click(next_passage)
        delete_btn.on_click(do_delete)
        show_passage()
