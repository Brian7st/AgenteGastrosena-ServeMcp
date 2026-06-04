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

        print(response.text)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_agent("¿Cuáles son las comandas pendientes?"))
