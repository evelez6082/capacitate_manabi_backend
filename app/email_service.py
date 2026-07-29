from email.message import EmailMessage
from email.utils import formataddr
import logging
import smtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_preinscription_confirmation(
    *,
    to_email: str,
    full_name: str,
    campaign_name: str,
) -> bool:
    settings = get_settings()
    if not settings.smtp_enabled:
        return False

    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("SMTP habilitado, pero faltan SMTP_HOST o SMTP_FROM_EMAIL")
        return False

    message = EmailMessage()
    message["Subject"] = "Confirmacion de preinscripcion - Capacitate Manabi"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = to_email
    message["Reply-To"] = settings.support_email
    message.set_content(
        f"""Hola {full_name},

Hemos recibido correctamente tu preinscripcion para:

{campaign_name}

Tus datos fueron registrados en el sistema de Capacitate Manabi. Te contactaremos por los medios registrados cuando exista una novedad sobre tu proceso de matriculacion o seguimiento del curso.

Si no realizaste esta preinscripcion o necesitas corregir algun dato, puedes responder a este correo o comunicarte con el equipo de soporte.

Saludos,
{settings.smtp_from_name}
Prefectura de Manabi
"""
    )

    try:
        use_ssl = settings.smtp_use_ssl or settings.smtp_port == 465
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls and not use_ssl:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception:
        logger.exception("No se pudo enviar correo de confirmacion a %s", to_email)
        return False
