"""Languages the cloning model can speak.

XTTS-v2 ships with a fixed set of 17. Tagalog is not among them, but Tagalog
and Spanish share the same five pure vowels and much of their consonant
inventory, so Spanish is by far the closest approximation - noticeably better
than English, which mangles the vowels.
"""

# Ordered: the two most useful here first, then alphabetical.
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("es", "Spanish - closest to Tagalog"),
    ("ar", "Arabic"),
    ("zh-cn", "Chinese"),
    ("cs", "Czech"),
    ("nl", "Dutch"),
    ("fr", "French"),
    ("de", "German"),
    ("hi", "Hindi"),
    ("hu", "Hungarian"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("tr", "Turkish"),
)

CODES = frozenset(code for code, _ in LANGUAGES)


def options() -> dict[str, str]:
    """Select options: code -> label."""
    return dict(LANGUAGES)


def is_supported(code: str) -> bool:
    return code in CODES
