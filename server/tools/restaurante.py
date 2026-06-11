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
AccionPedido = Literal["confirmar", "entregar", "cancelar"]

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


def _cuerpo(**kwargs) -> Optional[dict]:
    """Arma el JSON body descartando campos vacíos; None si no queda nada."""
    body = {k: v for k, v in kwargs.items() if v is not None and v != ""}
    return body or None


def _enviar(metodo: str, path: str, body: Optional[dict] = None) -> dict:
    """Único punto de salida para escrituras (POST/PUT/PATCH)."""
    resp = _session.request(
        metodo, f"{API_BASE_URL}{API_PREFIX}{path}", json=body, timeout=TIMEOUT
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


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

    # ========== ESCRITURA (POST / PUT / PATCH) ==========

    # ---------- FACTURAS ----------
    @mcp.tool()
    @_manejar_errores
    def facturar_pedido(pedido_id: str, metodo_pago: str, propina: Optional[float] = None) -> dict:
        """Factura un pedido entregado. metodo_pago: EFECTIVO|TARJETA|TRANSFERENCIA."""
        body = _cuerpo(pedidoId=pedido_id, metodoPago=metodo_pago, propina=propina)
        return {"ok": True, "factura": _compactar(_enviar("POST", "/facturas", body))}

    @mcp.tool()
    @_manejar_errores
    def anular_factura(id: str, motivo: str) -> dict:
        """Anula una factura por ID (requiere motivo)."""
        body = _cuerpo(motivo=motivo)
        return {"ok": True, "factura": _compactar(_enviar("PATCH", f"/facturas/{id}/anular", body))}

    # ---------- CAJA ----------
    @mcp.tool()
    @_manejar_errores
    def abrir_sesion_caja(monto_inicial: float) -> dict:
        """Abre una sesión de caja con un monto inicial."""
        body = _cuerpo(montoInicial=monto_inicial)
        return {"ok": True, "sesion": _compactar(_enviar("POST", "/caja/sesion/abrir", body))}

    @mcp.tool()
    @_manejar_errores
    def cerrar_sesion_caja(id: str, monto_final: Optional[float] = None) -> dict:
        """Cierra una sesión de caja por ID; monto_final opcional para arqueo."""
        body = _cuerpo(montoFinal=monto_final)
        return {"ok": True, "sesion": _compactar(_enviar("PATCH", f"/caja/sesion/{id}/cerrar", body))}

    # ---------- PEDIDOS ----------
    @mcp.tool()
    @_manejar_errores
    def cambiar_estado_pedido(id: str, accion: AccionPedido, motivo: Optional[str] = None) -> dict:
        """Transiciona un pedido: confirmar (envía a cocina/bar), entregar o cancelar (motivo)."""
        body = _cuerpo(motivo=motivo) if accion == "cancelar" else None
        return {"ok": True, "pedido": _compactar(_enviar("PATCH", f"/pedidos/{id}/{accion}", body))}

    # ---------- MESAS ----------
    @mcp.tool()
    @_manejar_errores
    def crear_mesa(numero: int, capacidad: int, ubicacion: Optional[str] = None) -> dict:
        """Crea una mesa (número y capacidad; ubicación opcional)."""
        body = _cuerpo(numero=numero, capacidad=capacidad, ubicacion=ubicacion)
        return {"ok": True, "mesa": _compactar(_enviar("POST", "/mesas", body))}

    @mcp.tool()
    @_manejar_errores
    def cambiar_disponibilidad_mesa(id: str, activa: bool) -> dict:
        """Activa o desactiva una mesa."""
        accion = "activar" if activa else "desactivar"
        return {"ok": True, "mesa": _compactar(_enviar("PATCH", f"/mesas/{id}/{accion}"))}

    @mcp.tool()
    @_manejar_errores
    def cambiar_estado_mesa(id: str, estado: EstadoMesa) -> dict:
        """Cambia manualmente el estado de una mesa (LIBRE|OCUPADA|POR_PAGAR)."""
        body = _cuerpo(estado=estado)
        return {"ok": True, "mesa": _compactar(_enviar("PATCH", f"/mesas/{id}/estado", body))}
