from __future__ import annotations

from datetime import datetime
from typing import Any
import unittest
from zoneinfo import ZoneInfo

from app.config import Settings
from app.whatsapp_reports import (
    ReportCounts,
    WhatsAppReportError,
    build_template_payload,
    run_report,
)


class FakeCursor:
    def __init__(self, row: dict[str, Any] | None = None):
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class FakeConnection:
    def __init__(self, *, claim: bool = True):
        self.claim = claim
        self.commits = 0
        self.rollbacks = 0
        self.updates: list[tuple[Any, ...]] = []

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> FakeCursor:
        sql = " ".join(query.split())
        if sql.startswith("INSERT INTO daily_report_deliveries"):
            return FakeCursor({"id": 17} if self.claim else None)
        if "count(DISTINCT persona_id) FILTER" in sql:
            return FakeCursor({"nuevos_hoy": 4, "total_inscritos": 31})
        if sql.startswith("UPDATE daily_report_deliveries"):
            self.updates.append(params)
            return FakeCursor()
        raise AssertionError(f"Consulta inesperada: {sql}")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        whatsapp_reports_enabled=True,
        whatsapp_graph_api_version="v99.0",
        whatsapp_phone_number_id="123456789",
        whatsapp_access_token="test-token",
        whatsapp_report_recipient="593999999999",
    )


class WhatsAppReportTests(unittest.TestCase):
    def test_template_payload_uses_documented_parameter_order(self) -> None:
        settings = configured_settings()
        cutoff = datetime(2026, 9, 11, 12, 0, tzinfo=ZoneInfo("America/Guayaquil"))

        payload = build_template_payload(settings, "mediodia", ReportCounts(4, 31), cutoff)

        parameters = payload["template"]["components"][0]["parameters"]
        self.assertEqual(payload["to"], "593999999999")
        self.assertEqual(
            [parameter["text"] for parameter in parameters],
            ["del mediodía", "4", "31", "11/09/2026 12:00"],
        )

    def test_report_is_sent_and_persisted(self) -> None:
        connection = FakeConnection()
        captured_payload: dict[str, Any] = {}

        def sender(_settings: Settings, payload: dict[str, Any]) -> str:
            captured_payload.update(payload)
            return "wamid.test"

        result = run_report(
            connection,  # type: ignore[arg-type]
            configured_settings(),
            "inicio",
            now=datetime(2026, 9, 11, 8, 0, tzinfo=ZoneInfo("America/Guayaquil")),
            sender=sender,
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["nuevos_hoy"], 4)
        self.assertEqual(result["total_inscritos"], 31)
        self.assertEqual(captured_payload["template"]["name"], "reporte_inscripciones_diarias")
        self.assertEqual(result["deliveries"]["whatsapp"]["provider_message_id"], "wamid.test")
        self.assertEqual(connection.commits, 2)

    def test_duplicate_slot_is_not_sent_again(self) -> None:
        connection = FakeConnection(claim=False)
        sender_called = False

        def sender(_settings: Settings, _payload: dict[str, Any]) -> str:
            nonlocal sender_called
            sender_called = True
            return "unexpected"

        result = run_report(
            connection,  # type: ignore[arg-type]
            configured_settings(),
            "fin",
            now=datetime(2026, 9, 11, 18, 0, tzinfo=ZoneInfo("America/Guayaquil")),
            sender=sender,
        )

        self.assertEqual(result["status"], "already_processed")
        self.assertFalse(sender_called)

    def test_email_and_whatsapp_are_delivered_independently(self) -> None:
        connection = FakeConnection()
        settings = configured_settings()
        settings.smtp_enabled = True
        settings.smtp_host = "smtp.example.test"
        settings.smtp_from_email = "reportes@example.test"
        settings.daily_report_email_enabled = True
        settings.daily_report_email_recipient = "direccion@example.test"

        result = run_report(
            connection,  # type: ignore[arg-type]
            settings,
            "mediodia",
            now=datetime(2026, 9, 11, 12, 0, tzinfo=ZoneInfo("America/Guayaquil")),
            sender=lambda _settings, _payload: "wamid.test",
            email_sender=lambda _settings, _slot, _counts, _cutoff: "smtp",
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["deliveries"]["whatsapp"]["status"], "sent")
        self.assertEqual(result["deliveries"]["email"]["status"], "sent")

    def test_email_still_sends_when_whatsapp_fails(self) -> None:
        connection = FakeConnection()
        settings = configured_settings()
        settings.smtp_enabled = True
        settings.smtp_host = "smtp.example.test"
        settings.smtp_from_email = "reportes@example.test"
        settings.daily_report_email_enabled = True
        settings.daily_report_email_recipient = "direccion@example.test"

        def failed_whatsapp(_settings: Settings, _payload: dict[str, Any]) -> str:
            raise WhatsAppReportError("fallo simulado")

        result = run_report(
            connection,  # type: ignore[arg-type]
            settings,
            "fin",
            now=datetime(2026, 9, 11, 18, 0, tzinfo=ZoneInfo("America/Guayaquil")),
            sender=failed_whatsapp,
            email_sender=lambda _settings, _slot, _counts, _cutoff: "smtp",
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["deliveries"]["whatsapp"]["status"], "failed")
        self.assertEqual(result["deliveries"]["email"]["status"], "sent")

    def test_disabled_reports_fail_before_database_access(self) -> None:
        with self.assertRaisesRegex(WhatsAppReportError, "deshabilitados"):
            run_report(
                FakeConnection(),  # type: ignore[arg-type]
                Settings(_env_file=None),
                "inicio",
            )


if __name__ == "__main__":
    unittest.main()
