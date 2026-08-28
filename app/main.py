"""Entry point: wire up static files, API routes, pages, and start the server."""

import logging

from nicegui import app as nicegui_app
from nicegui import ui

from app.api import register_api
from app.config import settings
from app.db import init_schema
from app.pages import register_auth, register_home, register_voices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings.data_dir.mkdir(parents=True, exist_ok=True)
nicegui_app.add_static_files(settings.static_url, str(settings.static_dir))
init_schema()
register_api()
register_auth()
register_home()
register_voices()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=settings.host,
        port=settings.port,
        title=settings.title,
        dark=settings.dark,
        reload=settings.reload,
        show=False,
        storage_secret=settings.storage_secret,
    )
