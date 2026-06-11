"""
Prueba MANUAL y aislada del envío de correo (sin pasar por el LLM ni el MCP).

Sirve para validar la configuración SMTP y los guardrails de destinatarios antes
de probar el flujo completo con el agente.

Uso (con el .venv activo y el .env configurado):
    python -m scripts.probar_email contadora "Asunto de prueba" "Cuerpo del mensaje"

Si no pasás argumentos, usa valores de ejemplo.
"""

import sys

from server.tools.correo import _resolver_destinatario, _enviar_smtp
from config import SMTP_USER, SMTP_PASSWORD, EMAIL_RECIPIENTS_BY_ROLE


def main() -> None:
    destinatario = sys.argv[1] if len(sys.argv) > 1 else "contadora"
    asunto = sys.argv[2] if len(sys.argv) > 2 else "Prueba GastroIA"
    cuerpo = sys.argv[3] if len(sys.argv) > 3 else "Este es un correo de prueba del asistente."

    # Probamos la lógica interna directo (sin pasar por el MCP ni el LLM).

    if not SMTP_USER or not SMTP_PASSWORD:
        print("[ERROR] Falta SMTP_USER / SMTP_PASSWORD en el .env")
        return
    if not EMAIL_RECIPIENTS_BY_ROLE:
        print("[ERROR] No hay destinatarios. Configurá EMAIL_RECIPIENTS_BY_ROLE en el .env")
        return

    try:
        destino = _resolver_destinatario(destinatario)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    print(f"-> Enviando a {destino} (rol/entrada: {destinatario})...")
    try:
        _enviar_smtp(destino, asunto, cuerpo)
    except Exception as e:  # noqa: BLE001 - es una prueba manual, queremos ver el detalle
        print(f"[ERROR] Falló el envío: {type(e).__name__}: {e}")
        return
    print("[OK] Correo enviado correctamente.")


if __name__ == "__main__":
    main()
