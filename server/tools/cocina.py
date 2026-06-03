from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):

    @mcp.tool()
    def crear_comanda(mesa: int, items: list[str]) -> dict:
        """Crea una comanda para una mesa con los ítems solicitados."""
        # TODO: conectar con base de datos
        return {"ok": True, "mesa": mesa, "items": items, "estado": "pendiente"}

    @mcp.tool()
    def actualizar_estado_comanda(comanda_id: int, estado: str) -> dict:
        """Actualiza el estado de una comanda. estado: 'pendiente' | 'en_preparacion' | 'listo'"""
        # TODO: conectar con base de datos
        return {"ok": True, "comanda_id": comanda_id, "estado": estado}

    @mcp.tool()
    def listar_comandas_pendientes() -> list:
        """Retorna todas las comandas pendientes o en preparación."""
        # TODO: conectar con base de datos
        return []
