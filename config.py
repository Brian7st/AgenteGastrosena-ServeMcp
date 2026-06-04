from dotenv import load_dotenv
import os

load_dotenv()

# ── LLM (agnóstico de proveedor) ─────────────────
# El proveedor se decide por el prefijo de MODEL: "<proveedor>/<modelo>".
# Ej: anthropic/claude-sonnet-4-20250514 | openai/gpt-4o | google/gemini-2.0-flash
MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4-20250514")
LLM_PROVIDER = MODEL.split("/", 1)[0] if "/" in MODEL else "anthropic"

# Mapa proveedor -> variable de entorno con su API key (la lee mirascope).
_PROVIDER_API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "anthropic-beta": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "together": "TOGETHER_API_KEY",
    # ollama / mlx corren local: no requieren API key.
}

# ── Telegram ─────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ── Email (SMTP) ──────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

# ── Base de datos ─────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

# ── MCP ───────────────────────────────────────────
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "localhost")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8000"))

# ── API HTTP (la consume el frontend Angular) ─────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "9000"))
# Orígenes permitidos por CORS, separados por coma. Default: dev server de Angular.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",")
    if o.strip()
]

# ── Validación al arrancar ────────────────────────
def validate_llm():
    """Valida que exista la API key del proveedor elegido en MODEL.

    Proveedores locales (ollama, mlx) no requieren key.
    """
    key_env = _PROVIDER_API_KEY_ENV.get(LLM_PROVIDER)
    if key_env and not os.getenv(key_env):
        raise EnvironmentError(
            f"Falta {key_env} para el proveedor '{LLM_PROVIDER}' (MODEL={MODEL})."
        )
