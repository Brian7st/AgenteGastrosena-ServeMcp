 
import asyncio
import os
import sys
from mcp import StdioServerParameters
from mirascope import llm
from mirascope.llm.mcp import stdio_client
from mirascope.llm import call 
from agent.prompts import SYSTEM_PROMPT
from config import GOOGLE_API_KEY, MODEL, TEMPERATURE

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

MCP_SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-m", "server.main"],
)

MAX_ITER = 5




async def run_agent(user_message: str):
    async with stdio_client(MCP_SERVER) as client:
        tools = await client.list_tools()

        @call(
            MODEL,
            tools=[*tools],
            system=SYSTEM_PROMPT,
            call_params={"temperature": TEMPERATURE},
        )
        async def agent(message: str) -> str:
            return message

        historial = user_message

        iteration = 0
        while iteration < MAX_ITER:
            iteration += 1

            response = await agent(historial)

            if not response.tool_calls:
                texto = response.content[0].text if response.content else ""
                print(f"\nAgente: {texto}\n")
                break

            resultados = []
            for tool_call in response.tool_calls:
                args = tool_call.args if isinstance(tool_call.args, dict) else {}
                print(f"-> Tool: {tool_call.name} | args: {args}")

                
                result = await client.session.call_tool(tool_call.name, args)
                contenido = result.content[0].text if result.content else "sin resultado"

                resultados.append(f"Tool '{tool_call.name}' retorno: {contenido}")

            historial = (
                f"Pregunta original: {user_message}\n"
                f"Resultados:\n" + "\n".join(resultados) +
                "\nResponde al usuario basandote en estos resultados."
            )

        else:
            print("\nLimite de iteraciones alcanzado.\n")


async def main():
    print("=== Asistente GastroSENA ===")
    print("Escribe 'salir' para terminar\n")
    while True:
        mensaje = input("Tu: ").strip()
        if mensaje.lower() == "salir":
            break
        if mensaje:
            await run_agent(mensaje)


if __name__ == "__main__":
    asyncio.run(main())
