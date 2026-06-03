from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):

    @mcp.tool()
    def crear_pedido_barra(mesa: int, bebidas: list[str]) -> dict:
        """Crea un pedido de bar o barismo para una mesa."""
        # TODO: conectar con base de datos
        return {"ok": True, "mesa": mesa, "bebidas": bebidas, "estado": "pendiente"}

    @mcp.tool()
    def listar_recetas(tipo: str = "todos") -> list:
        """Lista recetas disponibles. tipo: 'cafe' | 'cocteleria' | 'todos'"""
        # TODO: conectar con base de datos
        return []

    @mcp.tool()
    def registrar_merma(insumo: str, cantidad: float, motivo: str) -> dict:
        """Registra una merma de insumo en barra o barismo."""
        # TODO: conectar con base de datos
        return {"ok": True, "insumo": insumo, "cantidad": cantidad, "motivo": motivo}
