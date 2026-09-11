from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
import hashlib
import hmac
import json
import secrets
import time


class InvalidFormChallenge(ValueError):
    pass


def _encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_form_challenge(secret: str, now: int | None = None) -> str:
    payload = {
        "iat": int(time.time() if now is None else now),
        "nonce": secrets.token_urlsafe(24),
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_form_challenge(
    token: str,
    secret: str,
    minimum_age_seconds: int,
    maximum_age_seconds: int,
    now: int | None = None,
) -> dict[str, str | int]:
    try:
        encoded, provided_signature = token.split(".", 1)
        expected_signature = _encode(
            hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise InvalidFormChallenge("Firma inválida")
        payload = json.loads(_decode(encoded))
        issued_at = int(payload["iat"])
        nonce = str(payload["nonce"])
        current_time = int(time.time() if now is None else now)
        age = current_time - issued_at
        if age < minimum_age_seconds:
            raise InvalidFormChallenge("Formulario enviado demasiado rápido")
        if age > maximum_age_seconds or age < 0:
            raise InvalidFormChallenge("Desafío vencido")
        if len(nonce) < 20:
            raise InvalidFormChallenge("Nonce inválido")
        return {"iat": issued_at, "nonce": nonce}
    except InvalidFormChallenge:
        raise
    except Exception as exc:
        raise InvalidFormChallenge("Desafío inválido") from exc


def private_fingerprint(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
