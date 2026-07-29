from email.message import EmailMessage
from email.utils import formataddr
from html import escape
import logging
import smtplib

from app.config import get_settings

logger = logging.getLogger(__name__)

BANNER_PREINSCRIPCION_URL = "https://cacicustech.com/capacitate_manabi/assets/banner-correo-01.jpg"
FOOTER_PREINSCRIPCION_URL = "https://cacicustech.com/capacitate_manabi/assets/fotter-correo-02.jpg"
BANNER_MOODLE_URL = "https://cacicustech.com/capacitate_manabi/assets/header_02_escuelas.jpg"
FOOTER_MOODLE_URL = "https://cacicustech.com/capacitate_manabi/assets/footer_03_escuelas.jpg"


def _smtp_configured() -> bool:
    settings = get_settings()
    if not settings.smtp_enabled:
        return False

    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("SMTP habilitado, pero faltan SMTP_HOST o SMTP_FROM_EMAIL")
        return False

    return True


def _send_message(message: EmailMessage, *, to_email: str, error_label: str) -> bool:
    if not _smtp_configured():
        return False

    settings = get_settings()
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
        logger.exception("%s a %s", error_label, to_email)
        return False


def _build_message(*, to_email: str, subject: str) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email or ""))
    message["To"] = to_email
    message["Reply-To"] = settings.support_email
    return message


def _email_shell(*, banner_url: str, footer_url: str, body_html: str) -> str:
    return f"""
<div style="margin:0;padding:0;background:#f4f6f5;font-family:Arial,Helvetica,sans-serif;color:#1b1b1b;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;background:#f4f6f5;padding:24px 0;border-collapse:collapse;">
    <tr>
      <td align="center" style="padding:0 12px;">
        <table role="presentation" width="680" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:680px;background:#ffffff;border-radius:22px;overflow:hidden;box-shadow:0 12px 35px rgba(0,0,0,0.08);border-collapse:collapse;">
          <tr>
            <td style="background:#00AA99;padding:0;">
              <img src="{banner_url}" alt="Escuela de Formacion Ciudadana y Liderazgo Territorial" width="680" style="width:100%;max-width:680px;height:auto;display:block;border:0;outline:none;text-decoration:none;">
            </td>
          </tr>
          <tr>
            <td style="padding:36px 42px;text-align:center;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="background:#00AA99;padding:0;">
              <img src="{footer_url}" alt="Informacion de contacto de la Escuela" width="680" style="width:100%;max-width:680px;height:auto;display:block;border:0;outline:none;text-decoration:none;">
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
"""


def send_preinscription_confirmation(
    *,
    to_email: str,
    full_name: str,
    campaign_name: str,
) -> bool:
    safe_full_name = escape(full_name)
    safe_campaign_name = escape(campaign_name)
    message = _build_message(
        to_email=to_email,
        subject="Confirmacion de preinscripcion",
    )
    message.set_content(
        f"""Hola {full_name},

Tu preinscripcion en la Escuela de Formacion Ciudadana y Liderazgo Territorial ha sido registrada exitosamente.

Campana: {campaign_name}

Gracias por dar este importante paso hacia el fortalecimiento de tus conocimientos, liderazgo y participacion ciudadana.

Saludos,
Escuela de Formacion Ciudadana
"""
    )
    message.add_alternative(
        _email_shell(
            banner_url=BANNER_PREINSCRIPCION_URL,
            footer_url=FOOTER_PREINSCRIPCION_URL,
            body_html=f"""
              <h1 style="margin:0;color:#00AA99;font-size:28px;line-height:1.2;font-weight:700;letter-spacing:-0.5px;">
                Hola, {safe_full_name}
              </h1>

              <p style="font-size:17px;line-height:1.7;margin:22px 0 12px;color:#374151;">
                Tu preinscripcion en la
                <strong style="color:#00AA99;">Escuela de Formacion Ciudadana y Liderazgo Territorial</strong>
                ha sido
                <strong style="color:#0F9D58;">registrada exitosamente</strong>.
              </p>

              <p style="font-size:16px;line-height:1.7;margin:0 0 12px;color:#5B6470;">
                Campana: <strong>{safe_campaign_name}</strong>
              </p>

              <p style="font-size:16px;line-height:1.7;margin:0;color:#5B6470;">
                Gracias por dar este importante paso hacia el fortalecimiento de tus conocimientos,
                liderazgo y participacion ciudadana.
              </p>
            """,
        ),
        subtype="html",
    )

    return _send_message(
        message,
        to_email=to_email,
        error_label="No se pudo enviar correo de confirmacion",
    )


def send_moodle_access_email(
    *,
    to_email: str,
    full_name: str,
    moodle_username: str,
    moodle_password: str,
    moodle_url: str,
    course_name: str,
) -> bool:
    safe_full_name = escape(full_name)
    safe_moodle_username = escape(moodle_username)
    safe_moodle_password = escape(moodle_password)
    safe_moodle_url = escape(moodle_url, quote=True)
    safe_course_name = escape(course_name)
    message = _build_message(
        to_email=to_email,
        subject="Ya puedes iniciar tu curso virtual",
    )
    message.set_content(
        f"""Hola {full_name},

Ya estas inscrito en el curso:
{course_name}

Puedes ingresar a Moodle con estas credenciales:

Usuario: {moodle_username}
Contrasena: {moodle_password}
URL: {moodle_url}

Te recomendamos cambiar tu contrasena despues del primer ingreso y avanzar en cada modulo hasta completar todas las actividades.

Saludos,
Escuela de Formacion Ciudadana
"""
    )
    message.add_alternative(
        _email_shell(
            banner_url=BANNER_MOODLE_URL,
            footer_url=FOOTER_MOODLE_URL,
            body_html=f"""
              <h1 style="margin:0;color:#00AA99;font-size:28px;line-height:1.2;font-weight:700;">
                Hola, {safe_full_name}
              </h1>

              <p style="font-size:17px;line-height:1.7;margin:22px 0 12px;color:#374151;">
                Ya estas inscrito en el curso:
                <br>
                <strong style="color:#00AA99;">{safe_course_name}</strong>
              </p>

              <p style="font-size:16px;line-height:1.7;margin:0 0 24px;color:#5B6470;">
                Ahora puedes ingresar a la plataforma virtual Moodle y comenzar tu proceso de formacion.
              </p>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;margin:0 auto 28px;border-collapse:separate;">
                <tr>
                  <td style="padding:22px;text-align:left;">
                    <p style="margin:0 0 12px;font-size:16px;color:#374151;">
                      <strong>Usuario:</strong> {safe_moodle_username}
                    </p>
                    <p style="margin:0;font-size:16px;color:#374151;">
                      <strong>Contrasena:</strong> {safe_moodle_password}
                    </p>
                  </td>
                </tr>
              </table>

              <a href="{safe_moodle_url}" style="display:inline-block;background:#00AA99;color:#ffffff;text-decoration:none;padding:15px 28px;border-radius:999px;font-weight:700;font-size:16px;">
                Iniciar sesion en Moodle
              </a>

              <p style="font-size:14px;line-height:1.6;margin:24px 0 0;color:#6b7280;">
                Te recomendamos cambiar tu contrasena despues del primer ingreso y avanzar en cada modulo hasta completar todas las actividades.
              </p>
            """,
        ),
        subtype="html",
    )

    return _send_message(
        message,
        to_email=to_email,
        error_label="No se pudo enviar correo de acceso Moodle",
    )
