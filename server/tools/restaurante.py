"""
MCP de integración con el microservicio de Restaurante. Solo lectura.
Facturas, caja, reportes, pedidos y mesas.
Rutas verificadas contra los @RequestMapping; todas cuelgan de /api.
"""

import functools
import os
from typing import Literal, Optional

import requests
from mcp.server.fastmcp import FastMCP

# --- Config: propia del micro de restaurante (host independiente) ---
API_BASE_URL = os.environ.get("REST_API_BASE_URL", "http://localhost:8080").rstrip("/")
API_PREFIX = "/api"
API_TOKEN = os.environ.get("REST_API_TOKEN")
TIMEOUT = 10
MAX_ITEMS = 50                               # tope de filas: protege el contexto del LLM

EstadoMesa = Literal["LIBRE", "OCUPADA", "POR_PAGAR"]

_session = requests.Session()
if API_TOKEN:
    _session.headers["Authorization"] = f"Bearer {API_TOKEN}"


def _get(path: str, params: Optional[dict] = None) -> dict:
    """Único punto de salida HTTP: prefijo, timeout y raise."""
    resp = _session.get(f"{API_BASE_URL}{API_PREFIX}{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


def _manejar_errores(fn):
    """Traduce excepciones a respuestas honestas."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except requests.HTTPError as e:
            return {"ok": False, "error": f"La API respondió {e.response.status_code}"}
        except requests.RequestException as e:
            return {"ok": False, "error": f"Fallo de conexión: {e}"}
    return wrapper


def _compactar(dato):
    """Quita claves null/vacías para ahorrar tokens; no cambia la forma del dato."""
    if isinstance(dato, list):
        return [_compactar(x) for x in dato]
    if isinstance(dato, dict):
        return {k: _compactar(v) for k, v in dato.items() if v is not None and v != ""}
    return dato


def _lista(path: str, params: Optional[dict] = None) -> dict:
    """Endpoints de lista: compacta, recorta a MAX_ITEMS y reporta total + truncado."""
    datos = _compactar(_get(path, params))
    if not isinstance(datos, list):
        return {"total": 0, "items": [], "truncado": False}
    return {"total": len(datos), "items": datos[:MAX_ITEMS], "truncado": len(datos) > MAX_ITEMS}


def register(mcp: FastMCP):

    # ---------- FACTURAS ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_factura(id: Optional[str] = None, numero: Optional[str] = None) -> dict:
        """Factura por ID o por número (ej: FAC-20260530-AB12CD34)."""
        if id:
            ruta = f"/facturas/{id}"
        elif numero:
            ruta = f"/facturas/numero/{numero}"
        else:
            raise ValueError("Indica 'id' o 'numero'.")
        return {"ok": True, "factura": _compactar(_get(ruta))}

    @mcp.tool()
    @_manejar_errores
    def listar_facturas_sesion(sesion_id: str) -> dict:
        """Facturas de una sesión de caja."""
        return {"ok": True, **_lista(f"/facturas/sesion/{sesion_id}")}

    # ---------- CAJA ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_sesion_caja(sesion_id: Optional[str] = None) -> dict:
        """Sesión de caja: la activa si no se pasa ID, o el detalle de una (totales por método de pago)."""
        ruta = f"/caja/sesion/{sesion_id}" if sesion_id else "/caja/sesion/activa"
        return {"ok": True, "sesion": _compactar(_get(ruta))}

    # ---------- REPORTES ----------
    @mcp.tool()
    @_manejar_errores
    def reporte_resumen_sesion(sesion_id: str) -> dict:
        """Resumen de ventas de una sesión: totales, propinas, por método de pago y cancelados."""
        return {"ok": True, "resumen": _compactar(_get(f"/reportes/sesion/{sesion_id}/resumen"))}

    @mcp.tool()
    @_manejar_errores
    def reporte_mesas() -> dict:
        """Pedidos facturados y monto facturado por cada mesa."""
        return {"ok": True, **_lista("/reportes/mesas")}

    # ---------- PEDIDOS ----------
    @mcp.tool()
    @_manejar_errores
    def listar_pedidos(estado: Optional[str] = None, mesa_id: Optional[str] = None) -> dict:
        """Lista pedidos; opcional por estado (FACTURADO, CANCELADO, ENTREGADO...) o por mesa."""
        if estado:
            ruta = f"/pedidos/estado/{estado}"
        elif mesa_id:
            ruta = f"/pedidos/mesa/{mesa_id}"
        else:
            ruta = "/pedidos"
        return {"ok": True, **_lista(ruta)}

    @mcp.tool()
    @_manejar_errores
    def consultar_pedido(id: str) -> dict:
        """Detalle completo de un pedido con sus ítems."""
        return {"ok": True, "pedido": _compactar(_get(f"/pedidos/{id}"))}

    @mcp.tool()
    @_manejar_errores
    def listar_mis_pedidos() -> dict:
        """Pedidos del mesero autenticado."""
        return {"ok": True, **_lista("/pedidos/mis-pedidos")}

    # ---------- MESAS ----------
    @mcp.tool()
    @_manejar_errores
    def listar_mesas(estado: Optional[EstadoMesa] = None) -> dict:
        """Mesas activas; filtro opcional por estado."""
        ruta = f"/mesas/estado/{estado}" if estado else "/mesas"
        return {"ok": True, **_lista(ruta)}

    @mcp.tool()
    @_manejar_errores
    def consultar_mesa(id: str) -> dict:
        """Detalle de una mesa por ID."""
        return {"ok": True, "mesa": _compactar(_get(f"/mesas/{id}"))}
