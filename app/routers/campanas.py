from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from app.db import execute_one, fetch_all, fetch_one, get_connection
from app.schemas import CampaignCreate
from app.utils import public_token, slugify

router = APIRouter(prefix="/api/campanas-inscripcion", tags=["campanas de inscripcion"])


@router.get("")
def listar_campanas(
    estado: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    if estado:
        rows = fetch_all(
            conn,
            """
            SELECT ci.*, c.nombre AS curso, cv.nombre AS version_moodle
            FROM campanas_inscripcion ci
            JOIN cursos c ON c.id = ci.curso_id
            LEFT JOIN curso_versiones_moodle cv ON cv.id = ci.curso_version_id
            WHERE ci.estado = %s
            ORDER BY ci.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (estado, limit, offset),
        )
    else:
        rows = fetch_all(
            conn,
            """
            SELECT ci.*, c.nombre AS curso, cv.nombre AS version_moodle
            FROM campanas_inscripcion ci
            JOIN cursos c ON c.id = ci.curso_id
            LEFT JOIN curso_versiones_moodle cv ON cv.id = ci.curso_version_id
            ORDER BY ci.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
    return {"items": rows, "limit": limit, "offset": offset}


@router.post("", status_code=201)
def crear_campana(payload: CampaignCreate, conn: Connection = Depends(get_connection)) -> dict:
    curso = fetch_one(conn, "SELECT id FROM cursos WHERE id = %s", (payload.curso_id,))
    if not curso:
        raise HTTPException(status_code=400, detail="Curso no existe")
    if payload.curso_version_id:
        version = fetch_one(conn, "SELECT id FROM curso_versiones_moodle WHERE id = %s", (payload.curso_version_id,))
        if not version:
            raise HTTPException(status_code=400, detail="Version Moodle no existe")

    slug = slugify(payload.codigo)
    token = public_token()
    row = execute_one(
        conn,
        """
        INSERT INTO campanas_inscripcion (
            curso_id, curso_version_id, codigo, nombre, organizacion_origen, descripcion,
            slug_publico, token_publico, fecha_inicio, fecha_fin
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            payload.curso_id,
            payload.curso_version_id,
            payload.codigo,
            payload.nombre,
            payload.organizacion_origen,
            payload.descripcion,
            slug,
            token,
            payload.fecha_inicio,
            payload.fecha_fin,
        ),
    )
    return row


@router.get("/{campana_id}")
def obtener_campana(campana_id: int, conn: Connection = Depends(get_connection)) -> dict:
    row = fetch_one(
        conn,
        """
        SELECT ci.*, c.nombre AS curso, cv.nombre AS version_moodle
        FROM campanas_inscripcion ci
        JOIN cursos c ON c.id = ci.curso_id
        LEFT JOIN curso_versiones_moodle cv ON cv.id = ci.curso_version_id
        WHERE ci.id = %s
        """,
        (campana_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Campana no encontrada")
    return row


@router.get("/{campana_id}/inscripciones")
def inscripciones_campana(
    campana_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT
            i.id AS inscripcion_id,
            i.fecha_inscripcion,
            i.estado,
            p.cedula,
            p.nombre_completo,
            p.correo_principal,
            p.telefono_principal
        FROM inscripciones i
        JOIN personas p ON p.id = i.persona_id
        WHERE i.campana_inscripcion_id = %s
        ORDER BY i.fecha_inscripcion NULLS LAST, p.nombre_completo
        LIMIT %s OFFSET %s
        """,
        (campana_id, limit, offset),
    )
    return {"items": rows, "limit": limit, "offset": offset}
