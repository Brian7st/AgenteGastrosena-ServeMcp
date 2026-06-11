"""
Bot de Telegram — interfaz de chat con el agente Gastrosena (GastroIA).

Es un punto de entrada PARALELO al de Angular: en vez de la web, el usuario
le escribe al bot desde Telegram y el agente responde sus consultas.

Flujo:
    Telegram  --mensaje-->  este bot (polling)  -->  run_agent()
              -->  servidor MCP (:8000)  -->  microservicios backend

Requisitos para correr:
    1. El servidor MCP debe estar levantado (python -m server.main).
    2. TELEGRAM_BOT_TOKEN configurado en el .env.

Alcance: el agente es SOLO LECTURA. Este bot no agrega acciones de escritura.
"""

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent.main import run_agent
from config import TELEGRAM_ALLOWED_CHAT_IDS, TELEGRAM_BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("gastroia.telegram")

# Telegram corta los mensajes a 4096 caracteres. Dejamos margen.
_MAX_TELEGRAM_CHARS = 4000

_BIENVENIDA = (
    "¡Hola! Soy *GastroIA* 🍽️\n\n"
    "Puedo responder consultas sobre el inventario, el bar y el restaurante "
    "de Gastrosena. Escribime tu pregunta en lenguaje natural.\n\n"
    "Ejemplos:\n"
    "• ¿Cuántos productos hay en el inventario?\n"
    "• Listame las categorías\n"
    "• ¿Qué productos son de la categoría Fruver?"
)


def _autorizado(chat_id: int) -> bool:
    """True si el chat puede usar el bot.

    Si la lista blanca está vacía, se permite a todos (modo abierto).
    """
    if not TELEGRAM_ALLOWED_CHAT_IDS:
        return True
    return str(chat_id) in TELEGRAM_ALLOWED_CHAT_IDS


def _trozos(texto: str, limite: int = _MAX_TELEGRAM_CHARS):
    """Parte un texto largo en trozos que Telegram pueda enviar."""
    for i in range(0, len(texto), limite):
        yield texto[i : i + limite]


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de /start: muestra la bienvenida."""
    chat_id = update.effective_chat.id
    if not _autorizado(chat_id):
        await update.message.reply_text(
            "No estás autorizado para usar este bot. "
            "Pedile acceso al administrador (tu chat_id es: "
            f"{chat_id})."
        )
        return
    await update.message.reply_text(_BIENVENIDA, parse_mode="Markdown")


async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de mensajes de texto: consulta al agente y responde."""
    chat_id = update.effective_chat.id
    if not _autorizado(chat_id):
        logger.warning("Mensaje de chat_id no autorizado: %s", chat_id)
        await update.message.reply_text(
            f"No estás autorizado para usar este bot. Tu chat_id es: {chat_id}"
        )
        return

    pregunta = (update.message.text or "").strip()
    if not pregunta:
        return

    # Indicador "escribiendo…" mientras el agente piensa.
    await _ctx.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        respuesta = await run_agent(pregunta)
    except BaseException as e:  # noqa: BLE001 - cualquier fallo se reporta al usuario
        logger.exception("Fallo del agente para chat_id %s", chat_id)
        await update.message.reply_text(
            "Ups, tuve un problema al consultar el sistema. "
            "Probá de nuevo en un momento.\n"
            f"(detalle técnico: {type(e).__name__})"
        )
        return

    respuesta = respuesta or "No obtuve respuesta."
    # Enviamos como texto plano: la salida del agente es Markdown libre y
    # rompería el parser estricto de Telegram. Texto plano = siempre llega.
    for trozo in _trozos(respuesta):
        await update.message.reply_text(trozo)


def main() -> None:
    """Arranca el bot en modo polling."""
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN en el .env. "
            "Creá el bot con @BotFather y pegá el token."
        )

    if not TELEGRAM_ALLOWED_CHAT_IDS:
        logger.warning(
            "TELEGRAM_ALLOWED_CHAT_IDS está vacío: el bot responderá a CUALQUIERA. "
            "Para restringir, agregá los chat_id autorizados al .env."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Bot de Telegram iniciado (polling). Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
