from pathlib import Path
import unittest


PUBLIC_ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "publico.py"


class PublicRegistrationIdentityPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PUBLIC_ROUTER.read_text(encoding="utf-8")
        self.person_insert = self.source.split("INSERT INTO personas", 1)[1].split("RETURNING id", 1)[0]

    def test_anonymous_registration_never_updates_an_existing_person(self) -> None:
        self.assertIn("ON CONFLICT (cedula) DO NOTHING", self.person_insert)
        self.assertNotIn("DO UPDATE", self.person_insert)

    def test_existing_identity_returns_conflict(self) -> None:
        self.assertIn("SELECT id FROM personas WHERE cedula = %s", self.source)
        self.assertGreaterEqual(self.source.count("status_code=409"), 2)


if __name__ == "__main__":
    unittest.main()
