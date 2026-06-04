from collections.abc import AsyncIterator

import mirascope.llm as llm
from mirascope.llm.mcp import sse_client

from agent.prompts import SYSTEM_PROMPT
from config import MCP_SERVER_HOST, MCP_SERVER_PORT, MODEL, validate_llm

# El server MCP corre como microservicio (transporte SSE) y expone /sse.
MCP_SERVER_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"


async def run_agent(user_message: str):
    """Ciclo agéntico principal de Gastrosena."""
    validate_llm()  # falla temprano si falta la API key del proveedor elegido
    async with sse_client(MCP_SERVER_URL) as client:
        tools = await client.list_tools()
        model = llm.model(MODEL)

        messages = [
            llm.SystemMessage(content=SYSTEM_PROMPT),
            llm.UserMessage(content=user_message),
        ]
        response = await model.call_async(messages, tools=tools)

        # Loop agéntico: ejecutar las tool calls y reanudar con sus resultados,
        # hasta que el modelo deje de pedir herramientas.
        outputs = await response.execute_tools()
        while outputs:
            response = await response.resume(outputs)
            outputs = await response.execute_tools()

        return response.text


async def stream_agent(user_message: str) -> AsyncIterator[str]:
    """Igual que run_agent pero emite el texto en chunks a medida que llega.

    Mantiene el ciclo agéntico: por cada turno transmite el texto del modelo,
    ejecuta las tool calls y reanuda, hasta que no pida más herramientas.
    """
    validate_llm()
    async with sse_client(MCP_SERVER_URL) as client:
        tools = await client.list_tools()
        model = llm.model(MODEL)

        messages = [
            llm.SystemMessage(content=SYSTEM_PROMPT),
            llm.UserMessage(content=user_message),
        ]
        stream = model.stream_async(messages, tools=tools)

        while True:
            async for chunk in stream.text_stream():
                yield chunk
            outputs = await stream.execute_tools()
            if not outputs:
                break
            stream = stream.resume(outputs)


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(run_agent("¿Cuáles son las comandas pendientes?")))
