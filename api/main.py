"""
API HTTP que expone el agente Gastrosena al frontend Angular.

Flujo:
    Angular  --POST /api/agente {mensaje}-->  esta API  -->  run_agent()
              -->  MCP server (SSE)  -->  microservicios backend
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.main import run_agent, stream_agent
from config import CORS_ORIGINS

app = FastAPI(title="Gastrosena Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConsultaRequest(BaseModel):
    mensaje: str


class ConsultaResponse(BaseModel):
    respuesta: str


@app.get("/api/health")
async def health() -> dict:
    """Healthcheck simple para readiness/liveness."""
    return {"ok": True}


@app.post("/api/agente", response_model=ConsultaResponse)
async def consultar_agente(payload: ConsultaRequest) -> ConsultaResponse:
    """Recibe un mensaje del usuario, corre el ciclo agéntico y devuelve la respuesta."""
    mensaje = payload.mensaje.strip()
    if not mensaje:
        raise HTTPException(status_code=400, detail="El campo 'mensaje' no puede estar vacío.")
    try:
        respuesta = await run_agent(mensaje)
    except Exception as e:  # noqa: BLE001 - traducimos cualquier fallo a 502 hacia el front
        raise HTTPException(status_code=502, detail=f"Fallo del agente: {e}") from e
    return ConsultaResponse(respuesta=respuesta or "")


@app.post("/api/agente/stream")
async def consultar_agente_stream(payload: ConsultaRequest) -> StreamingResponse:
    """Igual que /api/agente pero responde en streaming (SSE) chunk a chunk.

    Cada evento es una línea `data: {...}\\n\\n`:
      {"delta": "texto"}  -> fragmento de respuesta
      {"done": true}      -> fin del stream
      {"error": "..."}    -> fallo durante el ciclo agéntico
    """
    mensaje = payload.mensaje.strip()
    if not mensaje:
        raise HTTPException(status_code=400, detail="El campo 'mensaje' no puede estar vacío.")

    async def event_stream():
        try:
            async for chunk in stream_agent(mensaje):
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:  # noqa: BLE001 - reportamos el fallo dentro del stream
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    from config import API_HOST, API_PORT

    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
