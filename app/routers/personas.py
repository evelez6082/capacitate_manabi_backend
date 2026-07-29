from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from app.db import fetch_all, fetch_one, get_connection

router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("")
def buscar_personas(
    q: str | None = Query(default=None, description="Cedula, nombre, correo o telefono"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    if q:
        pattern = f"%{q}%"
        rows = fetch_all(
            conn,
            """
            SELECT id, cedula, nombre_completo, correo_principal, telefono_principal, created_at
            FROM personas
            WHERE cedula ILIKE %s
               OR nombre_completo ILIKE %s
               OR correo_principal ILIKE %s
               OR telefono_principal ILIKE %s
            ORDER BY nombre_completo NULLS LAST, id
            LIMIT %s OFFSET %s
            """,
            (pattern, pattern, pattern, pattern, limit, offset),
        )
    else:
        rows = fetch_all(
            conn,
            """
            SELECT id, cedula, nombre_completo, correo_principal, telefono_principal, created_at
            FROM personas
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
    return {"items": rows, "limit": limit, "offset": offset}


@router.get("/{cedula}")
def obtener_persona(cedula: str, conn: Connection = Depends(get_connection)) -> dict:
    row = fetch_one(
        conn,
        """
        SELECT
            p.*,
            n.nombre AS nacionalidad,
            pr.nombre AS provincia,
            ca.nombre AS canton,
            pa.nombre AS parroquia
        FROM personas p
        LEFT JOIN nacionalidades n ON n.id = p.nacionalidad_id
        LEFT JOIN provincias pr ON pr.id = p.provincia_id
        LEFT JOIN cantones ca ON ca.id = p.canton_id
        LEFT JOIN parroquias pa ON pa.id = p.parroquia_id
        WHERE p.cedula = %s
        """,
        (cedula,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return row


@router.get("/{cedula}/trazabilidad")
def trazabilidad_persona(cedula: str, conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT *
        FROM vw_trazabilidad_participante
        WHERE cedula = %s
        ORDER BY fecha_inscripcion NULLS LAST
        """,
        (cedula,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No hay trazabilidad para esta cedula")
    return {"items": rows}


@router.get("/{cedula}/estado")
def estado_estudiante(cedula: str, conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT *
        FROM vw_estudiante_estado_general
        WHERE cedula = %s
        """,
        (cedula,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No hay estado consolidado para esta cedula")
    return {"items": rows}
