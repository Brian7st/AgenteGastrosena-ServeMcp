# Gastrosena — Agente MCP

Asistente de **consulta** (solo lectura) para el sistema de gestión de restaurantes Gastrosena.
Un agente LLM responde preguntas en lenguaje natural consultando los microservicios
del SENA a través de un servidor MCP.

## Arquitectura

```
Angular (:4200)
   │  POST /api/agente  |  POST /api/agente/stream (SSE)
   ▼
API HTTP — FastAPI (:9000)
   │  run_agent() / stream_agent()
   ▼
Agente LLM (mirascope v2, multi-proveedor)
   │  list_tools() + tool calls  (transporte SSE)
   ▼
Servidor MCP (:8000)
   │  HTTP a los backends
   ▼
Microservicios Spring
   ├─ Inventario   :8081
   ├─ Bar/Barismo  :8086
   └─ Restaurante  :8080
```

> **Alcance actual:** el agente es **solo lectura**. Las tools de escritura
> (cocina, notificaciones) están deshabilitadas en `server/main.py`.

---

## Requisitos

- Python 3.11+
- Los microservicios backend corriendo (al menos el que vayas a consultar)
- Una API key de un proveedor LLM (Google, Anthropic, OpenAI, etc.)

---

## Instalación

```bash
# 1. (Recomendado) entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows PowerShell
# source .venv/bin/activate     # Linux/macOS

# 2. Dependencias
pip install -r requirements.txt
```

> Si vas a usar un proveedor distinto de Google/Anthropic, instalá su extra:
> `pip install "mirascope[openai]"`.

---

## Configuración: archivo `.env`

Creá un archivo llamado `.env` en la **raíz del proyecto** (al lado de `config.py`).
No se versiona (está en `.gitignore`). **Nunca pongas claves en el código.**

```bash
# ── LLM (el proveedor va en el prefijo de MODEL) ──
# Ejemplos: google/gemini-3.5-flash | anthropic/claude-sonnet-4-20250514 | openai/gpt-4o
MODEL=google/gemini-3.5-flash

# API key SOLO del proveedor que uses en MODEL:
GOOGLE_API_KEY=tu-key-de-google
# ANTHROPIC_API_KEY=...
# OPENAI_API_KEY=...

# ── Backends Spring (microservicios SENA) ──
API_BASE_URL=http://localhost:8081        # Inventario
BAR_API_BASE_URL=http://localhost:8086    # Bar / Barismo
REST_API_BASE_URL=http://localhost:8080   # Restaurante

# Tokens opcionales (si los backends piden Authorization: Bearer)
# API_TOKEN=
# BAR_API_TOKEN=
# REST_API_TOKEN=

# ── Servidor MCP ──
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8000

# ── API HTTP (la consume Angular) ──
API_HOST=0.0.0.0
API_PORT=9000
CORS_ORIGINS=http://localhost:4200        # orígenes permitidos, separados por coma
```

### Tabla de variables

| Variable | Obligatoria | Default | Descripción |
|----------|:-----------:|---------|-------------|
| `MODEL` | sí | `anthropic/claude-sonnet-4-20250514` | `proveedor/modelo` |
| `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | según `MODEL` | — | key del proveedor elegido |
| `API_BASE_URL` | recomendada | `http://localhost:8081` | backend de inventario |
| `BAR_API_BASE_URL` | recomendada | `http://localhost:8086` | backend de bar/barismo |
| `REST_API_BASE_URL` | recomendada | `http://localhost:8080` | backend de restaurante |
| `API_TOKEN` / `BAR_API_TOKEN` / `REST_API_TOKEN` | no | — | bearer token si el backend lo exige |
| `MCP_SERVER_HOST` | no | `localhost` | host del servidor MCP |
| `MCP_SERVER_PORT` | no | `8000` | puerto del servidor MCP |
| `API_HOST` | no | `0.0.0.0` | host de la API HTTP |
| `API_PORT` | no | `9000` | puerto de la API HTTP |
| `CORS_ORIGINS` | no | `http://localhost:4200` | orígenes permitidos (coma) |

> **Proveedores soportados:** `google`, `anthropic`, `openai`, `openrouter`,
> `together`, `ollama` y `mlx` (estos dos últimos locales, sin API key).
> Para cambiar de proveedor: cambiá `MODEL`, poné su key y, si hace falta,
> instalá su extra de mirascope.

---

## Cómo levantarlo

Cada servidor queda corriendo en su propia terminal.

```bash
# Terminal 1 — Servidor MCP (las tools)
python -m server.main

# Terminal 2 — API HTTP + agente LLM
python -m api.main
```

Verificá que la API esté viva:

```bash
curl http://localhost:9000/api/health
# -> {"ok": true}
```

Para **detener** cualquiera de los dos: `Ctrl + C` en su terminal.

### Probar el agente por consola (sin Angular)

```bash
python -m agent.main
```

---

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET`  | `/api/health` | Healthcheck (`{"ok": true}`) |
| `POST` | `/api/agente` | Consulta simple. Body: `{"mensaje": "..."}` → `{"respuesta": "..."}` |
| `POST` | `/api/agente/stream` | Igual pero en streaming SSE (`data: {"delta": "..."}` … `data: {"done": true}`) |

---

## Integración con Angular

En `proxy.conf.json`, agregá la ruta del agente **antes** del catch-all `/api`:

```json
{
  "/api/agente": {
    "target": "http://localhost:9000",
    "secure": false,
    "changeOrigin": true
  }
}
```

> El endpoint `/api/agente/stream` es POST: para consumirlo en vivo usá
> `fetch` + `ReadableStream` (la API nativa `EventSource` solo soporta GET).
> Las respuestas vienen en Markdown; renderizalas con `ngx-markdown` para que
> se vean con negritas y listas.

---

## Estructura del proyecto

```
agent/        # ciclo agéntico (run_agent, stream_agent) + system prompt
api/          # API HTTP FastAPI (lo que consume Angular)
server/       # servidor MCP y tools por dominio
  tools/
    inventario.py    # solo lectura  ✅ registrada
    bar_barismo.py   # solo lectura  ✅ registrada
    restaurante.py   # solo lectura  ✅ registrada
    cocina.py        # acciones      ⛔ deshabilitada (stub)
    notifications.py # acciones      ⛔ deshabilitada (stub)
config.py     # carga del .env y validación del proveedor LLM
```
