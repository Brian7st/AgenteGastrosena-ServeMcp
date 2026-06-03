from mirascope.mcp import MCPClient
from mirascope.anthropic import AnthropicCall
from agent.prompts import SYSTEM_PROMPT
from config import MCP_SERVER_HOST, MCP_SERVER_PORT, MODEL


async def run_agent(user_message: str):
    """Ciclo agéntico principal de Gastrosena."""
    async with MCPClient(host=MCP_SERVER_HOST, port=MCP_SERVER_PORT) as client:
        tools = await client.get_tools()

        messages = [{"role": "user", "content": user_message}]

        while True:
            response = await AnthropicCall(
                model=MODEL,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            ).call_async()

            # Si no hay tool calls, terminamos
            if not response.tool_calls:
                print(response.content)
                break

            # Ejecutar cada tool call
            for tool_call in response.tool_calls:
                result = await client.call_tool(tool_call.name, tool_call.arguments)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": str(result)})


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_agent("¿Cuáles son las comandas pendientes?"))
