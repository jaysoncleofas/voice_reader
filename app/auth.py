"""Session helpers shared by the pages and the HTTP API."""

from nicegui import app

from app.services.users import User, get as get_user

SESSION_KEY = "user_id"


def current_user() -> User | None:
    """The signed-in user for this request, or None."""
    try:
        user_id = app.storage.user.get(SESSION_KEY)
    except Exception:
        # No session middleware in this context (e.g. a bare API call).
        return None
    return get_user(int(user_id)) if user_id else None


def sign_in(user: User) -> None:
    app.storage.user[SESSION_KEY] = user.id


def sign_out() -> None:
    app.storage.user.pop(SESSION_KEY, None)
