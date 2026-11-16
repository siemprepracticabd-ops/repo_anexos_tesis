"""consulta de la bitacora: quien hizo que y cuando"""

import re
from datetime import datetime, time, timedelta
from uuid import UUID

from flask import Blueprint, jsonify, request

from auth import requiere_rol
from bitacora_texto import UUID_TEXTO, Contexto, describir, lineas
from calendarios import GUATEMALA
from db import get_db
from jornadas import FECHA_MINIMA, leer_fecha

bp = Blueprint("bitacora", __name__, url_prefix="/api/bitacora")

POR_PAGINA = 50
PAGINA_MAXIMA = 1000
NOMBRE = re.compile(r"^[a-z_]{1,40}$")


def ids_de(filas, tablas=None, claves=("colaborador_id", "dispositivo_id", "desde")):
    """ids que aparecen en las filas: en el detalle y, si la tabla es de las pedidas, en registro_id"""
    encontrados = set()
    for f in filas:
        detalle = f.get("detalle") or {}
        for clave in claves:
            if isinstance(detalle.get(clave), str) and UUID_TEXTO.match(detalle[clave]):
                encontrados.add(detalle[clave])
        if f.get("registro_id") and UUID_TEXTO.match(str(f["registro_id"])) and (tablas is None or f["tabla"] in tablas):
            encontrados.add(f["registro_id"])
    return list(encontrados)


def leer(db, tabla, columnas, ids):
    if not ids:
        return []
    return db.table(tabla).select(columnas).in_("id", ids).execute().data or []


def armar_contexto(db, filas):
    """busca los nombres de las personas, relojes, quincenas y programaciones que se mencionan"""
    de_caso = {
        "horas_extra": ("horas_extra", "id, jornadas(fecha, colaborador_id)", lambda r: r["jornadas"]),
        "ausencias": ("ausencias", "id, fecha, colaborador_id", lambda r: r),
        "jornadas": ("jornadas", "id, fecha, colaborador_id", lambda r: r),
        "alertas": ("alertas", "id, tipo, fecha, colaborador_id", lambda r: r),
        "descuentos_tiempo": ("descuentos_tiempo", "id, fecha_inicio, colaborador_id", lambda r: {**r, "fecha": r["fecha_inicio"]}),
    }
    casos = {}
    for tabla, (nombre, columnas, datos) in de_caso.items():
        for r in leer(db, nombre, columnas, ids_de([f for f in filas if f["tabla"] == tabla], {tabla}, ())):
            try:
                base = datos(r) or {}
            except (KeyError, TypeError):
                continue
            casos[r["id"]] = {"colaborador_id": base.get("colaborador_id"), "fecha": base.get("fecha"), "tipo": r.get("tipo")}

    ids_personas = set(ids_de(filas, {"colaboradores", "colaborador_dispositivo", "ajustes_planilla", "dias_diurno"}))
    ids_personas |= {c["colaborador_id"] for c in casos.values() if c["colaborador_id"]}
    personas = {
        r["id"]: f"{r['nombres']} {r['apellidos']}".strip()
        for r in leer(db, "colaboradores", "id, nombres, apellidos", list(ids_personas))
    }
    for c in casos.values():
        c["persona"] = personas.get(c["colaborador_id"])

    relojes = {r["id"]: r["nombre"] for r in leer(db, "dispositivos", "id, nombre", ids_de(filas, {"dispositivos"}))}
    periodos = {
        r["id"]: f"del {r['fecha_inicio'][8:]}/{r['fecha_inicio'][5:7]}/{r['fecha_inicio'][:4]} al "
                 f"{r['fecha_fin'][8:]}/{r['fecha_fin'][5:7]}/{r['fecha_fin'][:4]}"
        for r in leer(db, "periodos_planilla", "id, fecha_inicio, fecha_fin",
                      ids_de([f for f in filas if f["tabla"] == "periodos_planilla"], {"periodos_planilla"}, ()))
    }
    programaciones = {}
    for r in leer(db, "programaciones", "id, tipo, fecha_inicio, fecha_fin, version",
                  ids_de(filas, {"programaciones", "asignaciones_turno"})):
        programaciones[r["id"]] = (
            f"{r['tipo']} del {r['fecha_inicio'][8:]}/{r['fecha_inicio'][5:7]} al "
            f"{r['fecha_fin'][8:]}/{r['fecha_fin'][5:7]}/{r['fecha_fin'][:4]}"
        )
    return Contexto(personas, relojes, periodos, programaciones, casos)


