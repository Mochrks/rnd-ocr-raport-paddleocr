import re

from app.utils.normalizer import normalize_text, normalize_text_safe  # noqa: F401


def clean_value(value: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    value = value.lstrip(".:")
    value = value.rstrip(".:")
    value = re.sub(r"\s+", " ", value)
    return value if value else None