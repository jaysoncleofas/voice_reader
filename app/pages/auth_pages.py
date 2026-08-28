"""Sign in and register."""

from nicegui import ui

from app.auth import current_user, sign_in, sign_out
from app.config import settings
from app.services.users import AuthError, authenticate, register


def _card(title: str, subtitle: str):
    """A centred Catalyst panel, used by both forms."""
    ui.add_head_html(f'<link rel="stylesheet" href="{settings.static_url}/css/styles.css">')
    outer = ui.element("div").classes(
        "w-full min-h-screen flex items-center justify-center p-6")
    with outer:
        card = ui.element("div").classes("panel w-full max-w-sm p-8 flex flex-col gap-5")
        with card:
            with ui.element("div").classes("flex flex-col gap-1"):
                ui.label(title).classes("page-title")
                ui.label(subtitle).classes("page-sub")
    return card


def register_pages() -> None:
    """Register the /login and /register routes."""

    @ui.page("/login")
    def login_page() -> None:
        if current_user():
            ui.navigate.to("/")
            return

        with _card("Sign in", f"Welcome back to {settings.title}."):
            with ui.element("div").classes("field"):
                ui.label("Email").classes("field-label")
                email = ui.input().props("outlined dense autofocus").classes("w-full")
            with ui.element("div").classes("field"):
                ui.label("Password").classes("field-label")
                password = ui.input(password=True).props("outlined dense").classes("w-full")

            error = ui.label("").classes("text-sm").style("color:var(--danger)")
            submit = ui.button("Sign in").props("unelevated no-caps").classes("btn-solid w-full")

            with ui.row().classes("w-full justify-center gap-1"):
                ui.label("No account?").classes("text-sm").style("color:var(--faint)")
                ui.link("Create one", "/register").classes("text-sm font-medium")

            def attempt() -> None:
                try:
                    sign_in(authenticate(email.value, password.value))
                except AuthError as exc:
                    error.text = str(exc)
                    return
                ui.navigate.to("/")

            submit.on_click(attempt)
            password.on("keydown.enter", attempt)
            email.on("keydown.enter", attempt)

    @ui.page("/register")
    def register_page() -> None:
        if current_user():
            ui.navigate.to("/")
            return

        with _card("Create account", "Your recorded voices stay private to your account."):
            with ui.element("div").classes("field"):
                ui.label("Email").classes("field-label")
                email = ui.input().props("outlined dense autofocus").classes("w-full")
            with ui.element("div").classes("field"):
                ui.label("Password").classes("field-label")
                password = ui.input(password=True).props("outlined dense").classes("w-full")
                ui.label("At least 8 characters.").classes("field-hint")

            error = ui.label("").classes("text-sm").style("color:var(--danger)")
            submit = ui.button("Create account").props("unelevated no-caps").classes("btn-solid w-full")

            with ui.row().classes("w-full justify-center gap-1"):
                ui.label("Already have one?").classes("text-sm").style("color:var(--faint)")
                ui.link("Sign in", "/login").classes("text-sm font-medium")

            def attempt() -> None:
                try:
                    sign_in(register(email.value, password.value))
                except AuthError as exc:
                    error.text = str(exc)
                    return
                ui.navigate.to("/")

            submit.on_click(attempt)
            password.on("keydown.enter", attempt)

    @ui.page("/logout")
    def logout_page() -> None:
        sign_out()
        ui.navigate.to("/login")
