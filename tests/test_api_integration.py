from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import unittest

from fastapi.testclient import TestClient

from app.anti_automation import issue_form_challenge
from app.config import get_settings
from app.db import get_connection
from app.main import app
from app.security import create_access_token, hash_password


class FakeCursor:
    def __init__(self, *, one: dict[str, Any] | None = None, many: list[dict[str, Any]] | None = None):
        self.one = one
        self.many = many or ([] if one is None else [one])

    def fetchone(self) -> dict[str, Any] | None:
        return self.one

    def fetchall(self) -> list[dict[str, Any]]:
        return self.many


class FakeDatabase:
    def __init__(self) -> None:
        self.password_hash = hash_password("clave-segura")
        self.users = {
            1: {"id": 1, "email": "admin@example.com", "nombre_visible": "Admin", "estado": "activo", "roles": ["admin"]},
            2: {"id": 2, "email": "student@example.com", "nombre_visible": "Estudiante", "estado": "activo", "roles": ["estudiante"]},
            3: {"id": 3, "email": "supervisor@example.com", "nombre_visible": "Supervisor", "estado": "activo", "roles": ["supervisor"]},
        }
        self.rate_counts: dict[tuple[Any, ...], int] = {}
        self.used_challenges: set[str] = set()
        self.existing_identity = False
        self.person_insert_count = 0
        self.registration_insert_count = 0
        self.registration_status = "registrada"
        self.audit_insert_count = 0
        self.commits = 0

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> FakeCursor:
        sql = " ".join(query.split())

        if "FROM usuarios u" in sql and "lower(u.email) = lower(%s)" in sql:
            email = str(params[0]).lower()
            user = next((item for item in self.users.values() if item["email"].lower() == email), None)
            return FakeCursor(one=({**user, "password_hash": self.password_hash} if user else None))

        if "FROM usuarios u" in sql and "WHERE u.id = %s" in sql:
            return FakeCursor(one=self.users.get(int(params[0])))

        if sql.startswith("UPDATE usuarios SET ultimo_login_at"):
            return FakeCursor()

        if "INSERT INTO public_submission_rate_limits" in sql:
            key = (params[0], params[1], params[2])
            self.rate_counts[key] = self.rate_counts.get(key, 0) + 1
            return FakeCursor(one={"request_count": self.rate_counts[key]})

        if "INSERT INTO used_public_form_challenges" in sql:
            token_hash = str(params[0])
            if token_hash in self.used_challenges:
                return FakeCursor()
            self.used_challenges.add(token_hash)
            return FakeCursor(one={"token_hash": token_hash})

        if "FROM campanas_inscripcion" in sql and "WHERE slug_publico = %s" in sql:
            now = datetime.now(timezone.utc)
            return FakeCursor(
                one={
                    "id": 7,
                    "curso_id": 1,
                    "curso_version_id": 2,
                    "nombre": "Campaña de prueba",
                    "estado": "activa",
                    "fecha_inicio": now - timedelta(days=1),
                    "fecha_fin": now + timedelta(days=1),
                }
            )

        if sql == "SELECT id FROM personas WHERE cedula = %s":
            return FakeCursor(one={"id": 99} if self.existing_identity else None)

        if "AS ubicacion_valida" in sql and "AS nacionalidad_valida" in sql:
            return FakeCursor(one={"ubicacion_valida": True, "nacionalidad_valida": True})

        if "INSERT INTO personas" in sql:
            if self.existing_identity:
                return FakeCursor()
            self.person_insert_count += 1
            self.existing_identity = True
            return FakeCursor(one={"id": 99})

        if "INSERT INTO persona_contactos" in sql:
            return FakeCursor()

        if "INSERT INTO inscripciones" in sql:
            self.registration_insert_count += 1
            return FakeCursor(one={"id": 501})

        if "FROM inscripciones i JOIN personas p" in sql and "FOR UPDATE OF i" in sql:
            return FakeCursor(
                one={
                    "id": 501,
                    "estado": self.registration_status,
                    "persona_id": 99,
                    "nombre_completo": "Ana María Vera López",
                    "tiene_matriculacion": False,
                    "tiene_aprobacion": False,
                    "tiene_diploma": False,
                }
            )

        if sql.startswith("UPDATE inscripciones SET estado = %s"):
            self.registration_status = str(params[0])
            return FakeCursor(
                one={
                    "inscripcion_id": int(params[3]),
                    "persona_id": 99,
                    "estado": self.registration_status,
                    "estado_motivo": params[1],
                    "estado_actualizado_at": datetime.now(timezone.utc),
                }
            )

        if sql.startswith("INSERT INTO auditoria_acciones"):
            self.audit_insert_count += 1
            return FakeCursor()

        if "FROM usuarios u" in sql and "ORDER BY u.created_at DESC" in sql:
            rows = [
                {
                    "id": user["id"],
                    "email": user["email"],
                    "nombre_visible": user["nombre_visible"],
                    "estado": user["estado"],
                    "cedula": None,
                    "nombre_completo": None,
                    "roles": ", ".join(user["roles"]),
                }
                for user in self.users.values()
            ]
            return FakeCursor(many=rows)

        if "FROM cantones c JOIN provincias pr" in sql:
            return FakeCursor(
                many=[
                    {
                        "canton_id": 1,
                        "nombre": "24 de Mayo",
                        "inscritos": 0,
                        "matriculados": 0,
                        "aprobados": 0,
                        "tasa_aprobacion": 0,
                    },
                    {
                        "canton_id": 2,
                        "nombre": "Manta",
                        "inscritos": 3,
                        "matriculados": 2,
                        "aprobados": 1,
                        "tasa_aprobacion": 33.3,
                    },
                ]
            )

        raise AssertionError(f"Consulta no simulada: {sql[:160]}")

    def commit(self) -> None:
        self.commits += 1


