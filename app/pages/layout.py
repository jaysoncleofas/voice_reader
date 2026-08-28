"""The application shell: a tinted sidebar beside a white content panel."""

from contextlib import contextmanager

from nicegui import ui

from app.config import settings
from app.deps import engine, library


def _asset(path: str) -> str:
    """Static URL stamped with the file's mtime, to defeat browser caching."""
    file = settings.static_dir / path
    stamp = int(file.stat().st_mtime) if file.exists() else 0
    return f"{settings.static_url}/{path}?v={stamp}"

NAV = (
    ("/", "Home", "home"),
    ("/voices", "Voices", "graphic_eq"),
)


def _head() -> None:
    ui.add_head_html(f'<link rel="stylesheet" href="{_asset("css/styles.css")}">')
    ui.add_body_html(f'<script src="{_asset("js/voices.js")}"></script>')
    ui.add_body_html(f'<script src="{_asset("js/recorder.js")}"></script>')


def _sidebar(active: str) -> None:
    with ui.element("div").classes("sidebar"):
        with ui.element("div").classes("brand"):
            ui.icon("graphic_eq").classes("text-xl")
            ui.label(settings.title)

        for path, label, icon in NAV:
            classes = "nav-item active" if path == active else "nav-item"
            with ui.link(target=path).classes(classes):
                ui.icon(icon).classes("text-lg")
                ui.label(label)

        # Mirrors Catalyst's "Upcoming Events" list: a peek at the collection.
        voices = library.list()
        if voices:
            ui.label("Saved voices").classes("nav-section")
            for voice in voices[:6]:
                with ui.link(target="/voices").classes("nav-item"):
                    ui.label(voice.name).classes("truncate")

        with ui.element("div").classes("sidebar-foot"):
            state = "ready" if engine.ready else ("disabled" if not engine.enabled else "loads on first use")
            ui.label("Voice cloning")
            ui.label(state).classes("text-xs")


@contextmanager
def field(label: str):
    """A Catalyst field: a plain label stacked above its control."""
    with ui.element("div").classes("field"):
        ui.label(label).classes("field-label")
        yield


@contextmanager
def page_shell(active: str):
    """Render the sidebar and open the main content panel."""
    _head()
    with ui.element("div").classes("shell"):
        _sidebar(active)
        with ui.element("div").classes("main"):
            with ui.element("div").classes("main-inner"):
                yield
