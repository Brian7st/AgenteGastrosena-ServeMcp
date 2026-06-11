"""
MCP de integración con gs-ms-cocina (Bar y Barismo).
Comandas, estadísticas, cancelaciones, devoluciones, recetas y alertas de sala.
Rutas verificadas contra los @RequestMapping; todas cuelgan de /api.
"""

import functools
import os
from typing import Literal, Optional

import requests
from mcp.server.fastmcp import FastMCP

# --- Config ---
API_BASE_URL = os.environ.get("BAR_API_BASE_URL", "http://localhost:8086").rstrip("/")
API_PREFIX = "/api"
API_TOKEN = os.environ.get("BAR_API_TOKEN")
TIMEOUT = 10
MAX_ITEMS = 50

EstadoComanda = Literal["PENDIENTE", "EN_PREPARACION", "LISTO", "ENTREGADO", "CANCELADO"]
EstadoAlerta  = Literal["PENDIENTE", "CONFIRMADA", "IGNORADA"]
Rol           = Literal["ADMIN", "BARISTA", "MESERO"]

_session = requests.Session()
if API_TOKEN:
    _session.headers["Authorization"] = f"Bearer {API_TOKEN}"


def _get(path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    """Único punto de salida HTTP GET: prefijo, timeout y raise."""
    resp = _session.get(
        f"{API_BASE_URL}{API_PREFIX}{path}", params=params, headers=headers, timeout=TIMEOUT
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


def _write(method: str, path: str, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
    """Único punto de salida HTTP de escritura: POST, PUT."""
    resp = _session.request(
        method, f"{API_BASE_URL}{API_PREFIX}{path}", params=params, json=json, timeout=TIMEOUT
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    ct = resp.headers.get("Content-Type", "")
    return resp.json() if "json" in ct else {"mensaje": resp.text}


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

    @mcp.tool()
    @_manejar_errores
    def actualizar_estado_comanda(id_comanda: str, estado: EstadoComanda) -> dict:
        """Actualiza el estado de una comanda."""
        datos = _write("PUT", f"/barybarismo/comandas/{id_comanda}/estado", params={"estado": estado})
        return {"ok": True, "comanda": _compactar(datos)}

    @mcp.tool()
    @_manejar_errores
    def iniciar_preparacion_comanda(id_comanda: str, id_responsable: int) -> dict:
        """Inicia la preparación de una comanda; registra el barista responsable."""
        datos = _write("PUT", f"/barybarismo/comandas/{id_comanda}/iniciar", params={"responsable": id_responsable})
        return {"ok": True, "comanda": _compactar(datos)}

    @mcp.tool()
    @_manejar_errores
    def finalizar_preparacion_comanda(id_comanda: str) -> dict:
        """Finaliza la preparación de una comanda (estado → LISTO)."""
        datos = _write("PUT", f"/barybarismo/comandas/{id_comanda}/finalizar")
        return {"ok": True, "comanda": _compactar(datos)}

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

    @mcp.tool()
    @_manejar_errores
    def cancelar_pedido(id_detalle_comanda: str, motivo_cancelacion: str, usuario_cancela: Optional[str] = None) -> dict:
        """Cancela un pedido y lo registra en el historial. usuario_cancela es opcional."""
        body = _filtros(idDetalleComanda=id_detalle_comanda, motivoCancelacion=motivo_cancelacion, usuarioCancela=usuario_cancela)
        datos = _write("PUT", "/barybarismo/pedido/cancelar", json=body)
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

    @mcp.tool()
    @_manejar_errores
    def registrar_devolucion(id_detalle_comanda: str, motivo: str) -> dict:
        """Registra la devolución de una bebida."""
        datos = _write("POST", "/barybarismo/devolucion", json={"idDetalleComanda": id_detalle_comanda, "motivo": motivo})
        return {"ok": True, "devolucion": _compactar(datos)}

    # ---------- MODIFICACIÓN DE PEDIDOS ----------
    @mcp.tool()
    @_manejar_errores
    def modificar_pedido(id_detalle_comanda: str, motivo: str, nueva_cantidad: Optional[int] = None, nuevas_notas: Optional[str] = None) -> dict:
        """Modifica cantidad y/o notas de un pedido; registra en auditoría."""
        body = _filtros(idDetalleComanda=id_detalle_comanda, motivo=motivo, nuevaCantidad=nueva_cantidad, nuevasNotas=nuevas_notas)
        datos = _write("PUT", "/barybarismo/pedido/modificar", json=body)
        return {"ok": True, **datos}

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

    @mcp.tool()
    @_manejar_errores
    def crear_receta(id_categoria: str, nombre_receta: str, tiempo_preparacion: int,
                     precio_unitario: float, temperatura: str, ingredientes: list[dict], pasos: list[dict]) -> dict:
        """Crea una nueva receta con ingredientes y pasos."""
        body = {"idCategoria": id_categoria, "nombreReceta": nombre_receta, "tiempoPreparacion": tiempo_preparacion,
                "precioUnitario": precio_unitario, "temperatura": temperatura, "ingredientes": ingredientes, "pasos": pasos}
        datos = _write("POST", "/recetas", json=body)
        return {"ok": True, "receta": _compactar(datos)}

    @mcp.tool()
    @_manejar_errores
    def actualizar_receta(id_receta: str, id_categoria: str, nombre_receta: str, tiempo_preparacion: int,
                          precio_unitario: float, temperatura: str, ingredientes: list[dict], pasos: list[dict]) -> dict:
        """Actualiza una receta existente; reemplaza ingredientes y pasos completos."""
        body = {"idCategoria": id_categoria, "nombreReceta": nombre_receta, "tiempoPreparacion": tiempo_preparacion,
                "precioUnitario": precio_unitario, "temperatura": temperatura, "ingredientes": ingredientes, "pasos": pasos}
        datos = _write("PUT", f"/recetas/{id_receta}", json=body)
        return {"ok": True, "receta": _compactar(datos)}

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

    @mcp.tool()
    @_manejar_errores
    def confirmar_alerta_sala(id_alerta: str, nuevo_estado: EstadoAlerta) -> dict:
        """Confirma o cambia el estado de una alerta de sala."""
        datos = _write("PUT", f"/alertas/{id_alerta}/confirmar", params={"nuevoEstado": nuevo_estado})
        return {"ok": True, "alerta": _compactar(datos)}

    @mcp.tool()
    @_manejar_errores
    def guardar_configuracion_alertas(id_usuario: str, pantalla: bool, sonido: bool) -> dict:
        """Guarda o actualiza la configuración de alertas (pantalla/sonido) de un usuario."""
        params = {"idUsuario": id_usuario, "pantalla": str(pantalla).lower(), "sonido": str(sonido).lower()}
        datos = _write("POST", "/alertas/configuracion", params=params)
        return {"ok": True, "configuracion": _compactar(datos)}

    # ---------- COCINA ----------
    @mcp.tool()
    @_manejar_errores
    def marcar_comanda_lista(id_comanda: str, id_mesa: str, id_mesero: str, id_modulo_origen: str) -> dict:
        """Marca una comanda como lista y genera alerta de sala automáticamente."""
        params = {"idMesa": id_mesa, "idMesero": id_mesero, "idModuloOrigen": id_modulo_origen}
        datos = _write("POST", f"/cocina/comandas/{id_comanda}/listo", params=params)
        return {"ok": True, **datos}