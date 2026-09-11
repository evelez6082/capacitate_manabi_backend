from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from psycopg import Connection
from psycopg.types.json import Jsonb

from app.anti_automation import InvalidFormChallenge, issue_form_challenge, private_fingerprint, verify_form_challenge
from app.config import get_settings
from app.db import fetch_all, fetch_one, get_connection
from app.email_service import send_preinscription_confirmation
from app.schemas import PublicRegistrationCreate

router = APIRouter(prefix="/api/public", tags=["publico"])


def get_client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.client_ip_header:
        forwarded = request.headers.get(settings.client_ip_header)
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def increment_rate_limit(
    conn: Connection,
    scope: str,
    raw_key: str,
    limit: int,
    window_seconds: int,
    now: datetime,
) -> None:
    settings = get_settings()
    epoch = int(now.timestamp())
    window_epoch = epoch - (epoch % window_seconds)
    window_start = datetime.fromtimestamp(window_epoch, timezone.utc)
    expires_at = datetime.fromtimestamp(window_epoch + window_seconds * 2, timezone.utc)
    result = conn.execute(
        """
        INSERT INTO public_submission_rate_limits (
            scope, key_hash, window_started_at, request_count, expires_at
        )
        VALUES (%s, %s, %s, 1, %s)
        ON CONFLICT (scope, key_hash, window_started_at) DO UPDATE SET
            request_count = public_submission_rate_limits.request_count + 1,
            expires_at = EXCLUDED.expires_at
        RETURNING request_count
        """,
        (scope, private_fingerprint(raw_key, settings.auth_secret_key), window_start, expires_at),
    ).fetchone()
    if result and int(result["request_count"]) > limit:
        conn.commit()
        retry_after = max(1, window_epoch + window_seconds - epoch)
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Espera antes de volver a enviar el formulario.",
            headers={"Retry-After": str(retry_after)},
        )


def enforce_anti_automation(request: Request, payload: PublicRegistrationCreate, conn: Connection) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    try:
        challenge = verify_form_challenge(
            payload.form_token,
            settings.auth_secret_key,
            settings.public_form_min_seconds,
            settings.public_form_max_seconds,
            int(now.timestamp()),
        )
    except InvalidFormChallenge as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    increment_rate_limit(
        conn,
        "ip",
        get_client_ip(request),
        settings.rate_limit_ip_attempts,
        settings.rate_limit_ip_window_seconds,
        now,
    )
    increment_rate_limit(
        conn,
        "identity",
        payload.cedula,
        settings.rate_limit_identity_attempts,
        settings.rate_limit_identity_window_seconds,
        now,
    )
    increment_rate_limit(
        conn,
        "email",
        payload.correo,
        settings.rate_limit_email_attempts,
        settings.rate_limit_email_window_seconds,
        now,
    )

    challenge_hash = private_fingerprint(payload.form_token, settings.auth_secret_key)
    consumed = conn.execute(
        """
        INSERT INTO used_public_form_challenges (token_hash, issued_at, expires_at)
        VALUES (%s, to_timestamp(%s), to_timestamp(%s))
        ON CONFLICT (token_hash) DO NOTHING
        RETURNING token_hash
        """,
        (
            challenge_hash,
            int(challenge["iat"]),
            int(challenge["iat"]) + settings.public_form_max_seconds,
        ),
    ).fetchone()
    conn.commit()
    if not consumed:
        raise HTTPException(status_code=409, detail="El formulario ya fue enviado. Recarga la página para intentarlo nuevamente.")
    if payload.website:
        raise HTTPException(status_code=400, detail="No se pudo validar el formulario")


def digits_only(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    return digits or None


def validate_catalog_ids(conn: Connection, payload: PublicRegistrationCreate) -> None:
    validation = fetch_one(
        conn,
        """
        SELECT
            EXISTS (
                SELECT 1
                FROM parroquias pa
                JOIN cantones ca ON ca.id = pa.canton_id
                JOIN provincias pr ON pr.id = ca.provincia_id
                WHERE pr.id = %s
                  AND ca.id = %s
                  AND pa.id = %s
                  AND pr.activo = true
                  AND ca.activo = true
                  AND pa.activo = true
            ) AS ubicacion_valida,
            EXISTS (
                SELECT 1
                FROM nacionalidades n
                WHERE n.id = %s AND n.activo = true
            ) AS nacionalidad_valida
        """,
        (payload.provincia_id, payload.canton_id, payload.parroquia_id, payload.nacionalidad_id),
    )
    if not validation or not validation["ubicacion_valida"]:
        raise HTTPException(status_code=422, detail="La provincia, el cantón y la parroquia no forman una ubicación válida")
    if not validation["nacionalidad_valida"]:
        raise HTTPException(status_code=422, detail="La nacionalidad seleccionada no es válida")


def normalize_registration(payload: PublicRegistrationCreate) -> dict[str, Any]:
    return payload.model_dump(mode="json", exclude={"form_token", "website"})


@router.get("/form-challenge")
def form_challenge() -> dict[str, str | int]:
    settings = get_settings()
    return {
        "form_token": issue_form_challenge(settings.auth_secret_key),
        "expires_in": settings.public_form_max_seconds,
    }


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
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> dict:
    if not payload.acepto:
        raise HTTPException(status_code=400, detail="Debes aceptar los terminos para inscribirte")

    enforce_anti_automation(request, payload, conn)

    campaign = fetch_one(
        conn,
        """
        SELECT id, curso_id, curso_version_id, nombre, estado, fecha_inicio, fecha_fin
        FROM campanas_inscripcion
        WHERE slug_publico = %s
        """,
        (slug_publico,),
    )
    if not campaign or campaign["estado"] != "activa":
        raise HTTPException(status_code=404, detail="Campana no disponible")
    now = datetime.now(timezone.utc)
    if campaign["fecha_inicio"] and now < campaign["fecha_inicio"]:
        raise HTTPException(status_code=422, detail="La campaña de inscripción todavía no ha iniciado")
    if campaign["fecha_fin"] and now > campaign["fecha_fin"]:
        raise HTTPException(status_code=422, detail="La campaña de inscripción ha finalizado")

    cedula = digits_only(payload.cedula)
    telefono = digits_only(payload.celular)
    if not cedula or len(cedula) < 10:
        raise HTTPException(status_code=400, detail="Cedula invalida")

    existing_person = fetch_one(conn, "SELECT id FROM personas WHERE cedula = %s", (cedula,))
    if existing_person:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una persona registrada con esta cedula. Contacta a soporte para actualizar tus datos.",
        )

    validate_catalog_ids(conn, payload)
    provincia_id, canton_id, parroquia_id = payload.provincia_id, payload.canton_id, payload.parroquia_id
    nacionalidad_id = payload.nacionalidad_id
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
        ON CONFLICT (cedula) DO NOTHING
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
    if not persona:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una persona registrada con esta cedula. Contacta a soporte para actualizar tus datos.",
        )
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
            now,
            payload.actividad,
            payload.institucion,
            f"Inscripcion publica desde campana {campaign['nombre']}",
            Jsonb(raw_data),
        ),
    ).fetchone()
    conn.commit()

    background_tasks.add_task(
        send_preinscription_confirmation,
        to_email=payload.correo,
        full_name=nombre_completo,
        campaign_name=campaign["nombre"],
    )

    return {
        "message": "Inscripcion registrada correctamente",
        "persona_id": persona_id,
        "inscripcion_id": int(inscripcion["id"]),
        "campana": campaign["nombre"],
        "correo_programado": True,
    }
