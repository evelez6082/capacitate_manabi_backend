from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from app.config import get_settings
from app.db import fetch_one, get_connection

TOKEN_ALGORITHM = "HS256"
PASSWORD_ITERATIONS = 260_000
bearer_scheme = HTTPBearer(auto_error=False)


def _b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_text),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def create_access_token(subject: str, roles: list[str]) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_token_expire_minutes)).timestamp()),
    }
    header = {"alg": TOKEN_ALGORITHM, "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        signing_input = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            settings.auth_secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64encode(expected_signature), signature_part):
            raise ValueError("invalid signature")
        payload = json.loads(_b64decode(payload_part))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired token")
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida o expirada",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn: Connection = Depends(get_connection),
) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    payload = decode_access_token(credentials.credentials)
    user = fetch_one(
        conn,
        """
        SELECT
            u.id,
            u.email,
            u.nombre_visible,
            u.estado,
            COALESCE(array_agg(r.codigo ORDER BY r.codigo) FILTER (WHERE r.codigo IS NOT NULL), '{}') AS roles
        FROM usuarios u
        LEFT JOIN usuario_roles ur ON ur.usuario_id = u.id
        LEFT JOIN roles r ON r.id = ur.rol_id
        WHERE u.id = %s
        GROUP BY u.id
        """,
        (int(payload["sub"]),),
    )
    if not user or user["estado"] != "activo":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o no encontrado")
    return user


def require_roles(*allowed_roles: str):
    def dependency(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_roles = set(current_user.get("roles") or [])
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta accion")
        return current_user

    return dependency
