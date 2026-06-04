"""
Servidor MCP de integración con el backend ga-ms-inventario (SENA).
Expone consultas de solo-lectura sobre catálogo, inventario, presupuesto,
compras y operaciones de instructores.

Endpoints verificados contra los @RequestMapping de los controllers Spring Boot.
Todas las rutas cuelgan de /api/v1 (ver API_PREFIX).
"""

import functools
import os
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

# --- Configuración: desde el entorno, con default local (inventario = 8081) ---
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8081").rstrip("/")
API_PREFIX = "/api/v1"                 # prefijo común de TODOS los controllers
API_TOKEN = os.environ.get("API_TOKEN")  # opcional, listo para cuando el backend lo pida
TIMEOUT = 10

# --- Session única: reusa conexión TCP y centraliza headers/auth ---
_session = requests.Session()
if API_TOKEN:
    _session.headers["Authorization"] = f"Bearer {API_TOKEN}"


def _get(path: str, params: Optional[dict] = None) -> dict:
    """Punto único de salida HTTP. Aquí viven el prefijo, el timeout y el raise."""
    resp = _session.get(f"{API_BASE_URL}{API_PREFIX}{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _manejar_errores(fn):
    """Traduce excepciones a respuestas honestas (no todo es 'error de conexión')."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:                       # regla de negocio (código inexistente)
            return {"ok": False, "error": str(e)}
        except requests.HTTPError as e:
            return {"ok": False, "error": f"La API respondió {e.response.status_code}"}
        except requests.RequestException as e:
            return {"ok": False, "error": f"Fallo de conexión: {e}"}
    return wrapper


def _buscar_productos(params: dict) -> list:
    """Fuente única de verdad para GET /catalog/productos (respuesta paginada)."""
    datos = _get("/catalog/productos", params)
    return datos.get("contenido", [])


def _uuid_por_codigo(codigo_sena: str) -> str:
    """Resuelve el UUID interno a partir del código SENA. Regla de negocio oculta al LLM."""
    productos = _buscar_productos({"codigoSena": codigo_sena})
    if productos:
        return productos[0]["id"]
    raise ValueError(f"El código SENA '{codigo_sena}' no existe en el catálogo.")


def register(mcp: FastMCP):

    # ---------- CATÁLOGO ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_catalogo(
        codigo_sena: Optional[str] = None,
        nombre: Optional[str] = None,
        categoria: Optional[str] = None,
    ) -> dict:
        """Busca bienes en el catálogo del SENA por código SENA, nombre o categoría."""
        params = {}
        if codigo_sena:
            params["codigoSena"] = codigo_sena
        if nombre:
            params["nombre"] = nombre
        if categoria:
            params["categoria"] = categoria
        productos = _buscar_productos(params)
        return {"ok": True, "total": len(productos), "datos": productos}

    # ---------- INVENTARIO (una tool = una intención) ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_existencias(codigo_sena: str) -> dict:
        """Devuelve el stock físico actual de un bien por su código SENA."""
        uuid = _uuid_por_codigo(codigo_sena)
        stock = _get(f"/inventory/existencias/{uuid}")
        stock.pop("productoId", None)
        return {"ok": True, "codigo_sena": codigo_sena, "stock": stock}

    @mcp.tool()
    @_manejar_errores
    def consultar_kardex(codigo_sena: str) -> dict:
        """Devuelve el historial valorizado de movimientos (Kardex) de un bien."""
        uuid = _uuid_por_codigo(codigo_sena)
        kardex = _get("/reporting/kardex", {"productoId": uuid})
        return {"ok": True, "codigo_sena": codigo_sena, "kardex": kardex}

    @mcp.tool()
    @_manejar_errores
    def consultar_alertas_stock() -> dict:
        """Devuelve los bienes con existencias por debajo del mínimo (alertas globales)."""
        return {"ok": True, "alertas": _get("/inventory/existencias/bajo-minimo")}

    # ---------- PRESUPUESTO ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_resumen_presupuesto(vigencia: int) -> dict:
        """Saldos presupuestales globales de una vigencia."""
        return {"ok": True, "resumen": _get("/budget/presupuestos/resumen", {"vigencia": vigencia})}

    @mcp.tool()
    @_manejar_errores
    def consultar_ejecucion_presupuesto(
        ficha_id: Optional[str] = None,
        vigencia: Optional[int] = None,
    ) -> dict:
        """Ejecución presupuestal (rubros comprometidos), filtrable por ficha y vigencia."""
        params = {}
        if ficha_id:
            params["fichaId"] = ficha_id
        if vigencia:
            params["vigencia"] = vigencia
        return {"ok": True, "ejecucion": _get("/reporting/ejecucion-presupuestal", params)}

    # ---------- COMPRAS / FACTURACIÓN ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_facturas(
        nit_proveedor: Optional[str] = None,
        estado: Optional[str] = None,
    ) -> dict:
        """Lista facturas filtrando por estado (REGISTRADA|VERIFICADA|PAGADA|ANULADA) o NIT del proveedor."""
        params = {}
        if nit_proveedor:
            params["proveedorNit"] = nit_proveedor
        if estado:
            params["estado"] = estado
        datos = _get("/sourcing/facturas", params)
        return {"ok": True, "facturas": datos.get("contenido", [])}

    @mcp.tool()
    @_manejar_errores
    def consultar_resumen_compras() -> dict:
        """Resumen de compras: montos totales pagados vs anulados."""
        return {"ok": True, "resumen_compras": _get("/sourcing/facturas/resumen")}

    # ---------- OPERACIONES DE INSTRUCTORES ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_alertas(destinatario_id: Optional[str] = None) -> dict:
        """Resumen de alertas, filtrable por destinatario (solo acepta destinatarioId)."""
        params = {"destinatarioId": destinatario_id} if destinatario_id else {}
        return {"ok": True, "datos": _get("/reporting/alertas/resumen", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_consumos(
        instructor_id: Optional[str] = None,
        ficha_id: Optional[str] = None,
    ) -> dict:
        """Consumos registrados, filtrables por instructor o ficha."""
        params = {}
        if instructor_id:
            params["instructorId"] = instructor_id
        if ficha_id:
            params["fichaId"] = ficha_id
        return {"ok": True, "datos": _get("/reporting/consumo", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_requisiciones(
        instructor_id: Optional[str] = None,
        ficha_id: Optional[str] = None,
        estado: Optional[str] = None,
    ) -> dict:
        """Requisiciones de legalización, filtrables por instructor, ficha o estado."""
        params = {}
        if instructor_id:
            params["instructorId"] = instructor_id
        if ficha_id:
            params["fichaId"] = ficha_id
        if estado:
            params["estado"] = estado
        return {"ok": True, "datos": _get("/legalization/requisiciones", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_conciliaciones(estado: str = "CERRADA") -> dict:
        """Conciliaciones, filtrables por estado (por defecto CERRADA)."""
        return {"ok": True, "datos": _get("/reconciliation/conciliaciones", {"estado": estado})}


if __name__ == "__main__":
    servidor = FastMCP("IntegracionBackendSENA")
    register(servidor)
    servidor.run()