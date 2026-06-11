"""
Herramienta de envío de correo del agente Gastrosena.

Es la PRIMERA acción del agente con efecto hacia afuera (el resto es solo
lectura). Por eso aplica guardrails estrictos:

  - El agente SOLO puede enviar a destinatarios pre-autorizados por rol
    (contadora, administrador, instructores...) definidos en el .env.
  - Cada correo lleva una firma institucional automática.
  - Todo envío queda registrado en el log para auditoría.
"""

import logging
import smtplib
from email.message import EmailMessage

from mcp.server.fastmcp import FastMCP

from config import (
    EMAIL_ALLOWED_RECIPIENTS,
    EMAIL_FIRMA,
    EMAIL_FROM,
    EMAIL_RECIPIENTS_BY_ROLE,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger("gastroia.correo")


def _resolver_destinatario(destinatario: str) -> str:
    """Traduce un rol (ej. 'contadora') a su correo, o valida un correo directo.

    Regla de negocio oculta al LLM: el destinatario debe ser un rol conocido
    o un correo que esté en la lista blanca. Cualquier otra cosa se rechaza.
    """
    clave = destinatario.strip().lower()
    if clave in EMAIL_RECIPIENTS_BY_ROLE:
        return EMAIL_RECIPIENTS_BY_ROLE[clave]
    if destinatario.strip() in EMAIL_ALLOWED_RECIPIENTS:
        return destinatario.strip()
    roles = ", ".join(EMAIL_RECIPIENTS_BY_ROLE) or "(ninguno configurado)"
    raise ValueError(
        f"Destinatario '{destinatario}' no autorizado. "
        f"Roles disponibles: {roles}."
    )


def _enviar_smtp(destino: str, asunto: str, cuerpo: str) -> None:
    """Punto único de salida SMTP: arma el mensaje, conecta con STARTTLS y envía."""
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(f"{cuerpo}\n\n--\n{EMAIL_FIRMA}")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


def register(mcp: FastMCP):

    @mcp.tool()
    def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
        """Envía un correo a un destinatario autorizado del SENA (contadora, administrador, instructores).

        'destinatario' puede ser el nombre del ROL (ej. 'contadora') o un correo
        que esté en la lista de autorizados. Solo se permite enviar a destinatarios
        pre-aprobados. La firma institucional se agrega automáticamente.

        IMPORTANTE: antes de llamar a esta herramienta, confirmá con el usuario el
        destinatario, el asunto y el cuerpo del mensaje.
        """
        # Guardrail 1: SMTP debe estar configurado.
        if not SMTP_USER or not SMTP_PASSWORD:
            return {"ok": False, "error": "Falta configurar SMTP_USER / SMTP_PASSWORD en el .env."}

        # Guardrail 2: tiene que haber al menos un destinatario autorizado.
        if not EMAIL_RECIPIENTS_BY_ROLE:
            return {
                "ok": False,
                "error": "No hay destinatarios autorizados. Configurá EMAIL_RECIPIENTS_BY_ROLE en el .env.",
            }

        # Guardrail 3: resolver rol -> correo y validar contra la lista blanca.
        try:
            destino = _resolver_destinatario(destinatario)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        try:
            _enviar_smtp(destino, asunto, cuerpo)
        except smtplib.SMTPAuthenticationError:
            logger.exception("Fallo de autenticación SMTP")
            return {"ok": False, "error": "Autenticación SMTP rechazada. Revisá usuario/contraseña (usá App Password en Gmail)."}
        except smtplib.SMTPException as e:
            logger.exception("Error SMTP al enviar a %s", destino)
            return {"ok": False, "error": f"No se pudo enviar el correo: {type(e).__name__}"}
        except OSError as e:
            logger.exception("Error de conexión SMTP")
            return {"ok": False, "error": f"Fallo de conexión con el servidor de correo: {e}"}

        logger.info("Correo enviado a %s | asunto: %s", destino, asunto)
        return {"ok": True, "canal": "email", "destinatario": destino, "asunto": asunto}
