from mcp.server.fastmcp import FastMCP
from server.tools import inventario, cocina, bar_barismo, restaurante, notifications

mcp = FastMCP("gastrosena")

# Registrar herramientas por módulo
inventario.register(mcp)
cocina.register(mcp)
bar_barismo.register(mcp)
restaurante.register(mcp)
notifications.register(mcp)

if __name__ == "__main__":
    mcp.run()
