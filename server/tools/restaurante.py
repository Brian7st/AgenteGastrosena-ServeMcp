from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):

    @mcp.tool()
    def consultar_mesas() -> list:
        """Retorna el estado actual de todas las mesas (libre, ocupada, reservada)."""
        # TODO: conectar con base de datos
        return []

    @mcp.tool()
    def crear_reserva(nombre: str, fecha: str, hora: str, personas: int) -> dict:
        """Crea una reserva para el restaurante."""
        # TODO: conectar con base de datos
        return {"ok": True, "nombre": nombre, "fecha": fecha, "hora": hora, "personas": personas}

    @mcp.tool()
    def cerrar_mesa(mesa: int) -> dict:
        """Cierra una mesa y genera el resumen de consumo."""
        # TODO: conectar con base de datos
        return {"ok": True, "mesa": mesa, "total": 0}
