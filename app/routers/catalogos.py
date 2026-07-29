from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import fetch_all, get_connection

router = APIRouter(prefix="/api/catalogos", tags=["catalogos"])


@router.get("/provincias")
def provincias(conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(conn, "SELECT id, nombre FROM provincias WHERE activo = true ORDER BY nombre")
    return {"items": rows}


@router.get("/cantones")
def cantones(provincia_id: int, conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        "SELECT id, nombre FROM cantones WHERE activo = true AND provincia_id = %s ORDER BY nombre",
        (provincia_id,),
    )
    return {"items": rows}


@router.get("/parroquias")
def parroquias(canton_id: int, conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        "SELECT id, nombre FROM parroquias WHERE activo = true AND canton_id = %s ORDER BY nombre",
        (canton_id,),
    )
    return {"items": rows}


@router.get("/nacionalidades")
def nacionalidades(conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(conn, "SELECT id, nombre, codigo FROM nacionalidades WHERE activo = true ORDER BY nombre")
    return {"items": rows}