def medianoche(dia):
    return datetime.combine(dia, time.min, tzinfo=GUATEMALA)


@bp.get("")
@requiere_rol("rrhh", "jefe")
def listar():
    errores = {}

    desde = leer_fecha(request.args.get("desde")) if request.args.get("desde") else None
    hasta = leer_fecha(request.args.get("hasta")) if request.args.get("hasta") else None
    if request.args.get("desde") and (desde is None or desde < FECHA_MINIMA):
        errores["desde"] = "Fecha inválida"
    if request.args.get("hasta") and hasta is None:
        errores["hasta"] = "Fecha inválida"

    usuario = request.args.get("usuario")
    if usuario:
        try:
            usuario = str(UUID(usuario))
        except ValueError:
            errores["usuario"] = "Usuario inválido"

    accion = request.args.get("accion", "")
    tabla = request.args.get("tabla", "")
    if accion and not NOMBRE.match(accion):
        errores["accion"] = "Acción inválida"
    if tabla and not NOMBRE.match(tabla):
        errores["tabla"] = "Tabla inválida"

    try:
        pagina = int(request.args.get("pagina", "1"))
        if not 1 <= pagina <= PAGINA_MAXIMA:
            raise ValueError
    except ValueError:
        pagina = 1
        errores["pagina"] = "Página inválida"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    consulta = (
        get_db()
        .table("bitacora")
        .select("id, accion, tabla, registro_id, detalle, creado_en, profiles(full_name)")
        .order("creado_en", desc=True)
    )
    if desde:
        consulta = consulta.gte("creado_en", medianoche(desde).isoformat())
    if hasta:
        consulta = consulta.lt("creado_en", medianoche(hasta + timedelta(days=1)).isoformat())
    if usuario:
        consulta = consulta.eq("usuario_id", usuario)
    if accion:
        consulta = consulta.eq("accion", accion)
    if tabla:
        consulta = consulta.eq("tabla", tabla)

    inicio = (pagina - 1) * POR_PAGINA
    filas = consulta.range(inicio, inicio + POR_PAGINA).execute().data

    pagina_filas = filas[:POR_PAGINA]
    contexto = armar_contexto(get_db(), pagina_filas)

    return jsonify(
        filas=[
            {
                "id": f["id"],
                "accion": f["accion"],
                "tabla": f["tabla"],
                "descripcion": describir(f, contexto),
                "detalle": [{"etiqueta": e, "valor": v} for e, v in lineas(f["detalle"], contexto)],
                "creado_en": f["creado_en"],
                "usuario": (f.get("profiles") or {}).get("full_name"),
            }
            for f in pagina_filas
        ],
        hay_mas=len(filas) > POR_PAGINA,
    )


@bp.get("/opciones")
@requiere_rol("rrhh", "jefe")
def opciones():
    db = get_db()
    recientes = db.table("bitacora").select("accion, tabla").order("creado_en", desc=True).limit(1000).execute().data
    usuarios = db.table("profiles").select("id, full_name").order("full_name").execute().data
    return jsonify(
        acciones=sorted({f["accion"] for f in recientes}),
        tablas=sorted({f["tabla"] for f in recientes}),
        usuarios=[{"id": u["id"], "nombre": u["full_name"]} for u in usuarios],
    )
