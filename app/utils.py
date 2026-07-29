import re
import secrets
import unicodedata


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-") or secrets.token_urlsafe(8)


def public_token() -> str:
    return secrets.token_urlsafe(24)
