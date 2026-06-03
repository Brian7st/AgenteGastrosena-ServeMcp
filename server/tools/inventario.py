from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):

    @mcp.tool()
    def consultar_stock(producto: str) -> dict:
        """Consulta el stock actual de un producto en inventario."""
        # TODO: conectar con base de datos
        return {"producto": producto, "stock": 0, "unidad": "unidades"}

    @mcp.tool()
    def actualizar_stock(producto: str, cantidad: int, operacion: str = "entrada") -> dict:
        """Registra entrada o salida de stock. operacion: 'entrada' | 'salida'"""
        # TODO: conectar con base de datos
        return {"ok": True, "producto": producto, "cantidad": cantidad, "operacion": operacion}

    @mcp.tool()
    def listar_productos_bajos(umbral: int = 10) -> list:
        """Lista productos con stock por debajo del umbral dado."""
        # TODO: conectar con base de datos
        return []
