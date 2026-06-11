from mcp.server.fastmcp import FastMCP
from server.tools import inventario, bar_barismo, restaurante, correo
from config import MCP_SERVER_HOST, MCP_SERVER_PORT

# Microservicio MCP: escucha en host/puerto (transporte SSE), no en stdio.
mcp = FastMCP("gastrosena", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)

# Registrar herramientas por módulo.
# Consulta (SOLO LECTURA):
inventario.register(mcp)
bar_barismo.register(mcp)
restaurante.register(mcp)

# Correo: ÚNICA acción con efecto hacia afuera. Expone enviar_email con guardrails
# (destinatarios autorizados por rol).
correo.register(mcp)

# Acciones de escritura aún deshabilitadas (stubs # TODO):
#   from server.tools import cocina, notifications
#   cocina.register(mcp)         # crear/actualizar comandas

if __name__ == "__main__":
    mcp.run(transport="sse")
