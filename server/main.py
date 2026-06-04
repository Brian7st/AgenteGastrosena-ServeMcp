from mcp.server.fastmcp import FastMCP
from server.tools import inventario, bar_barismo, restaurante
from config import MCP_SERVER_HOST, MCP_SERVER_PORT

# Microservicio MCP: escucha en host/puerto (transporte SSE), no en stdio.
mcp = FastMCP("gastrosena", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)

# Registrar herramientas por módulo (SOLO LECTURA por ahora).
inventario.register(mcp)
bar_barismo.register(mcp)
restaurante.register(mcp)

# Acciones deshabilitadas mientras el agente sea solo de consulta.
# Son stubs (# TODO) y exponen tools de escritura que el LLM no debe ejecutar:
#   from server.tools import cocina, notifications
#   cocina.register(mcp)         # crear/actualizar comandas
#   notifications.register(mcp)  # enviar telegram/email

if __name__ == "__main__":
    mcp.run(transport="sse")
