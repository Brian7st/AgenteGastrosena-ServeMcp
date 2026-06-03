from dotenv import load_dotenv
import os

load_dotenv()

# ── LLM ──────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "openai/llama-3.3-70b-versatile"
TEMPERATURE = 0.3

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


# ── Validación al arrancar ────────────────────────
def validate():
    required = {
        "GROQ_API_KEY": GROQ_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "DATABASE_URL": DATABASE_URL,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"Variables de entorno faltantes: {', '.join(missing)}")
