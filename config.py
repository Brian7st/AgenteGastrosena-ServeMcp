from dotenv import load_dotenv
import os

load_dotenv()

# ── LLM ──────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("MODEL", "claude-sonnet-4-20250514")

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

# ── Validación al arrancar ────────────────────────
def validate():
    required = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "DATABASE_URL": DATABASE_URL,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"Variables de entorno faltantes: {', '.join(missing)}")
