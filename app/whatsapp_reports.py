from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg

from app.config import Settings


REPORT_SLOT_LABELS = {
    "inicio": "de inicio del día",
    "mediodia": "del mediodía",
    "fin": "de cierre del día",
}


class WhatsAppReportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReportCounts:
    nuevos_hoy: int
    total_inscritos: int


def validate_configuration(settings: Settings) -> None:
    if not settings.whatsapp_reports_enabled:
        raise WhatsAppReportError("Los reportes de WhatsApp están deshabilitados.")

    required = {
        "WHATSAPP_GRAPH_API_VERSION": settings.whatsapp_graph_api_version,
        "WHATSAPP_PHONE_NUMBER_ID": settings.whatsapp_phone_number_id,
        "WHATSAPP_ACCESS_TOKEN": settings.whatsapp_access_token,
        "WHATSAPP_REPORT_RECIPIENT": settings.whatsapp_report_recipient,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise WhatsAppReportError(f"Faltan variables de entorno: {', '.join(missing)}")
    if not re.fullmatch(r"v\d+\.\d+", settings.whatsapp_graph_api_version or ""):
        raise WhatsAppReportError("WHATSAPP_GRAPH_API_VERSION debe tener el formato vNN.N.")
    if not re.fullmatch(r"\d+", settings.whatsapp_phone_number_id or ""):
        raise WhatsAppReportError("WHATSAPP_PHONE_NUMBER_ID debe contener solo dígitos.")
    if not re.fullmatch(r"\d{8,15}", settings.whatsapp_report_recipient or ""):
        raise WhatsAppReportError(
            "WHATSAPP_REPORT_RECIPIENT debe estar en formato internacional, solo dígitos."
        )
    try:
        ZoneInfo(settings.whatsapp_report_timezone)
    except ZoneInfoNotFoundError as exc:
        raise WhatsAppReportError("WHATSAPP_REPORT_TIMEZONE no es una zona horaria válida.") from exc


def validate_email_configuration(settings: Settings) -> None:
    if not settings.daily_report_email_enabled:
        raise WhatsAppReportError("Los reportes por correo están deshabilitados.")
    required = {
        "DAILY_REPORT_EMAIL_RECIPIENT": settings.daily_report_email_recipient,
        "SMTP_HOST": settings.smtp_host,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
    }
    missing = [name for name, value in required.items() if not value]
    if not settings.smtp_enabled:
        missing.insert(0, "SMTP_ENABLED=true")
    if missing:
        raise WhatsAppReportError(f"Falta configuración para el correo diario: {', '.join(missing)}")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", settings.daily_report_email_recipient or ""):
        raise WhatsAppReportError("DAILY_REPORT_EMAIL_RECIPIENT no es un correo válido.")


def build_template_payload(
    settings: Settings,
    slot: str,
    counts: ReportCounts,
    cutoff: datetime,
) -> dict[str, Any]:
    if slot not in REPORT_SLOT_LABELS:
        raise WhatsAppReportError(f"Horario de reporte no válido: {slot}")
    return {
        "messaging_product": "whatsapp",
        "to": settings.whatsapp_report_recipient,
        "type": "template",
        "template": {
            "name": settings.whatsapp_report_template,
            "language": {"code": settings.whatsapp_report_template_language},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": REPORT_SLOT_LABELS[slot]},
                        {"type": "text", "text": str(counts.nuevos_hoy)},
                        {"type": "text", "text": str(counts.total_inscritos)},
                        {"type": "text", "text": cutoff.strftime("%d/%m/%Y %H:%M")},
                    ],
                }
            ],
        },
    }


