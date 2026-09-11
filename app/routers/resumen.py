from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import fetch_one, get_connection
from app.security import require_roles

router = APIRouter(
    prefix="/api",
    tags=["resumen"],
    dependencies=[Depends(require_roles("admin", "supervisor"))],
)


@router.get("/resumen")
def resumen(conn: Connection = Depends(get_connection)) -> dict:
    return {
        "personas": fetch_one(conn, "SELECT count(*) AS total FROM personas")["total"],
        "inscripciones": fetch_one(conn, "SELECT count(*) AS total FROM inscripciones")["total"],
        "aprobaciones": fetch_one(conn, "SELECT count(*) AS total FROM aprobaciones")["total"],
        "solicitudes_diploma": fetch_one(conn, "SELECT count(*) AS total FROM solicitudes_diploma")["total"],
        "diplomas": fetch_one(conn, "SELECT count(*) AS total FROM diplomas")["total"],
        "campanas_inscripcion": fetch_one(conn, "SELECT count(*) AS total FROM campanas_inscripcion")["total"],
        "campanas_avance": fetch_one(conn, "SELECT count(*) AS total FROM campanas_avance")["total"],
        "campanas_seguimiento": fetch_one(conn, "SELECT count(*) AS total FROM campanas_seguimiento")["total"],
    }
