from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.types.json import Jsonb

from app.db import fetch_all, fetch_one, get_connection
from app.email_service import send_preinscription_confirmation
from app.schemas import PublicRegistrationCreate

router = APIRouter(prefix="/api/public", tags=["publico"])


def digits_only(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    return digits or None


def get_or_create_named(conn: Connection, table: str, value: str | None) -> int | None:
    if not value:
        return None
    row = conn.execute(
        f"""
        INSERT INTO {table} (nombre)
        VALUES (%s)
        ON CONFLICT (nombre) DO UPDATE SET activo = true
        RETURNING id
        """,
        (value,),
    ).fetchone()
    return int(row["id"]) if row else None


def get_or_create_geo(
    conn: Connection,
    provincia: str | None,
    canton: str | None,
    parroquia: str | None,
) -> tuple[int | None, int | None, int | None]:
    provincia_id = get_or_create_named(conn, "provincias", provincia)
    canton_id = None
    parroquia_id = None
    if provincia_id and canton:
        row = conn.execute(
            """
            INSERT INTO cantones (provincia_id, nombre)
            VALUES (%s, %s)
            ON CONFLICT (provincia_id, nombre) DO UPDATE SET activo = true
            RETURNING id
            """,
            (provincia_id, canton),
        ).fetchone()
        canton_id = int(row["id"]) if row else None
    if canton_id and parroquia:
        row = conn.execute(
            """
            INSERT INTO parroquias (canton_id, nombre)
            VALUES (%s, %s)
            ON CONFLICT (canton_id, nombre) DO UPDATE SET activo = true
            RETURNING id
            """,
            (canton_id, parroquia),
        ).fetchone()
        parroquia_id = int(row["id"]) if row else None
    return provincia_id, canton_id, parroquia_id


def resolve_geo_ids(
    conn: Connection,
    payload: PublicRegistrationCreate,
) -> tuple[int | None, int | None, int | None]:
    if payload.provincia_id or payload.canton_id or payload.parroquia_id:
        return payload.provincia_id, payload.canton_id, payload.parroquia_id
    return get_or_create_geo(conn, payload.provincia, payload.canton, payload.parroquia)


def normalize_registration(payload: PublicRegistrationCreate) -> dict[str, Any]:
    return payload.model_dump(mode="json")


@router.get("/campanas/{slug_publico}")
def obtener_campana_publica(slug_publico: str, conn: Connection = Depends(get_connection)) -> dict:
    row = fetch_one(
        conn,
        """
        SELECT
            ci.id,
            ci.codigo,
            ci.nombre,
            ci.organizacion_origen,
            ci.descripcion,
            ci.slug_publico,
            ci.estado,
            ci.fecha_inicio,
            ci.fecha_fin,
            c.nombre AS curso,
            cv.nombre AS version_moodle
        FROM campanas_inscripcion ci
        JOIN cursos c ON c.id = ci.curso_id
        LEFT JOIN curso_versiones_moodle cv ON cv.id = ci.curso_version_id
        WHERE ci.slug_publico = %s
        """,
        (slug_publico,),
    )
    if not row or row["estado"] != "activa":
        raise HTTPException(status_code=404, detail="Campana no disponible")
    return row


@router.get("/catalogos/provincias")
def listar_provincias_publicas(conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT id, nombre
        FROM provincias
        WHERE activo = true
        ORDER BY nombre
        """,
    )
    return {"items": rows}


@router.get("/catalogos/cantones")
def listar_cantones_publicos(provincia_id: int, conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT id, nombre
        FROM cantones
        WHERE activo = true
          AND provincia_id = %s
        ORDER BY nombre
        """,
        (provincia_id,),
    )
    return {"items": rows}


@router.get("/catalogos/parroquias")
def listar_parroquias_publicas(canton_id: int, conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT id, nombre
        FROM parroquias
        WHERE activo = true
          AND canton_id = %s
        ORDER BY nombre
        """,
        (canton_id,),
    )
    return {"items": rows}


@router.get("/catalogos/nacionalidades")
def listar_nacionalidades_publicas(conn: Connection = Depends(get_connection)) -> dict:
    rows = fetch_all(
        conn,
        """
        SELECT id, nombre
        FROM nacionalidades
        WHERE activo = true
        ORDER BY
            CASE
                WHEN lower(nombre) IN ('ecuatoriana', 'ecuador', 'ecuatoriano/a', 'ecuatoriano') THEN 0
                ELSE 1
            END,
            nombre
        """,
    )
    return {"items": rows}


@router.post("/campanas/{slug_publico}/inscripciones", status_code=201)
def registrar_inscripcion_publica(
    slug_publico: str,
    payload: PublicRegistrationCreate,
    conn: Connection = Depends(get_connection),
) -> dict:
    if not payload.acepto:
        raise HTTPException(status_code=400, detail="Debes aceptar los terminos para inscribirte")

    campaign = fetch_one(
        conn,
        """
        SELECT id, curso_id, curso_version_id, nombre, estado
        FROM campanas_inscripcion
        WHERE slug_publico = %s
        """,
        (slug_publico,),
    )
    if not campaign or campaign["estado"] != "activa":
        raise HTTPException(status_code=404, detail="Campana no disponible")

    cedula = digits_only(payload.cedula)
    telefono = digits_only(payload.celular)
    if not cedula or len(cedula) < 10:
        raise HTTPException(status_code=400, detail="Cedula invalida")

    provincia_id, canton_id, parroquia_id = resolve_geo_ids(conn, payload)
    nacionalidad_id = payload.nacionalidad_id or get_or_create_named(conn, "nacionalidades", payload.nacionalidad)
    raw_data = normalize_registration(payload)
    nombre_completo = f"{payload.nombres} {payload.apellidos}".strip()

    persona = conn.execute(
        """
        INSERT INTO personas (
            cedula, nombres, apellidos, nombre_completo, correo_principal, telefono_principal,
            fecha_nacimiento, genero, etnia, nivel_educativo, discapacidad, nacionalidad_id,
            provincia_id, canton_id, parroquia_id, sector, datos_extra
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (cedula) DO UPDATE SET
            nombres = COALESCE(EXCLUDED.nombres, personas.nombres),
            apellidos = COALESCE(EXCLUDED.apellidos, personas.apellidos),
            nombre_completo = COALESCE(EXCLUDED.nombre_completo, personas.nombre_completo),
            correo_principal = COALESCE(EXCLUDED.correo_principal, personas.correo_principal),
            telefono_principal = COALESCE(EXCLUDED.telefono_principal, personas.telefono_principal),
            fecha_nacimiento = COALESCE(EXCLUDED.fecha_nacimiento, personas.fecha_nacimiento),
            genero = COALESCE(EXCLUDED.genero, personas.genero),
            etnia = COALESCE(EXCLUDED.etnia, personas.etnia),
            nivel_educativo = COALESCE(EXCLUDED.nivel_educativo, personas.nivel_educativo),
            discapacidad = COALESCE(EXCLUDED.discapacidad, personas.discapacidad),
            nacionalidad_id = COALESCE(EXCLUDED.nacionalidad_id, personas.nacionalidad_id),
            provincia_id = COALESCE(EXCLUDED.provincia_id, personas.provincia_id),
            canton_id = COALESCE(EXCLUDED.canton_id, personas.canton_id),
            parroquia_id = COALESCE(EXCLUDED.parroquia_id, personas.parroquia_id),
            sector = COALESCE(EXCLUDED.sector, personas.sector),
            datos_extra = personas.datos_extra || EXCLUDED.datos_extra,
            updated_at = now()
        RETURNING id
        """,
        (
            cedula,
            payload.nombres,
            payload.apellidos,
            nombre_completo,
            payload.correo,
            telefono,
            payload.fechaNac,
            payload.genero,
            payload.autoidentificacion,
            payload.educacion,
            payload.discapacidad,
            nacionalidad_id,
            provincia_id,
            canton_id,
            parroquia_id,
            payload.barrio,
            Jsonb({"frontend": raw_data}),
        ),
    ).fetchone()
    persona_id = int(persona["id"])

    for tipo, valor in (("correo", payload.correo), ("telefono", telefono), ("whatsapp", telefono)):
        if valor:
            conn.execute(
                """
                INSERT INTO persona_contactos (persona_id, tipo, valor, es_principal)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (persona_id, tipo, valor) DO NOTHING
                """,
                (persona_id, tipo, valor),
            )

    inscripcion = conn.execute(
        """
        INSERT INTO inscripciones (
            persona_id, curso_id, curso_version_id, campana_inscripcion_id, fecha_inscripcion,
            modalidad, ocupacion, institucion, consentimiento, observacion, raw_data
        )
        VALUES (%s, %s, %s, %s, %s, 'Virtual', %s, %s, true, %s, %s)
        RETURNING id
        """,
        (
            persona_id,
            campaign["curso_id"],
            campaign["curso_version_id"],
            campaign["id"],
            datetime.utcnow(),
            payload.actividad,
            payload.institucion,
            f"Inscripcion publica desde campana {campaign['nombre']}",
            Jsonb(raw_data),
        ),
    ).fetchone()
    conn.commit()

    correo_enviado = send_preinscription_confirmation(
        to_email=payload.correo,
        full_name=nombre_completo,
        campaign_name=campaign["nombre"],
    )

    return {
        "message": "Inscripcion registrada correctamente",
        "persona_id": persona_id,
        "inscripcion_id": int(inscripcion["id"]),
        "campana": campaign["nombre"],
        "correo_enviado": correo_enviado,
    }
