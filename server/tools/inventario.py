from mcp.server.fastmcp import FastMCP
import httpx
from fastmcp import FastMCP

BASE_URL = "http://localhost:8081/api/v1"


def register(mcp: FastMCP):

    @mcp.tool()
    async def consultar_stock(producto_id: str) -> dict:
        """Consulta el stock actual de un producto por su ID o código SENA.

        Args:
            producto_id: El código SENA o ID del producto (ej. 'PROD-001').
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/inventory/existencias/{producto_id}")
            if response.status_code == 404:
                return {"error": f"Producto '{producto_id}' no encontrado"}
            return response.json()

    @mcp.tool()
    async def listar_productos_bajos() -> list:
        """Lista todos los productos que están por debajo del stock mínimo."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/inventory/existencias/bajo-minimo")
            return response.json()

    @mcp.tool()
    async def listar_catalogo() -> list:
        """Lista todos los productos del catálogo con sus existencias actuales."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/catalog/productos")
            return response.json()

    @mcp.tool()
    async def registrar_entrada(
        producto_id: str,
        cantidad: float,
        precio_unitario: float,
        factura_id: str = None,
        proveedor_nit: str = None,
        gil_id: str = None,
        conciliacion_id: str = None,
    ) -> dict:
        """Registra una entrada de stock para un producto.

        Args:
            producto_id: Código SENA del producto (ej. 'PROD-001').
            cantidad: Cantidad a ingresar al inventario.
            precio_unitario: Precio unitario del producto.
            factura_id: ID de la factura asociada (opcional).
            proveedor_nit: NIT del proveedor (opcional).
            gil_id: ID del GIL asociado (opcional).
            conciliacion_id: ID de conciliación (opcional).
        """
        body = {
            "productoId": producto_id,
            "cantidad": cantidad,
            "precioUnitario": precio_unitario,
            "facturaId": factura_id,
            "proveedorNit": proveedor_nit,
            "gilId": gil_id,
            "conciliacionId": conciliacion_id,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/inventory/movimientos/entrada", json=body
            )
            if response.status_code not in (200, 201):
                return {"error": response.text, "status": response.status_code}
            return response.json()

    @mcp.tool()
    async def registrar_salida(
        producto_id: str,
        cantidad: float,
        instructor_id: str,
        categoria: str,
        requisicion_id: str = None,
    ) -> dict:
        """Registra una salida de stock para un producto.

        Args:
            producto_id: Código SENA del producto (ej. 'PROD-001').
            cantidad: Cantidad a retirar del inventario.
            instructor_id: ID del instructor que solicita la salida.
            categoria: Categoría del producto. Valores: 'ABARROTES', 'LACTEOS', 'FRUTAS_Y_VEGETALES', 'CARNES_PESCADOS_MARISCOS'.
            requisicion_id: ID de la requisición asociada (opcional).
        """
        categorias_validas = ["ABARROTES", "LACTEOS", "FRUTAS_Y_VEGETALES", "CARNES_PESCADOS_MARISCOS"]
        if categoria not in categorias_validas:
            return {"error": f"Categoría inválida. Use: {categorias_validas}"}

        body = {
            "productoId": producto_id,
            "cantidad": cantidad,
            "requisicionId": requisicion_id,
            "instructorId": instructor_id,
            "categoria": categoria,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/inventory/movimientos/salida", json=body
            )
            if response.status_code not in (200, 201):
                return {"error": response.text, "status": response.status_code}
            return response.json()

    @mcp.tool()
    async def listar_movimientos() -> list:
        """Lista todos los movimientos de inventario (entradas y salidas)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/inventory/movimientos/todos")
            return response.json()