def registration_payload(token: str) -> dict[str, Any]:
    return {
        "form_token": token,
        "website": "",
        "cedula": "2400000002",
        "fechaNac": "2000-01-01",
        "nombres": "Ana María",
        "apellidos": "Vera López",
        "correo": "ana@example.com",
        "celular": "+593982104735",
        "provincia_id": 1,
        "canton_id": 2,
        "parroquia_id": 3,
        "barrio": "Centro",
        "actividad": "Ninguno",
        "autoidentificacion": "Mestizo/a",
        "genero": "Mujer",
        "orientacion": "Prefiero no decirlo",
        "nacionalidad_id": 1,
        "discapacidad": "No",
        "educacion": "Tercer nivel",
        "acepto": True,
    }


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = FakeDatabase()
        app.dependency_overrides[get_connection] = lambda: self.database
        self.client = TestClient(app)
        self.settings = get_settings()
        self.original_min_seconds = self.settings.public_form_min_seconds
        self.original_ip_attempts = self.settings.rate_limit_ip_attempts
        self.original_smtp_enabled = self.settings.smtp_enabled
        self.settings.public_form_min_seconds = 0
        self.settings.smtp_enabled = False

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.settings.public_form_min_seconds = self.original_min_seconds
        self.settings.rate_limit_ip_attempts = self.original_ip_attempts
        self.settings.smtp_enabled = self.original_smtp_enabled

    def auth_header(self, user_id: int, roles: list[str]) -> dict[str, str]:
        token = create_access_token(str(user_id), roles)
        return {"Authorization": f"Bearer {token}"}

    def new_form_token(self) -> str:
        return issue_form_challenge(self.settings.auth_secret_key)

    def test_authentication_login_and_profile(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "clave-segura"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]

        profile = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["user"]["roles"], ["admin"])

        invalid = self.client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "incorrecta"},
        )
        self.assertEqual(invalid.status_code, 401)

    def test_permissions_return_401_403_and_allow_admin(self) -> None:
        self.assertEqual(self.client.get("/api/usuarios").status_code, 401)
        self.assertEqual(
            self.client.get("/api/usuarios", headers=self.auth_header(2, ["estudiante"])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/usuarios", headers=self.auth_header(3, ["supervisor"])).status_code,
            403,
        )
        allowed = self.client.get("/api/usuarios", headers=self.auth_header(1, ["admin"]))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(len(allowed.json()["items"]), 3)

    def test_canton_metrics_include_territories_without_registrations(self) -> None:
        response = self.client.get(
            "/api/admin/metricas/cantones-manabi",
            headers=self.auth_header(1, ["admin"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual(response.json()["items"][0]["nombre"], "24 de Mayo")
        self.assertEqual(response.json()["items"][0]["inscritos"], 0)
        self.assertEqual(response.json()["items"][1]["tasa_aprobacion"], 33.3)

    def test_only_admin_can_reject_or_cancel_registration(self) -> None:
        payload = {"estado": "rechazada", "motivo": "Documento de identidad incorrecto"}
        forbidden = self.client.patch(
            "/api/admin/inscritos/inscripciones/501/estado",
            headers=self.auth_header(3, ["supervisor"]),
            json=payload,
        )
        self.assertEqual(forbidden.status_code, 403)

        updated = self.client.patch(
            "/api/admin/inscritos/inscripciones/501/estado",
            headers=self.auth_header(1, ["admin"]),
            json=payload,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["item"]["estado"], "rechazada")
        self.assertEqual(self.database.registration_status, "rechazada")
        self.assertEqual(self.database.audit_insert_count, 1)

    def test_public_registration_succeeds_once_and_rejects_replay(self) -> None:
        token = self.new_form_token()
        created = self.client.post(
            "/api/public/campanas/campana-prueba/inscripciones",
            json=registration_payload(token),
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(self.database.person_insert_count, 1)
        self.assertEqual(self.database.registration_insert_count, 1)

        replay = self.client.post(
            "/api/public/campanas/campana-prueba/inscripciones",
            json=registration_payload(token),
        )
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(self.database.registration_insert_count, 1)

    def test_existing_identity_is_never_overwritten(self) -> None:
        self.database.existing_identity = True
        response = self.client.post(
            "/api/public/campanas/campana-prueba/inscripciones",
            json=registration_payload(self.new_form_token()),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.database.person_insert_count, 0)
        self.assertEqual(self.database.registration_insert_count, 0)

    def test_rate_limit_returns_429_with_retry_after(self) -> None:
        self.settings.rate_limit_ip_attempts = 1
        first_payload = registration_payload(self.new_form_token())
        first_payload["cedula"] = "2400000002"
        first = self.client.post("/api/public/campanas/campana-prueba/inscripciones", json=first_payload)
        self.assertEqual(first.status_code, 201, first.text)

        self.database.existing_identity = False
        second_payload = registration_payload(self.new_form_token())
        second_payload["cedula"] = "2300000003"
        second_payload["correo"] = "otra@example.com"
        second = self.client.post("/api/public/campanas/campana-prueba/inscripciones", json=second_payload)
        self.assertEqual(second.status_code, 429)
        self.assertIn("Retry-After", second.headers)


if __name__ == "__main__":
    unittest.main()
