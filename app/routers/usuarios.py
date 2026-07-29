from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import fetch_all, get_connection

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


@router.get("/roles")
def listar_roles(conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(conn, "SELECT id, codigo, nombre, descripcion FROM roles ORDER BY id")
    return {"items": rows}


@router.get("")
def listar_usuarios(conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT
            u.id,
            u.email,
            u.nombre_visible,
            u.estado,
            p.cedula,
            p.nombre_completo,
            string_agg(r.codigo, ', ' ORDER BY r.codigo) AS roles
        FROM usuarios u
        LEFT JOIN personas p ON p.id = u.persona_id
        LEFT JOIN usuario_roles ur ON ur.usuario_id = u.id
        LEFT JOIN roles r ON r.id = ur.rol_id
        GROUP BY u.id, p.cedula, p.nombre_completo
        ORDER BY u.created_at DESC
        """
    )
    return {"items": rows}
