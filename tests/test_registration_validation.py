from pathlib import Path
import unittest

from pydantic import ValidationError

from app.schemas import CampaignCreate, PublicRegistrationCreate
from app.validation import is_valid_ecuadorian_id


ROOT = Path(__file__).resolve().parents[1]


def valid_payload() -> dict:
    return {
        "form_token": "x" * 40,
        "cedula": "2400000002",
        "fechaNac": "2000-01-01",
        "nombres": "Ana María",
        "apellidos": "Vera López",
        "correo": "ANA@EXAMPLE.COM",
        "celular": "+593982104735",
        "provincia_id": 1,
        "canton_id": 1,
        "parroquia_id": 1,
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


class RegistrationValidationTests(unittest.TestCase):
    def test_ecuadorian_id_checksum(self) -> None:
        self.assertTrue(is_valid_ecuadorian_id("2400000002"))
        self.assertFalse(is_valid_ecuadorian_id("2400000001"))
        self.assertFalse(is_valid_ecuadorian_id("2500000000"))
        self.assertFalse(is_valid_ecuadorian_id("24A0000002"))

    def test_complete_payload_is_normalized(self) -> None:
        registration = PublicRegistrationCreate(**valid_payload())
        self.assertEqual(registration.correo, "ana@example.com")
        self.assertEqual(registration.nombres, "Ana María")

    def test_rejects_invalid_core_fields(self) -> None:
        invalid_values = {
            "cedula": "2400000001",
            "fechaNac": "2099-01-01",
            "correo": "correo-invalido",
            "celular": "0982104735",
        }
        for field, value in invalid_values.items():
            with self.subTest(field=field):
                payload = valid_payload()
                payload[field] = value
                with self.assertRaises(ValidationError):
                    PublicRegistrationCreate(**payload)

    def test_conditional_fields_are_required(self) -> None:
        working = valid_payload() | {"actividad": "Trabajo", "institucion": ""}
        disability = valid_payload() | {"discapacidad": "Sí", "tipoDiscapacidad": ""}
        for payload in (working, disability):
            with self.assertRaises(ValidationError):
                PublicRegistrationCreate(**payload)

    def test_campaign_end_must_follow_start(self) -> None:
        with self.assertRaises(ValidationError):
            CampaignCreate(
                codigo="campana-prueba",
                nombre="Campaña de prueba",
                fecha_inicio="2026-09-10T12:00:00Z",
                fecha_fin="2026-09-10T11:00:00Z",
            )

    def test_catalog_hierarchy_is_validated_server_side(self) -> None:
        source = (ROOT / "app" / "routers" / "publico.py").read_text(encoding="utf-8")
        self.assertIn("JOIN cantones", source)
        self.assertIn("JOIN provincias", source)
        self.assertIn("ubicacion_valida", source)
        self.assertIn("nacionalidad_valida", source)

    def test_required_profile_fields_are_not_optional(self) -> None:
        source = (ROOT / "app" / "schemas.py").read_text(encoding="utf-8")
        for declaration in (
            "fechaNac: date",
            "provincia_id: int",
            "canton_id: int",
            "parroquia_id: int",
            "nacionalidad_id: int",
            "barrio: str",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, source)


if __name__ == "__main__":
    unittest.main()