def send_cloud_api_message(settings: Settings, payload: dict[str, Any]) -> str:
    url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise WhatsAppReportError(f"WhatsApp Cloud API respondió HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise WhatsAppReportError("No se pudo conectar con WhatsApp Cloud API.") from exc

    messages = result.get("messages", [])
    if not messages or not messages[0].get("id"):
        raise WhatsAppReportError("WhatsApp Cloud API no devolvió un identificador de mensaje.")
    return str(messages[0]["id"])


def send_email_message(
    settings: Settings,
    slot: str,
    counts: ReportCounts,
    cutoff: datetime,
) -> str:
    from app.email_service import send_daily_registration_report

    sent = send_daily_registration_report(
        to_email=settings.daily_report_email_recipient or "",
        slot_label=REPORT_SLOT_LABELS[slot],
        nuevos_hoy=counts.nuevos_hoy,
        total_inscritos=counts.total_inscritos,
        cutoff_label=cutoff.strftime("%d/%m/%Y %H:%M"),
    )
    if not sent:
        raise WhatsAppReportError("El servidor SMTP no pudo enviar el reporte diario.")
    return "smtp"


def run_report(
    conn: psycopg.Connection,
    settings: Settings,
    slot: str,
    *,
    now: datetime | None = None,
    sender: Callable[[Settings, dict[str, Any]], str] = send_cloud_api_message,
    email_sender: Callable[[Settings, str, ReportCounts, datetime], str] = send_email_message,
) -> dict[str, Any]:
    if slot not in REPORT_SLOT_LABELS:
        raise WhatsAppReportError(f"Horario de reporte no válido: {slot}")
    try:
        timezone = ZoneInfo(settings.whatsapp_report_timezone)
    except ZoneInfoNotFoundError as exc:
        raise WhatsAppReportError("WHATSAPP_REPORT_TIMEZONE no es una zona horaria válida.") from exc

    channels: list[tuple[str, str]] = []
    if settings.whatsapp_reports_enabled:
        validate_configuration(settings)
        channels.append(("whatsapp", settings.whatsapp_report_recipient or ""))
    if settings.daily_report_email_enabled:
        validate_email_configuration(settings)
        channels.append(("email", settings.daily_report_email_recipient or ""))
    if not channels:
        raise WhatsAppReportError("Los reportes por WhatsApp y correo están deshabilitados.")

    cutoff = (now or datetime.now(timezone)).astimezone(timezone)
    report_date = cutoff.date()

    row = conn.execute(
        """
        SELECT
            count(DISTINCT persona_id) FILTER (
                WHERE (fecha_inscripcion AT TIME ZONE %s)::date = %s
            ) AS nuevos_hoy,
            count(DISTINCT persona_id) AS total_inscritos
        FROM inscripciones
        """,
        (settings.whatsapp_report_timezone, report_date),
    ).fetchone()
    counts = ReportCounts(
        nuevos_hoy=int(row["nuevos_hoy"] or 0),
        total_inscritos=int(row["total_inscritos"] or 0),
    )
    deliveries: dict[str, dict[str, Any]] = {}

    for channel, recipient in channels:
        claimed = conn.execute(
            """
            INSERT INTO daily_report_deliveries (
                report_date, report_slot, channel, recipient, status, attempt_count, last_attempt_at
            )
            VALUES (%s, %s, %s, %s, 'pending', 1, now())
            ON CONFLICT (report_date, report_slot, channel, recipient) DO UPDATE
            SET status = 'pending',
                attempt_count = daily_report_deliveries.attempt_count + 1,
                last_attempt_at = now(),
                error_message = NULL
            WHERE daily_report_deliveries.status = 'failed'
               OR (
                   daily_report_deliveries.status = 'pending'
                   AND daily_report_deliveries.last_attempt_at < now() - interval '15 minutes'
               )
            RETURNING id
            """,
            (report_date, slot, channel, recipient),
        ).fetchone()
        conn.commit()
        if not claimed:
            deliveries[channel] = {"status": "already_processed"}
            continue

        delivery_id = claimed["id"]
        try:
            if channel == "whatsapp":
                provider_message_id = sender(settings, build_template_payload(settings, slot, counts, cutoff))
            else:
                provider_message_id = email_sender(settings, slot, counts, cutoff)
            conn.execute(
                """
                UPDATE daily_report_deliveries
                SET status = 'sent', provider_message_id = %s, sent_at = now(), error_message = NULL
                WHERE id = %s
                """,
                (provider_message_id, delivery_id),
            )
            conn.commit()
            deliveries[channel] = {"status": "sent", "provider_message_id": provider_message_id}
        except Exception as exc:
            conn.rollback()
            conn.execute(
                """
                UPDATE daily_report_deliveries
                SET status = 'failed', error_message = %s
                WHERE id = %s
                """,
                (str(exc)[:1000], delivery_id),
            )
            conn.commit()
            deliveries[channel] = {"status": "failed", "error": str(exc)}

    statuses = {delivery["status"] for delivery in deliveries.values()}
    overall_status = "sent" if statuses == {"sent"} else "partial" if "sent" in statuses else statuses.pop()
    return {
        "status": overall_status,
        "slot": slot,
        "report_date": str(report_date),
        "nuevos_hoy": counts.nuevos_hoy,
        "total_inscritos": counts.total_inscritos,
        "deliveries": deliveries,
    }
