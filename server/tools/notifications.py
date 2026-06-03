from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):

    @mcp.tool()
    def enviar_telegram(mensaje: str, chat_id: str = "") -> dict:
        """Envía un mensaje por Telegram al chat configurado o a uno específico."""
        # TODO: usar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID de config
        return {"ok": True, "canal": "telegram", "mensaje": mensaje}

    @mcp.tool()
    def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
        """Envía un correo electrónico."""
        # TODO: usar SMTP config
        return {"ok": True, "canal": "email", "destinatario": destinatario}

    @mcp.tool()
    def alerta_stock_bajo(producto: str, stock_actual: int) -> dict:
        """Envía alerta por Telegram y email cuando un producto tiene stock bajo."""
        # TODO: combinar enviar_telegram + enviar_email
        return {"ok": True, "producto": producto, "stock_actual": stock_actual}
