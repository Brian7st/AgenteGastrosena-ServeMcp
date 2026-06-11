"""
MCP de integración con gs-ms-cocina (Cocina).
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


def _post(path: str, params: Optional[dict] = None, json_body: Optional[dict] = None) -> dict:
    """Punto de salida HTTP para operaciones POST."""
    resp = _session.post(
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

    # ==========================================
    # ---------- CREACIÓN (POST) ---------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def crear_categoria_receta(datos_categoria: dict) -> dict:
        """
        Crea una nueva categoría de receta.
        
        Parámetros:
        - datos_categoria (dict): Diccionario con los datos de la categoría (ej. nombre).
        
        Retorna:
        - Un objeto indicando éxito y la categoría creada.
        """
        created = _post("/categorias", json_body=datos_categoria)
        return {
            "ok": True,
            "mensaje": "✅ Confirmación visual: La nueva categoría de receta fue creada correctamente.",
            "categoria": _compactar(created)
        }

    @mcp.tool()
    @_manejar_errores
    def crear_ingrediente(datos_ingrediente: dict) -> dict:
        """
        Crea un nuevo ingrediente en el inventario/cocina.
        
        Parámetros:
        - datos_ingrediente (dict): Diccionario con los datos del ingrediente (ej. nombre, unidadMedida).
        
        Retorna:
        - Un objeto indicando éxito y el ingrediente creado.
        """
        created = _post("/ingredientes", json_body=datos_ingrediente)
        return {
            "ok": True,
            "mensaje": "✅ Confirmación visual: El ingrediente fue registrado exitosamente.",
            "ingrediente": _compactar(created)
        }

    @mcp.tool()
    @_manejar_errores
    def crear_receta(datos_receta: dict) -> dict:
        """
        Crea una nueva receta en la cocina.
        
        Parámetros:
        - datos_receta (dict): Diccionario completo con la receta (nombreReceta, precioUnitario, ingredientes, pasos, etc.).
        
        Retorna:
        - Un objeto indicando éxito y la receta creada.
        """
        created = _post("/recetas", json_body=datos_receta)
        return {
            "ok": True,
            "mensaje": "✅ Confirmación visual: La receta ha sido creada y guardada con éxito.",
            "receta": _compactar(created)
        }

    @mcp.tool()
    @_manejar_errores
    def crear_paso_preparacion(datos_paso: dict) -> dict:
        """
        Crea un nuevo paso de preparación para una receta.
        
        Parámetros:
        - datos_paso (dict): Diccionario con los datos del paso (ej. orden, descripcionPaso, idReceta).
        
        Retorna:
        - Un objeto indicando éxito y el paso creado.
        """
        created = _post("/pasos", json_body=datos_paso)
        return {
            "ok": True,
            "mensaje": "✅ Confirmación visual: El paso de preparación fue añadido correctamente a la receta.",
            "paso": _compactar(created)
        }

    @mcp.tool()
    @_manejar_errores
    def crear_actividad_cocina(datos_actividad: dict) -> dict:
        """
        Crea una nueva actividad de cocina.
        
        Parámetros:
        - datos_actividad (dict): Diccionario con los datos de la actividad (ej. nombre, fecha, estado).
        
        Retorna:
        - Un objeto indicando éxito y la actividad creada.
        """
        created = _post("/actividades", json_body=datos_actividad)
        return {
            "ok": True,
            "mensaje": "✅ Confirmación visual: La nueva actividad ha sido programada exitosamente.",
            "actividad": _compactar(created)
        }

    @mcp.tool()
    @_manejar_errores
    def evaluar_aprendiz(actividad_id: str, datos_evaluacion: dict) -> dict:
        """
        Evalúa a un aprendiz en una actividad específica.
        
        Parámetros:
        - actividad_id (str): El ID de la actividad a evaluar.
        - datos_evaluacion (dict): Diccionario con los datos de la evaluación.
        
        Retorna:
        - Un objeto indicando éxito y la evaluación creada.
        """
        created = _post(f"/actividades/{actividad_id}/evaluar", json_body=datos_evaluacion)
        return {
            "ok": True,
            "mensaje": f"✅ Confirmación visual: La evaluación del aprendiz para la actividad {actividad_id} ha sido registrada.",
            "evaluacion": _compactar(created)
        }

    @mcp.tool()
    @_manejar_errores
    def reportar_incidencia_cocina(datos_incidencia: dict) -> dict:
        """
        Reporta una nueva incidencia en la cocina.
        
        Parámetros:
        - datos_incidencia (dict): Diccionario con tipo, idComanda, idUsuario y descripcion.
        
        Retorna:
        - Un objeto indicando éxito y la incidencia creada.
        """
        created = _post("/cocina/incidencias", json_body=datos_incidencia)
        return {
            "ok": True,
            "mensaje": "✅ Confirmación visual: La incidencia se ha reportado exitosamente.",
            "incidencia": _compactar(created)
        }

    # ==========================================
    # ---------- ACTUALIZACIONES / ACCIONES ----
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def marcar_comanda_lista(id_comanda: str, id_mesa: str, id_mesero: str, id_modulo_origen: str) -> dict:
        """
        Marca una comanda de cocina como lista, notificando a la sala.
        
        Parámetros:
        - id_comanda (str): ID de la comanda.
        - id_mesa (str): ID de la mesa.
        - id_mesero (str): ID del mesero.
        - id_modulo_origen (str): ID del módulo de origen.
        """
        params = {"idMesa": id_mesa, "idMesero": id_mesero, "idModuloOrigen": id_modulo_origen}
        _post(f"/cocina/comandas/{id_comanda}/listo", params=params)
        return {"ok": True, "mensaje": f"✅ Confirmación visual: La comanda {id_comanda} ha sido marcada como lista."}

    @mcp.tool()
    @_manejar_errores
    def actualizar_estado_actividad(id_actividad: str, nuevo_estado: str) -> dict:
        """
        Actualiza el estado de una actividad específica.
        
        Parámetros:
        - id_actividad (str): ID de la actividad.
        - nuevo_estado (str): El nuevo estado a aplicar (ej. PROGRAMADA, EN_PROCESO, COMPLETADA, CANCELADA).
        """
        _patch(f"/actividades/{id_actividad}/estado", params={"estado": nuevo_estado})
        return {"ok": True, "mensaje": f"✅ Confirmación visual: El estado de la actividad {id_actividad} ha sido actualizado a {nuevo_estado}."}

    @mcp.tool()
    @_manejar_errores
    def iniciar_preparacion_plato(id_detalle: str) -> dict:
        """
        Inicia la preparación de un plato específico (detalle de comanda).
        
        Parámetros:
        - id_detalle (str): ID del detalle de la comanda.
        """
        _patch(f"/cocina/comandas/detalle/{id_detalle}/iniciar")
        return {"ok": True, "mensaje": f"✅ Confirmación visual: La preparación del plato {id_detalle} ha iniciado correctamente."}

    @mcp.tool()
    @_manejar_errores
    def finalizar_preparacion_plato(id_detalle: str) -> dict:
        """
        Finaliza la preparación de un plato específico (detalle de comanda).
        
        Parámetros:
        - id_detalle (str): ID del detalle de la comanda.
        """
        _patch(f"/cocina/comandas/detalle/{id_detalle}/finalizar")
        return {"ok": True, "mensaje": f"✅ Confirmación visual: La preparación del plato {id_detalle} ha finalizado."}

    @mcp.tool()
    @_manejar_errores
    def actualizar_estado_preparacion_plato(id_detalle: str, nuevo_estado: str) -> dict:
        """
        Actualiza el estado de preparación de un plato específico de forma manual.
        
        Parámetros:
        - id_detalle (str): ID del detalle de la comanda.
        - nuevo_estado (str): El nuevo estado a asignar.
        """
        _patch(f"/cocina/comandas/detalle/{id_detalle}/estado", params={"estado": nuevo_estado})
        return {"ok": True, "mensaje": f"✅ Confirmación visual: El estado del plato {id_detalle} se actualizó a {nuevo_estado}."}

    # ==========================================
    # ---------- CONSULTAS (GET) ---------------
    # ==========================================

    # ---------- COMANDAS ----------

    @mcp.tool()
    @_manejar_errores
    def obtener_comanda_por_id(id_comanda: str) -> dict:
        """
        Obtiene el detalle completo de una comanda específica por su ID.
        
        No modifica información.
        """
        return {"ok": True, "comanda": _compactar(_get(f"/cocina/comandas/{id_comanda}"))}

    @mcp.tool()
    @_manejar_errores
    def listar_comandas_cocina() -> dict:
        """
        Lista todas las comandas de cocina registradas.
        
        No modifica información.
        """
        return {"ok": True, **_lista("/cocina/comandas")}

    @mcp.tool()
    @_manejar_errores
    def filtrar_comandas(
        estado: Optional[str] = None,
        prioridad: Optional[str] = None,
        orden: str = "ASC",
        inicio: Optional[str] = None,
        fin: Optional[str] = None
    ) -> dict:
        """
        Filtra comandas de cocina por estado, prioridad y rango de fechas de llegada.
        
        No modifica información.
        """
        params = _filtros(estado=estado, prioridad=prioridad, orden=orden, inicio=inicio, fin=fin)
        return {"ok": True, **_lista("/cocina/comandas/cocina/filtrar", params)}

    # ---------- CATEGORÍAS ----------

    @mcp.tool()
    @_manejar_errores
    def obtener_categoria_por_id(id_categoria: str) -> dict:
        """
        Obtiene los detalles de una categoría de receta por su ID.
        
        No modifica información.
        """
        return {"ok": True, "categoria": _compactar(_get(f"/categorias/{id_categoria}"))}

    @mcp.tool()
    @_manejar_errores
    def buscar_categorias(nombre: str) -> dict:
        """
        Busca categorías de recetas que contengan el nombre especificado.
        
        No modifica información.
        """
        params = _filtros(nombre=nombre)
        return {"ok": True, **_lista("/categorias/buscar", params)}

    @mcp.tool()
    @_manejar_errores
    def listar_categorias(paginado: bool = False) -> dict:
        """
        Lista todas las categorías de recetas.
        
        No modifica información.
        """
        ruta = "/categorias/paginado" if paginado else "/categorias"
        return {"ok": True, **_lista(ruta)}

    # ---------- INGREDIENTES ----------

    @mcp.tool()
    @_manejar_errores
    def obtener_ingrediente_por_id(id_ingrediente: str) -> dict:
        """
        Obtiene los detalles de un ingrediente específico por su ID.
        
        No modifica información.
        """
        return {"ok": True, "ingrediente": _compactar(_get(f"/ingredientes/{id_ingrediente}"))}

    @mcp.tool()
    @_manejar_errores
    def buscar_ingrediente_por_nombre(nombre: str) -> dict:
        """
        Busca ingredientes que contengan el nombre indicado.
        
        No modifica información.
        """
        params = _filtros(nombre=nombre)
        return {"ok": True, **_lista("/ingredientes/buscar-nombre", params)}

    @mcp.tool()
    @_manejar_errores
    def listar_ingredientes_por_unidad(unidad: str) -> dict:
        """
        Filtra ingredientes por su unidad de medida.
        
        No modifica información.
        """
        return {"ok": True, **_lista(f"/ingredientes/unidad/{unidad}")}

    @mcp.tool()
    @_manejar_errores
    def listar_todos_ingredientes() -> dict:
        """
        Obtiene la lista completa de todos los ingredientes registrados (sin paginado).
        
        No modifica información.
        """
        return {"ok": True, **_lista("/ingredientes/todos")}

    @mcp.tool()
    @_manejar_errores
    def listar_ingredientes_paginado() -> dict:
        """
        Lista ingredientes en formato paginado estándar.
        
        No modifica información.
        """
        return {"ok": True, **_lista("/ingredientes")}

    # ---------- RECETAS ----------

    @mcp.tool()
    @_manejar_errores
    def obtener_receta_por_id(id_receta: str) -> dict:
        """
        Obtiene una receta específica por su ID.
        
        No modifica información.
        """
        return {"ok": True, "receta": _compactar(_get(f"/recetas/{id_receta}"))}

    @mcp.tool()
    @_manejar_errores
    def listar_recetas_por_categoria(id_categoria: str) -> dict:
        """
        Lista todas las recetas pertenecientes a una categoría específica.
        
        No modifica información.
        """
        return {"ok": True, **_lista(f"/recetas/categoria/{id_categoria}")}

    @mcp.tool()
    @_manejar_errores
    def buscar_recetas_por_nombre(nombre: str) -> dict:
        """
        Busca recetas cuyos nombres coincidan con el término indicado.
        
        No modifica información.
        """
        params = _filtros(nombre=nombre)
        return {"ok": True, **_lista("/recetas/buscar", params)}

    @mcp.tool()
    @_manejar_errores
    def listar_recetas_por_filtro(filtro: Literal["precio", "tiempo", "caras"]) -> dict:
        """
        Lista recetas aplicando filtros predefinidos (precio, tiempo o más caras).
        
        No modifica información.
        """
        return {"ok": True, **_lista(f"/recetas/filtro/{filtro}")}

    @mcp.tool()
    @_manejar_errores
    def listar_recetas(paginado: bool = False) -> dict:
        """
        Lista todas las recetas registradas en la cocina.
        
        No modifica información.
        """
        ruta = "/recetas/paginado" if paginado else "/recetas"
        return {"ok": True, **_lista(ruta)}

    # ---------- PASOS ----------

    @mcp.tool()
    @_manejar_errores
    def listar_pasos_receta(id_receta: str) -> dict:
        """
        Obtiene los pasos de preparación asociados a una receta.
        
        No modifica información.
        """
        return {"ok": True, **_lista(f"/pasos/receta/{id_receta}")}

    # ---------- INCIDENCIAS ----------

    @mcp.tool()
    @_manejar_errores
    def listar_incidencias(inicio: Optional[str] = None, fin: Optional[str] = None) -> dict:
        """
        Lista todas las incidencias registradas en la cocina, con filtro opcional por fecha.
        
        No modifica información.
        """
        params = _filtros(inicio=inicio, fin=fin)
        return {"ok": True, **_lista("/cocina/incidencias", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_incidencias_por_tipo(tipo: str, inicio: Optional[str] = None, fin: Optional[str] = None) -> dict:
        """
        Obtiene las incidencias filtradas por su tipo.
        
        No modifica información.
        """
        params = _filtros(inicio=inicio, fin=fin)
        return {"ok": True, **_lista(f"/cocina/incidencias/tipo/{tipo}", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_incidencias_por_comanda(id_comanda: str, inicio: Optional[str] = None, fin: Optional[str] = None) -> dict:
        """
        Obtiene las incidencias asociadas a una comanda.
        
        No modifica información.
        """
        params = _filtros(inicio=inicio, fin=fin)
        return {"ok": True, **_lista(f"/cocina/incidencias/comanda/{id_comanda}", params)}

    @mcp.tool()
    @_manejar_errores
    def consultar_incidencias_por_usuario(id_usuario: str, inicio: Optional[str] = None, fin: Optional[str] = None) -> dict:
        """
        Obtiene las incidencias reportadas por un usuario.
        
        No modifica información.
        """
        params = _filtros(inicio=inicio, fin=fin)
        return {"ok": True, **_lista(f"/cocina/incidencias/usuario/{id_usuario}", params)}

    # ---------- ESTADÍSTICAS ----------

    @mcp.tool()
    @_manejar_errores
    def consultar_estadisticas_promedio(inicio: Optional[str] = None, fin: Optional[str] = None) -> dict:
        """
        Obtiene el promedio de preparación por plato en el rango de fechas.
        
        No modifica información.
        """
        params = _filtros(inicio=inicio, fin=fin)
        return {"ok": True, "estadisticas": _compactar(_get("/cocina/estadisticas/promedio", params))}

    @mcp.tool()
    @_manejar_errores
    def consultar_estadisticas_diarias_cocina(
        fecha: Optional[str] = None,
        inicio: Optional[str] = None,
        fin: Optional[str] = None
    ) -> dict:
        """
        Obtiene la carga de trabajo diaria de la cocina.
        
        No modifica información.
        """
        params = _filtros(fecha=fecha, inicio=inicio, fin=fin)
        return {"ok": True, "estadisticas": _compactar(_get("/cocina/estadisticas/diarias", params))}

    # ==========================================
    # ---------- CONTEOS (TOTALES) -------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def consultar_total_recetas() -> dict:
        """
        Consulta la cantidad total de recetas creadas en la cocina.
        
        No modifica información.
        """
        try:
            res = _get("/recetas/total")
            if isinstance(res, (int, float)):
                return {"ok": True, "total": int(res)}
            if isinstance(res, dict) and "total" in res:
                return {"ok": True, "total": res["total"]}
            recetas = _get("/recetas")
            return {"ok": True, "total": len(recetas)}
        except Exception:
            try:
                pag = _get("/recetas/paginado")
                if "totalElements" in pag:
                    return {"ok": True, "total": pag["totalElements"]}
                if "total" in pag:
                    return {"ok": True, "total": pag["total"]}
                if "contenido" in pag:
                    return {"ok": True, "total": len(pag["contenido"])}
            except Exception:
                pass
            return {"ok": False, "error": "No se pudo consultar el total de recetas."}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_comandas() -> dict:
        """
        Consulta la cantidad total de comandas registradas en la cocina.
        
        No modifica información.
        """
        try:
            res = _get("/cocina/comandas/total")
            if isinstance(res, (int, float)):
                return {"ok": True, "total": int(res)}
            if isinstance(res, dict) and "total" in res:
                return {"ok": True, "total": res["total"]}
            comandas = _get("/cocina/comandas")
            return {"ok": True, "total": len(comandas)}
        except Exception:
            return {"ok": False, "error": "No se pudo consultar el total de comandas."}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_actividades() -> dict:
        """
        Consulta la cantidad total de actividades de cocina programadas.
        
        No modifica información.
        """
        try:
            res = _get("/actividades/total")
            if isinstance(res, (int, float)):
                return {"ok": True, "total": int(res)}
            if isinstance(res, dict) and "total" in res:
                return {"ok": True, "total": res["total"]}
            actividades = _get("/actividades")
            return {"ok": True, "total": len(actividades)}
        except Exception:
            return {"ok": False, "error": "No se pudo consultar el total de actividades."}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_incidencias() -> dict:
        """
        Consulta la cantidad total de incidencias reportadas en la cocina.
        
        No modifica información.
        """
        try:
            res = _get("/cocina/incidencias/total")
            if isinstance(res, (int, float)):
                return {"ok": True, "total": int(res)}
            if isinstance(res, dict) and "total" in res:
                return {"ok": True, "total": res["total"]}
            incidencias = _get("/cocina/incidencias")
            return {"ok": True, "total": len(incidencias)}
        except Exception:
            return {"ok": False, "error": "No se pudo consultar el total de incidencias."}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_categorias() -> dict:
        """
        Consulta el total de categorías de recetas registradas.
        
        No modifica información.
        """
        return {"ok": True, "total": _compactar(_get("/categorias/total"))}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_ingredientes() -> dict:
        """
        Consulta el total de ingredientes registrados en el sistema.
        
        No modifica información.
        """
        return {"ok": True, "total": _compactar(_get("/ingredientes/total"))}

    @mcp.tool()
    @_manejar_errores
    def consultar_total_pasos_receta(id_receta: str) -> dict:
        """
        Consulta la cantidad total de pasos que componen una receta específica.
        
        No modifica información.
        """
        return {"ok": True, "total": _compactar(_get(f"/pasos/receta/{id_receta}/total"))}

    # ==========================================
    # ---------- VALIDACIONES ------------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def existe_receta(nombre: str) -> dict:
        """
        Verifica si existe una receta con el mismo nombre exacto (insensible a mayúsculas/minúsculas).
        Ayuda a prevenir duplicados.
        
        No modifica información.
        """
        try:
            resp = _get("/recetas/buscar", params={"nombre": nombre})
            items = resp if isinstance(resp, list) else resp.get("contenido", [])
            nombre_limpio = nombre.strip().lower()
            existe = any(
                str(x.get("nombre", x.get("nombreReceta", ""))).strip().lower() == nombre_limpio
                for x in items
            )
            return {"ok": True, "existe": existe}
        except Exception:
            return {"ok": True, "existe": False}

    @mcp.tool()
    @_manejar_errores
    def existe_categoria(nombre: str) -> dict:
        """
        Verifica si existe una categoría con el mismo nombre exacto (insensible a mayúsculas/minúsculas).
        Ayuda a prevenir duplicados.
        
        No modifica información.
        """
        try:
            resp = _get("/categorias/buscar", params={"nombre": nombre})
            items = resp if isinstance(resp, list) else resp.get("contenido", [])
            nombre_limpio = nombre.strip().lower()
            existe = any(
                str(x.get("nombre", x.get("nombreCategoria", ""))).strip().lower() == nombre_limpio
                for x in items
            )
            return {"ok": True, "existe": existe}
        except Exception:
            return {"ok": True, "existe": False}

    @mcp.tool()
    @_manejar_errores
    def existe_ingrediente(nombre: str) -> dict:
        """
        Verifica si existe un ingrediente con el mismo nombre exacto (insensible a mayúsculas/minúsculas).
        Ayuda a prevenir duplicados.
        
        No modifica información.
        """
        try:
            resp = _get("/ingredientes/buscar-nombre", params={"nombre": nombre})
            items = resp if isinstance(resp, list) else resp.get("contenido", [])
            nombre_limpio = nombre.strip().lower()
            existe = any(
                str(x.get("nombre", x.get("nombreIngrediente", ""))).strip().lower() == nombre_limpio
                for x in items
            )
            return {"ok": True, "existe": existe}
        except Exception:
            return {"ok": True, "existe": False}

    # ==========================================
    # ---------- CONTEXTO COMPLETO -------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def obtener_receta_completa(id_receta: str) -> dict:
        """
        Obtiene el contexto unificado de una receta: datos básicos, pasos, ingredientes y categoría.
        Ahorra múltiples llamadas http independientes.
        
        No modifica información.
        """
        receta = _compactar(_get(f"/recetas/{id_receta}"))
        
        # Obtener pasos
        try:
            pasos_resp = _get(f"/pasos/receta/{id_receta}")
            pasos_list = pasos_resp if isinstance(pasos_resp, list) else pasos_resp.get("contenido", [])
        except Exception:
            pasos_list = receta.get("pasos", [])

        # Categoria
        id_categoria = receta.get("idCategoria") or receta.get("categoriaId")
        categoria = {}
        if id_categoria:
            try:
                categoria = _compactar(_get(f"/categorias/{id_categoria}"))
            except Exception:
                pass

        return {
            "ok": True,
            "receta": receta,
            "ingredientes": receta.get("ingredientes", []),
            "pasos": _compactar(pasos_list),
            "categoria": categoria
        }

    # ==========================================
    # ---------- BÚSQUEDA GLOBAL ---------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def buscar_en_cocina(termino: str) -> dict:
        """
        Realiza una búsqueda global del término en recetas, ingredientes y categorías.
        Consolida las coincidencias de todo el microservicio en una única respuesta.
        
        No modifica información.
        """
        recetas = []
        ingredientes = []
        categorias = []
        
        params = {"nombre": termino}
        
        try:
            r_resp = _get("/recetas/buscar", params=params)
            recetas = _compactar(r_resp if isinstance(r_resp, list) else r_resp.get("contenido", []))
        except Exception:
            pass
            
        try:
            i_resp = _get("/ingredientes/buscar-nombre", params=params)
            ingredientes = _compactar(i_resp if isinstance(i_resp, list) else i_resp.get("contenido", []))
        except Exception:
            pass
            
        try:
            c_resp = _get("/categorias/buscar", params=params)
            categorias = _compactar(c_resp if isinstance(c_resp, list) else c_resp.get("contenido", []))
        except Exception:
            pass
            
        return {
            "ok": True,
            "recetas": recetas[:MAX_ITEMS],
            "ingredientes": ingredientes[:MAX_ITEMS],
            "categorias": categorias[:MAX_ITEMS]
        }

    # ==========================================
    # ---------- CATÁLOGOS ---------------------
    # ==========================================

    @mcp.tool()
    def consultar_estados_comanda() -> dict:
        """
        Obtiene el catálogo de estados permitidos para el ciclo de vida de una comanda.
        
        No modifica información.
        """
        return {
            "ok": True,
            "estados": ["PENDIENTE", "EN_PREPARACION", "LISTO", "ENTREGADO", "CANCELADO"]
        }

    @mcp.tool()
    def consultar_estados_plato() -> dict:
        """
        Obtiene el catálogo de estados de preparación de un plato en particular.
        
        No modifica información.
        """
        return {
            "ok": True,
            "estados": ["PENDIENTE", "EN_PREPARACION", "LISTO", "ENTREGADO", "CANCELADO"]
        }

    @mcp.tool()
    def consultar_estados_actividad() -> dict:
        """
        Obtiene el catálogo de estados permitidos de una actividad educativa/operativa de cocina.
        
        No modifica información.
        """
        return {
            "ok": True,
            "estados": ["PROGRAMADA", "EN_PROCESO", "COMPLETADA", "CANCELADA"]
        }

    @mcp.tool()
    def consultar_unidades() -> dict:
        """
        Obtiene la lista de unidades de medida estándar aceptadas para los ingredientes en la cocina.
        
        No modifica información.
        """
        return {
            "ok": True,
            "unidades": ["g", "kg", "ml", "L", "unidades", "tazas", "cucharadas", "oz"]
        }

    @mcp.tool()
    def consultar_prioridades() -> dict:
        """
        Obtiene el catálogo de prioridades válidas para las comandas en cocina.
        
        No modifica información.
        """
        return {
            "ok": True,
            "prioridades": ["BAJA", "MEDIA", "ALTA"]
        }

    @mcp.tool()
    def consultar_tipos_incidencia() -> dict:
        """
        Obtiene el catálogo de los tipos de incidencias que se pueden reportar en cocina.
        
        No modifica información.
        """
        return {
            "ok": True,
            "tipos": ["FALTA_INGREDIENTE", "RETRASO_PREPARACION", "ERROR_PLATO", "ACCIDENTE_COCINA", "FALLO_EQUIPO", "OTRO"]
        }

    # ==========================================
    # ---------- RESUMEN OPERATIVO -------------
    # ==========================================

    @mcp.tool()
    @_manejar_errores
    def resumen_cocina() -> dict:
        """
        Obtiene un resumen cuantitativo del estado actual de la cocina (comandas activas por estado e incidencias).
        Útil para responder preguntas globales rápidamente.
        
        No modifica información.
        """
        try:
            c_resp = _get("/cocina/comandas")
            comandas = c_resp if isinstance(c_resp, list) else c_resp.get("contenido", [])
        except Exception:
            comandas = []
            
        try:
            i_resp = _get("/cocina/incidencias")
            incidencias = i_resp if isinstance(i_resp, list) else i_resp.get("contenido", [])
        except Exception:
            incidencias = []
            
        pendientes = 0
        en_preparacion = 0
        listas = 0
        
        for c in comandas:
            estado = str(c.get("estado", c.get("estadoPreparacion", ""))).upper()
            if "PEND" in estado:
                pendientes += 1
            elif "PREP" in estado or "PROCESO" in estado:
                en_preparacion += 1
            elif "LIST" in estado:
                listas += 1
                
        return {
            "ok": True,
            "resumen": {
                "comandas_pendientes": pendientes,
                "comandas_en_preparacion": en_preparacion,
                "comandas_listas": listas,
                "incidencias": len(incidencias)
            }
        }

    # ==========================================
    # ---------- CAPACIDADES -------------------
    # ==========================================

    @mcp.tool()
    def capacidades_cocina() -> dict:
        """
        Obtiene las capacidades, módulos y tipos de acciones disponibles para interactuar con la cocina.
        
        No modifica información.
        """
        return {
            "ok": True,
            "capacidades": {
                "modulos": [
                    "Recetas",
                    "Ingredientes",
                    "Comandas",
                    "Incidencias",
                    "Actividades"
                ],
                "acciones": [
                    "Consultar",
                    "Crear",
                    "Actualizar",
                    "Reportar",
                    "Evaluar"
                ]
            }
        }
