"""
MCP de integración con gs-ms-cocina (Cocina). Solo lectura.
Módulos: Actividades, Categorías, Comandas, Estadísticas, Incidencias, Ingredientes, Pasos, Recetas.
Rutas verificadas contra los @RequestMapping; todas cuelgan de /api.
"""

import os
from typing import Literal, Optional

import requests
from mcp.server.fastmcp import FastMCP

# --- Config: propia del micro de cocina ---
API_BASE_URL = os.environ.get("COCINA_API_BASE_URL", "http://localhost:8082").rstrip("/")
API_PREFIX = "/api"
API_TOKEN = os.environ.get("COCINA_API_TOKEN")
TIMEOUT = 10
MAX_ITEMS = 50                               # tope de filas: protege el contexto del LLM

_session = requests.Session()
if API_TOKEN:
    _session.headers["Authorization"] = f"Bearer {API_TOKEN}"


def _get(path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    """Único punto de salida HTTP para GET: prefijo, timeout y raise."""
    resp = _session.get(
        f"{API_BASE_URL}{API_PREFIX}{path}", params=params, headers=headers, timeout=TIMEOUT
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


def _patch(path: str, params: Optional[dict] = None, json_body: Optional[dict] = None) -> dict:
    """Punto de salida HTTP para operaciones PATCH."""
    resp = _session.patch(
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
        # A veces la API paginada devuelve un dict con 'contenido'
        if isinstance(datos, dict) and "contenido" in datos:
            elementos = datos["contenido"]
            if isinstance(elementos, list):
                return {"total": len(elementos), "items": elementos[:MAX_ITEMS], "truncado": len(elementos) > MAX_ITEMS}
        return {"total": 0, "items": [], "truncado": False}
    return {"total": len(datos), "items": datos[:MAX_ITEMS], "truncado": len(datos) > MAX_ITEMS}


def register(mcp: FastMCP):

    # ---------- ACTUALIZACIONES OPERATIVAS (PATCH) ----------
    @mcp.tool()
    @_manejar_errores
    def actualizar_estado_actividad(id_actividad: str, nuevo_estado: str) -> dict:
        """Actualiza el estado de una actividad usando PATCH."""
        _patch(f"/actividades/{id_actividad}/estado", params={"estado": nuevo_estado})
        return {"ok": True, "mensaje": f"✅ Confirmación visual: El estado de la actividad {id_actividad} ha sido actualizado a {nuevo_estado}."}

    @mcp.tool()
    @_manejar_errores
    def gestionar_preparacion_plato(
        id_detalle: str, 
        accion: Literal["iniciar", "finalizar", "cambiar_estado"],
        nuevo_estado: Optional[str] = None
    ) -> dict:
        """
        Permite a la cocina iniciar, finalizar o cambiar el estado de un plato específico.
        Requiere el ID del detalle de la comanda.
        """
        if accion == "iniciar":
            _patch(f"/cocina/comandas/detalle/{id_detalle}/iniciar")
            return {"ok": True, "mensaje": f"✅ Confirmación visual: La preparación del plato {id_detalle} ha iniciado correctamente."}
        elif accion == "finalizar":
            _patch(f"/cocina/comandas/detalle/{id_detalle}/finalizar")
            return {"ok": True, "mensaje": f"✅ Confirmación visual: La preparación del plato {id_detalle} ha finalizado."}
        elif accion == "cambiar_estado":
            if not nuevo_estado:
                return {"ok": False, "error": "Debe proveer un nuevo_estado"}
            _patch(f"/cocina/comandas/detalle/{id_detalle}/estado", params={"estado": nuevo_estado})
            return {"ok": True, "mensaje": f"✅ Confirmación visual: El estado del plato {id_detalle} se actualizó a {nuevo_estado}."}
        return {"ok": False, "error": "Acción no válida."}


    # ---------- ACTIVIDADES Y APRENDICES ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_categorias_receta(
        id_categoria: Optional[str] = None,
        buscar: Optional[str] = None,
        paginado: bool = False
    ) -> dict:
        """Busca o lista categorías de recetas de la cocina."""
        if id_categoria:
            return {"ok": True, "categoria": _compactar(_get(f"/categorias/{id_categoria}"))}
        elif buscar:
            params = _filtros(nombre=buscar)
            return {"ok": True, **_lista("/categorias/buscar", params)}
        elif paginado:
            return {"ok": True, **_lista("/categorias/paginado")}
        return {"ok": True, **_lista("/categorias")}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_categorias() -> dict:
        """Contar el total de categorías."""
        return {"ok": True, "total": _compactar(_get("/categorias/total"))}


    # ---------- COMANDAS DE COCINA ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_comandas_cocina(
        id_comanda: Optional[str] = None,
        filtrar: bool = False,
        estado: Optional[str] = None,
        prioridad: Optional[str] = None,
        orden: Optional[str] = "ASC",
        inicio: Optional[str] = None,
        fin: Optional[str] = None
    ) -> dict:
        """
        Obtiene comandas de cocina activas, una específica por ID,
        o las filtra por estado, prioridad y rango de fechas (usa filtrar=True).
        Las fechas inicio y fin deben estar en formato ISO (ej. 2026-05-01T00:00:00).
        """
        if id_comanda:
            return {"ok": True, "comanda": _compactar(_get(f"/cocina/comandas/{id_comanda}"))}
        elif filtrar:
            params = _filtros(estado=estado, prioridad=prioridad, orden=orden, inicio=inicio, fin=fin)
            return {"ok": True, **_lista("/cocina/comandas/cocina/filtrar", params)}
        return {"ok": True, **_lista("/cocina/comandas")}


    # ---------- ESTADÍSTICAS ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_estadisticas_cocina(
        tipo: Literal["promedio", "diarias"] = "promedio",
        fecha: Optional[str] = None,
        inicio: Optional[str] = None,
        fin: Optional[str] = None
    ) -> dict:
        """
        Estadísticas de la cocina: promedios por plato o carga de trabajo diaria.
        Para tipo='diarias', puedes proveer una 'fecha' o un rango con 'inicio' y 'fin'.
        """
        if tipo == "diarias":
            params = _filtros(fecha=fecha, inicio=inicio, fin=fin)
            return {"ok": True, "estadisticas": _compactar(_get("/cocina/estadisticas/diarias", params))}
        
        params = _filtros(inicio=inicio, fin=fin)
        return {"ok": True, "estadisticas": _compactar(_get("/cocina/estadisticas/promedio", params))}


    # ---------- INCIDENCIAS ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_incidencias_cocina(
        tipo: Optional[str] = None,
        id_comanda: Optional[str] = None,
        id_usuario: Optional[str] = None,
        inicio: Optional[str] = None,
        fin: Optional[str] = None
    ) -> dict:
        """Busca incidencias en la cocina por tipo, id de la comanda o id de usuario, pudiendo filtrar por rango de fechas (inicio, fin)."""
        params = _filtros(inicio=inicio, fin=fin)
        if tipo:
            return {"ok": True, **_lista(f"/cocina/incidencias/tipo/{tipo}", params)}
        elif id_comanda:
            return {"ok": True, **_lista(f"/cocina/incidencias/comanda/{id_comanda}", params)}
        elif id_usuario:
            return {"ok": True, **_lista(f"/cocina/incidencias/usuario/{id_usuario}", params)}
        
        # Si no se proveen variables de path pero se quieren filtrar incidencias generales por fecha
        if inicio or fin:
            return {"ok": True, **_lista("/cocina/incidencias", params)}

        return {"ok": False, "error": "Debes proveer tipo, id_comanda, id_usuario o un rango de fechas para buscar incidencias"}


    # ---------- INGREDIENTES ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_ingredientes(
        id_ingrediente: Optional[str] = None,
        nombre: Optional[str] = None,
        unidad: Optional[str] = None,
        todos: bool = False
    ) -> dict:
        """Busca o lista ingredientes. Usa 'todos=True' para evitar paginado si son necesarios todos."""
        if id_ingrediente:
            return {"ok": True, "ingrediente": _compactar(_get(f"/ingredientes/{id_ingrediente}"))}
        elif nombre:
            params = _filtros(nombre=nombre)
            return {"ok": True, **_lista("/ingredientes/buscar-nombre", params)}
        elif unidad:
            return {"ok": True, **_lista(f"/ingredientes/unidad/{unidad}")}
        elif todos:
            return {"ok": True, **_lista("/ingredientes/todos")}
        
        # Paginado por defecto
        return {"ok": True, **_lista("/ingredientes")}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_ingredientes() -> dict:
        """Contar el total de ingredientes registrados."""
        return {"ok": True, "total": _compactar(_get("/ingredientes/total"))}


    # ---------- PASOS DE PREPARACIÓN ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_pasos_receta(id_receta: str, solo_total: bool = False) -> dict:
        """Obtiene los pasos de una receta o simplemente cuenta el total de pasos."""
        if solo_total:
            return {"ok": True, "total": _compactar(_get(f"/pasos/receta/{id_receta}/total"))}
        return {"ok": True, **_lista(f"/pasos/receta/{id_receta}")}


    # ---------- RECETAS ----------
    @mcp.tool()
    @_manejar_errores
    def consultar_recetas_cocina(
        id_receta: Optional[str] = None,
        id_categoria: Optional[str] = None,
        buscar: Optional[str] = None,
        filtro: Optional[Literal["precio", "tiempo", "caras"]] = None,
        paginado: bool = False
    ) -> dict:
        """
        Consolida todas las consultas a recetas. 
        Permite buscar por id, categoría, nombre o filtros especiales (precio, tiempo, caras).
        """
        if id_receta:
            return {"ok": True, "receta": _compactar(_get(f"/recetas/{id_receta}"))}
        elif id_categoria:
            return {"ok": True, **_lista(f"/recetas/categoria/{id_categoria}")}
        elif buscar:
            params = _filtros(nombre=buscar)
            return {"ok": True, **_lista("/recetas/buscar", params)}
        elif filtro:
            return {"ok": True, **_lista(f"/recetas/filtro/{filtro}")}
        elif paginado:
            return {"ok": True, **_lista("/recetas/paginado")}
        
        return {"ok": True, **_lista("/recetas")}

