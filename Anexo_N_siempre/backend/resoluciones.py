"""endpoints para resolver lo pendiente antes de cerrar la quincena: descuentos por tardanza"""

from datetime import datetime, time
from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from calendarios import GUATEMALA
from db import get_db
from jornadas import FECHA_MINIMA, leer_fecha
from pendientes import MAX_TEXTO, minutos, texto

bp = Blueprint("resoluciones", __name__, url_prefix="/api")

DECISIONES_DESCUENTO = ("aplicado", "parcial", "no_aplicado")
DIAS_MAXIMOS_DESCUENTOS = 32

ERRORES = {
    "P0002": (404, "No existe"),
    "55000": (409, "Esa quincena ya está cerrada"),
    "22023": (422, None),
}


def responder_error(error):
    """traduce un error de la base"""
    if error.code not in ERRORES:
        raise error
    estado, mensaje = ERRORES[error.code]
    return jsonify(error=mensaje or error.message), estado


@bp.post("/descuentos/preparar")
@requiere_rol("rrhh")
def preparar_descuentos():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    desde = leer_fecha(datos.get("desde"))
    hasta = leer_fecha(datos.get("hasta"))
    errores = {}
    if desde is None or desde < FECHA_MINIMA:
        errores["desde"] = "Fecha inválida"
    if hasta is None:
        errores["hasta"] = "Fecha inválida"
    if not errores and (hasta < desde or (hasta - desde).days >= DIAS_MAXIMOS_DESCUENTOS):
        errores["hasta"] = "El período debe ser de 1 a 31 días"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "preparar_descuentos",
                {"p_inicio": desde.isoformat(), "p_fin": hasta.isoformat(), "p_usuario": g.usuario["id"]},
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(personas=respuesta.data)


@bp.put("/descuentos/<uuid:descuento_id>/decision")
@requiere_rol("rrhh", "jefe")
def decidir_descuento(descuento_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    decision = texto(datos.get("decision"))
    if decision not in DECISIONES_DESCUENTO:
        errores["decision"] = "Elige descontar, descontar una parte o no descontar"

    justificacion = texto(datos.get("justificacion"))
    if not justificacion or len(justificacion) > MAX_TEXTO:
        errores["justificacion"] = "La justificación es obligatoria (hasta 500 caracteres)"

    descontados = None
    if decision == "parcial":
        descontados = minutos(datos.get("minutos_descontados"))
        if descontados is None:
            errores["minutos_descontados"] = "Indica los minutos que se descuentan"

    if g.usuario["rol"] == "jefe":
        autorizado_por = g.usuario["nombre"] or "Jefe"
    else:
        autorizado_por = texto(datos.get("autorizado_por"))
        if not autorizado_por or len(autorizado_por) > 120:
            errores["autorizado_por"] = "Indica quién lo autorizó"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "resolver_descuento",
            {
                "p_id": str(descuento_id),
                "p_decision": decision,
                "p_minutos": descontados,
                "p_justificacion": justificacion,
                "p_autorizado_por": autorizado_por,
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)


@bp.post("/marcaciones-manuales")
@requiere_rol("rrhh")
def agregar_marcacion():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    try:
        colaborador_id = str(UUID(str(datos.get("colaborador_id"))))
    except ValueError:
        colaborador_id = None
        errores["colaborador_id"] = "Elige a la persona"

    dia = leer_fecha(datos.get("fecha"))
    if dia is None or dia < FECHA_MINIMA:
        errores["fecha"] = "Fecha inválida"

    try:
        hora = time.fromisoformat(str(datos.get("hora")))
    except ValueError:
        hora = None
        errores["hora"] = "Hora inválida (por ejemplo 13:03)"

    tipo = texto(datos.get("tipo"))
    if tipo not in ("entrada", "salida"):
        errores["tipo"] = "Elige entrada o salida"

    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo es obligatorio (hasta 500 caracteres)"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    momento = datetime.combine(dia, hora.replace(second=0, microsecond=0), tzinfo=GUATEMALA)
    try:
        respuesta = (
            get_db()
            .rpc(
                "agregar_marcacion_manual",
                {
                    "p_colaborador": colaborador_id,
                    "p_momento": momento.isoformat(),
                    "p_tipo": tipo,
                    "p_motivo": motivo,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(id=respuesta.data), 201


def leer_momento(valor):
    """lee 'aaaa-mm-ddthh:mm' como hora de guatemala; vacio es none, invalido lanza valueerror"""
    if valor in (None, ""):
        return None
    momento = datetime.fromisoformat(str(valor))
    return momento.replace(second=0, microsecond=0, tzinfo=GUATEMALA)


@bp.post("/jornadas/<uuid:jornada_id>/correccion")
@requiere_rol("rrhh")
def corregir_jornada(jornada_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    momentos = {}
    for campo in ("entrada", "salida"):
        try:
            momentos[campo] = leer_momento(datos.get(campo))
        except ValueError:
            momentos[campo] = None
            errores[campo] = "Fecha y hora inválidas"
    if not errores and momentos["entrada"] is None and momentos["salida"] is None:
        errores["entrada"] = "Corrige la entrada o la salida"

    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo es obligatorio (hasta 500 caracteres)"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "corregir_jornada",
            {
                "p_jornada": str(jornada_id),
                "p_entrada": momentos["entrada"].isoformat() if momentos["entrada"] else None,
                "p_salida": momentos["salida"].isoformat() if momentos["salida"] else None,
                "p_motivo": motivo,
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)


@bp.post("/ausencias/<uuid:ausencia_id>/asistencia")
@requiere_rol("rrhh")
def registrar_asistencia(ausencia_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    momentos = {}
    for campo in ("entrada", "salida"):
        try:
            momentos[campo] = leer_momento(datos.get(campo))
        except ValueError:
            momentos[campo] = None
        if momentos[campo] is None:
            errores[campo] = "Indica la hora"

    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo es obligatorio (hasta 500 caracteres)"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "registrar_asistencia_en_ausencia",
                {
                    "p_ausencia": str(ausencia_id),
                    "p_entrada": momentos["entrada"].isoformat(),
                    "p_salida": momentos["salida"].isoformat(),
                    "p_motivo": motivo,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(respuesta.data), 201


@bp.post("/jornadas/<uuid:jornada_id>/confirmacion")
@requiere_rol("rrhh")
def confirmar_jornada(jornada_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        return jsonify(error="datos inválidos", campos={"motivo": "El motivo es obligatorio (hasta 500 caracteres)"}), 422

    try:
        get_db().rpc(
            "confirmar_jornada",
            {"p_jornada": str(jornada_id), "p_motivo": motivo, "p_usuario": g.usuario["id"]},
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)