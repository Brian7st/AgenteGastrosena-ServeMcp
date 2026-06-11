from mcp.server.fastmcp import FastMCP
from server.tools import inventario, bar_barismo, restaurante, cocina, notifications
from config import MCP_SERVER_HOST, MCP_SERVER_PORT

# Microservicio MCP: escucha en host/puerto (transporte SSE), no en stdio.
mcp = FastMCP("gastrosena", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)

# Registrar herramientas por módulo
inventario.register(mcp)
bar_barismo.register(mcp)
restaurante.register(mcp)
cocina.register(mcp)
notifications.register(mcp)

if __name__ == "__main__":
    mcp.run(transport="sse")
