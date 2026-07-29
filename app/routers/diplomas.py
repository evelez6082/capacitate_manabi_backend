from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.db import fetch_all, get_connection

router = APIRouter(prefix="/api/diplomas", tags=["diplomas"])


@router.get("")
def buscar_diplomas(
    q: str | None = Query(default=None, description="Cedula, nombre o numero de diploma"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    if q:
        pattern = f"%{q}%"
        rows = fetch_all(
            conn,
            """
            SELECT *
            FROM vw_buscar_diplomas
            WHERE cedula ILIKE %s
               OR nombre_completo ILIKE %s
               OR numero_diploma ILIKE %s
            ORDER BY nombre_completo NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (pattern, pattern, pattern, limit, offset),
        )
    else:
        rows = fetch_all(
            conn,
            """
            SELECT *
            FROM vw_buscar_diplomas
            ORDER BY nombre_completo NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
    return {"items": rows, "limit": limit, "offset": offset}
