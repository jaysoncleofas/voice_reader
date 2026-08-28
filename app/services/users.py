"""Accounts: registration, sign-in, and password hashing.

Passwords are hashed with scrypt from the standard library - no extra
dependency, and memory-hard enough to make brute force expensive.
"""

import hashlib
import hmac
import os
import re
from dataclasses import dataclass

from app.db import cursor

# scrypt parameters. n must be a power of two; these are the parameters
# recommended for interactive logins.
_N, _R, _P = 2**14, 8, 1
_SALT_BYTES = 16
_KEY_LEN = 32

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


class AuthError(RuntimeError):
    """Raised when a registration or sign-in attempt is rejected."""


@dataclass(frozen=True)
class User:
    id: int
    email: str


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LEN)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        key = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(key_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    # Constant time: never leak how much of the hash matched.
    return hmac.compare_digest(key.hex(), key_hex)


def _clean_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("That does not look like an email address.")
    return email


def register(email: str, password: str) -> User:
    email = _clean_email(email)
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"Use a password of at least {MIN_PASSWORD} characters.")
    with cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise AuthError("That email is already registered.")
        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (email, hash_password(password)),
        )
        return User(id=cur.fetchone()[0], email=email)


def authenticate(email: str, password: str) -> User:
    email = (email or "").strip().lower()
    with cursor() as cur:
        cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
    # Same message either way, so the form never reveals which emails exist.
    if not row or not verify_password(password or "", row[2]):
        raise AuthError("Wrong email or password.")
    return User(id=row[0], email=row[1])


def get(user_id: int) -> User | None:
    with cursor() as cur:
        cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return User(id=row[0], email=row[1]) if row else None
