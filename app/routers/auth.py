from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection
from pydantic import BaseModel, Field

from app.db import fetch_one, get_connection
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=6)


@router.post("/login")
def login(payload: LoginRequest, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    user = fetch_one(
        conn,
        """
        SELECT
            u.id,
            u.email,
            u.password_hash,
            u.nombre_visible,
            u.estado,
            COALESCE(array_agg(r.codigo ORDER BY r.codigo) FILTER (WHERE r.codigo IS NOT NULL), '{}') AS roles
        FROM usuarios u
        LEFT JOIN usuario_roles ur ON ur.usuario_id = u.id
        LEFT JOIN roles r ON r.id = ur.rol_id
        WHERE lower(u.email) = lower(%s)
        GROUP BY u.id
        """,
        (payload.email,),
    )
    if not user or user["estado"] != "activo" or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")

    conn.execute("UPDATE usuarios SET ultimo_login_at = now(), updated_at = now() WHERE id = %s", (user["id"],))
    conn.commit()
    roles = list(user.get("roles") or [])
    return {
        "access_token": create_access_token(str(user["id"]), roles),
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "nombre_visible": user["nombre_visible"],
            "roles": roles,
        },
    }


@router.get("/me")
def me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": current_user}
