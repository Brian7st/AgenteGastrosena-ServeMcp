"""
MCP de integración con gams-usuarios (Notificaciones).
Centraliza la consulta de notificaciones de sistema (leídas, no leídas, filtros).
Rutas verificadas contra el NotificacionController; todas cuelgan de /api.
"""

import os
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

# --- Config: backend de usuarios ---
API_BASE_URL = os.environ.get("USUARIOS_API_BASE_URL", "http://localhost:8086").rstrip("/")
API_PREFIX = "/api"
API_TOKEN = os.environ.get("USUARIOS_API_TOKEN")
TIMEOUT = 10
MAX_ITEMS = 50

_session = requests.Session()
if API_TOKEN:
    _session.headers["Authorization"] = f"Bearer {API_TOKEN}"


def _get(path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    """Único punto de salida HTTP."""
    resp = _session.get(
        f"{API_BASE_URL}{API_PREFIX}{path}", params=params, headers=headers, timeout=TIMEOUT
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


def _put(path: str, params: Optional[dict] = None, json_body: Optional[dict] = None) -> dict:
    """Punto de salida HTTP para operaciones PUT (usado como PATCH en actualizaciones de estado)."""
    resp = _session.put(
        f"{API_BASE_URL}{API_PREFIX}{path}", params=params, json=json_body, timeout=TIMEOUT
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
    """Quita claves null/vacías para ahorrar tokens."""
    if isinstance(dato, list):
        return [_compactar(x) for x in dato]
    if isinstance(dato, dict):
        return {k: _compactar(v) for k, v in dato.items() if v is not None and v != ""}
    return dato


def _lista(path: str, params: Optional[dict] = None) -> dict:
    """Endpoints de lista: compacta y recorta a MAX_ITEMS."""
    datos = _compactar(_get(path, params))
    if not isinstance(datos, list):
        # A veces la API paginada devuelve un dict con 'contenido'
        if isinstance(datos, dict) and "contenido" in datos:
            elementos = datos["contenido"]
            if isinstance(elementos, list):
                return {"total": len(elementos), "items": elementos[:MAX_ITEMS], "truncado": len(elementos) > MAX_ITEMS}
        return {"total": 0, "items": [], "truncado": False}
    return {"total": len(datos), "items": datos[:MAX_ITEMS], "truncado": len(datos) > MAX_ITEMS}


def register(mcp: FastMCP):

    # ==========================================
    # ---------- ACCIONES (PUT/PATCH) ----------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def marcar_notificacion_como_leida(id_notificacion: str) -> dict:
        """
        Marca una notificación específica como leída usando su ID único.
        
        Parámetros:
        - id_notificacion (str): ID único de la notificación a marcar como leída.
        """
        _put(f"/notificaciones/{id_notificacion}/leer")
        return {"ok": True, "mensaje": f"✅ Confirmación visual: La notificación {id_notificacion} ha sido marcada como leída."}

    @mcp.tool()
    @_manejar_errores
    def marcar_todas_notificaciones_como_leidas() -> dict:
        """
        Marca todas las notificaciones pendientes del usuario como leídas.
        """
        _put("/notificaciones/leer-todas")
        return {"ok": True, "mensaje": "✅ Confirmación visual: Todas las notificaciones han sido marcadas como leídas."}

    # ==========================================
    # ---------- CONSULTAS (GET) ---------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def listar_todas_notificaciones() -> dict:
        """
        Obtiene la lista completa de todas las notificaciones (tanto leídas como no leídas) del usuario.
        
        No modifica información.
        """
        return {"ok": True, **_lista("/notificaciones")}

    @mcp.tool()
    @_manejar_errores
    def listar_notificaciones_no_leidas() -> dict:
        """
        Obtiene únicamente la lista de notificaciones pendientes de leer del usuario.
        
        No modifica información.
        """
        return {"ok": True, **_lista("/notificaciones/no-leidas")}

    @mcp.tool()
    @_manejar_errores
    def filtrar_notificaciones(
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        tipo: Optional[str] = None
    ) -> dict:
        """
        Filtra y busca notificaciones aplicando rango de fechas y/o tipo específico de alerta.
        
        Parámetros:
        - fecha_inicio (str, opcional): Fecha de inicio del filtro (formato ISO/cadena).
        - fecha_fin (str, opcional): Fecha de fin del filtro (formato ISO/cadena).
        - tipo (str, opcional): Tipo de notificación/alerta a filtrar.
        
        No modifica información.
        """
        params = _filtros(inicio=fecha_inicio, fin=fecha_fin, tipo=tipo)
        return {"ok": True, **_lista("/notificaciones/filtrar", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_conteo_notificaciones_no_leidas() -> dict:
        """
        Obtiene la cantidad exacta (conteo numérico) de notificaciones pendientes por leer del usuario.
        
        No modifica información.
        """
        datos = _get("/notificaciones/no-leidas/count")
        if isinstance(datos, dict) and "count" in datos:
            conteo = datos["count"]
        elif isinstance(datos, (int, str)):
            conteo = int(datos)
        else:
            conteo = datos  # Fallback
            
        return {"ok": True, "notificaciones_no_leidas": conteo}
