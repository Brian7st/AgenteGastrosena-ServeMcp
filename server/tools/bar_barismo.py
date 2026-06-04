"""
MCP de integración con gs-ms-cocina (Bar y Barismo). Solo lectura.
Comandas, estadísticas, cancelaciones, devoluciones, recetas y alertas de sala.
Rutas verificadas contra los @RequestMapping; todas cuelgan de /api.
"""

import os
from typing import Literal, Optional

import requests
from mcp.server.fastmcp import FastMCP

# --- Config: propia del micro de cocina (no comparte host con inventario) ---
API_BASE_URL = os.environ.get("BAR_API_BASE_URL", "http://localhost:8086").rstrip("/")
API_PREFIX = "/api"
API_TOKEN = os.environ.get("BAR_API_TOKEN")
TIMEOUT = 10
MAX_ITEMS = 50                               # tope de filas: protege el contexto del LLM

EstadoComanda = Literal["PENDIENTE", "EN_PREPARACION", "LISTO", "ENTREGADO", "CANCELADO"]
Rol = Literal["ADMIN", "BARISTA", "MESERO"]

_session = requests.Session()
if API_TOKEN:
    _session.headers["Authorization"] = f"Bearer {API_TOKEN}"


def _get(path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    """Único punto de salida HTTP: prefijo, timeout y raise."""
    resp = _session.get(
        f"{API_BASE_URL}{API_PREFIX}{path}", params=params, headers=headers, timeout=TIMEOUT
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


def _manejar_errores(fn):
    """Traduce excepciones a respuestas honestas."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except requests.HTTPError as e:
            return {"ok": False, "error": f"La API respondió {e.response.status_code}"}
        except requests.RequestException as e:
            return {"ok": False, "error": f"Fallo de conexión: {e}"}
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _filtros(**kwargs) -> dict:
    """Query string sin filtros vacíos."""
    return {k: v for k, v in kwargs.items() if v is not None and v != ""}


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

    # ---------- COMANDAS ----------
    @mcp.tool()
    @_manejar_errores
    def listar_comandas(estado: Optional[EstadoComanda] = None) -> dict:
        """Lista comandas; filtro opcional por estado."""
        ruta = f"/barybarismo/comandas/estado/{estado}" if estado else "/barybarismo/comandas"
        return {"ok": True, **_lista(ruta)}

    @mcp.tool()
    @_manejar_errores
    def consultar_comanda(id_comanda: str) -> dict:
        """Detalle de una comanda por ID."""
        return {"ok": True, "comanda": _compactar(_get(f"/barybarismo/comandas/{id_comanda}"))}

    @mcp.tool()
    @_manejar_errores
    def consultar_tiempo_comanda(id_comanda: str) -> dict:
        """Tiempo de preparación (inicio, fin, duración) de una comanda."""
        return {"ok": True, "tiempo": _compactar(_get(f"/barybarismo/comandas/{id_comanda}/tiempo"))}

    # ---------- ESTADÍSTICAS ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_promedio_preparacion() -> dict:
        """Tiempo promedio de preparación por bebida."""
        return {"ok": True, "promedios": _compactar(_get("/barybarismo/estadisticas/promedio"))}

    @mcp.tool()
    @_manejar_errores
    def consultar_estadisticas_diarias(fecha: Optional[str] = None) -> dict:
        """Resumen diario (total y tiempo promedio). fecha=YYYY-MM-DD; default hoy."""
        datos = _get("/barybarismo/estadisticas/diarias", _filtros(fecha=fecha))
        return {"ok": True, "estadisticas": _compactar(datos)}

    @mcp.tool()
    @_manejar_errores
    def consultar_estadisticas_devoluciones(
        inicio: Optional[str] = None,
        fin: Optional[str] = None,
        id_barista: Optional[str] = None,
    ) -> dict:
        """Estadísticas de devoluciones; filtros opcionales por fechas ISO y barista."""
        params = _filtros(inicio=inicio, fin=fin, idBarista=id_barista)
        return {"ok": True, "estadisticas": _compactar(_get("/barybarismo/estadisticas/devoluciones", params))}

    # ---------- CANCELACIONES ----------
    @mcp.tool()
    @_manejar_errores
    def listar_pedidos_cancelados(
        inicio: Optional[str] = None,
        fin: Optional[str] = None,
        id_usuario: Optional[int] = None,
        id_pedido: Optional[str] = None,
    ) -> dict:
        """Pedidos cancelados; filtros opcionales por fechas, usuario o pedido."""
        params = _filtros(inicio=inicio, fin=fin, idUsuario=id_usuario, idPedido=id_pedido)
        return {"ok": True, **_lista("/barybarismo/pedidos/cancelados", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_cancelacion(id_detalle: str, rol: Rol = "ADMIN") -> dict:
        """Motivo de cancelación de un pedido (requiere rol)."""
        datos = _get(f"/barybarismo/cancelacion/{id_detalle}", headers={"X-User-Role": rol})
        return {"ok": True, "cancelacion": _compactar(datos)}

    # ---------- DEVOLUCIONES ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_devoluciones(
        bebida: Optional[str] = None,
        inicio: Optional[str] = None,
        fin: Optional[str] = None,
    ) -> dict:
        """Devoluciones: todas, por bebida, o por rango de fechas ISO (inicio+fin)."""
        if bebida:
            ruta, params = "/barybarismo/devoluciones/buscar-bebida", _filtros(nombre=bebida)
        elif inicio and fin:
            ruta, params = "/barybarismo/devoluciones/filtrar-fecha", _filtros(inicio=inicio, fin=fin)
        else:
            ruta, params = "/barybarismo/devoluciones", None
        return {"ok": True, **_lista(ruta, params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_devolucion(id_plato: str) -> dict:
        """Causa de devolución de un ítem por ID."""
        return {"ok": True, "devolucion": _compactar(_get(f"/barybarismo/devolucion/{id_plato}"))}

    # ---------- RECETAS ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_recetas(termino: Optional[str] = None) -> dict:
        """Lista recetas; con 'termino' busca por nombre."""
        ruta, params = ("/recetas/buscar", _filtros(termino=termino)) if termino else ("/recetas", None)
        return {"ok": True, **_lista(ruta, params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_receta(id_receta: str) -> dict:
        """Detalle de una receta (ingredientes y pasos) por ID."""
        return {"ok": True, "receta": _compactar(_get(f"/recetas/{id_receta}"))}

    # ---------- ALERTAS DE SALA ----------
    @mcp.tool()
    @_manejar_errores
    def listar_alertas_sala() -> dict:
        """Alertas de sala activas."""
        return {"ok": True, **_lista("/alertas")}

    @mcp.tool()
    @_manejar_errores
    def consultar_configuracion_alertas(id_usuario: str) -> dict:
        """Configuración de alertas (pantalla/sonido) de un usuario."""
        return {"ok": True, "configuracion": _compactar(_get(f"/alertas/configuracion/{id_usuario}"))}
