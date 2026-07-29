from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.db import fetch_all, get_connection

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def limited_view(conn: Connection, view_name: str, limit: int, offset: int) -> dict:
    rows = fetch_all(
        conn,
        f"SELECT * FROM {view_name} LIMIT %s OFFSET %s",
        (limit, offset),
    )
    return {"items": rows, "limit": limit, "offset": offset}


@router.get("/aprobados-sin-diploma")
def aprobados_sin_diploma(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    return limited_view(conn, "vw_aprobados_sin_diploma", limit, offset)


@router.get("/aprobados-sin-solicitud-diploma")
def aprobados_sin_solicitud_diploma(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    return limited_view(conn, "vw_aprobados_sin_solicitud_diploma", limit, offset)


@router.get("/aprobados-solicitados-sin-diploma")
def aprobados_solicitados_sin_diploma(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    return limited_view(conn, "vw_aprobados_solicitados_sin_diploma", limit, offset)


@router.get("/inscritos-sin-aprobar")
def inscritos_sin_aprobar(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    return limited_view(conn, "vw_inscritos_sin_aprobar", limit, offset)


@router.get("/estudiantes-para-seguimiento")
def estudiantes_para_seguimiento(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    return limited_view(conn, "vw_estudiantes_para_seguimiento", limit, offset)


@router.get("/personas-multiples-versiones")
def personas_multiples_versiones(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    return limited_view(conn, "vw_personas_multiples_versiones_inscripcion", limit, offset)
