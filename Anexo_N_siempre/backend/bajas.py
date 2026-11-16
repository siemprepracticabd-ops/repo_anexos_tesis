"""endpoints de baja, reactivacion y licencias (permisos y suspensiones) de colaboradores"""

from datetime import date, timedelta
from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db
from jornadas import FECHA_MINIMA, leer_fecha
from pendientes import MAX_TEXTO, texto
from resoluciones import responder_error

bp = Blueprint("bajas", __name__, url_prefix="/api/colaboradores")

DIAS_ADELANTE = 60


def fecha_valida(valor, adelante=DIAS_ADELANTE):
    """devuelve la fecha si esta entre 2024 y unos dias en el futuro; si no, none"""
    dia = leer_fecha(valor)
    if dia is None or dia < FECHA_MINIMA or dia > date.today() + timedelta(days=adelante):
        return None
    return dia


@bp.post("/<uuid:colaborador_id>/baja")
@requiere_rol("rrhh")
def dar_de_baja(colaborador_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    fecha = fecha_valida(datos.get("fecha"))
    if fecha is None:
        errores["fecha"] = "Fecha inválida"
    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo es obligatorio (hasta 500 caracteres)"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "dar_de_baja",
                {
                    "p_colaborador": str(colaborador_id),
                    "p_fecha": fecha.isoformat(),
                    "p_motivo": motivo,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(respuesta.data)


@bp.post("/<uuid:colaborador_id>/reactivacion")
@requiere_rol("rrhh")
def reactivar(colaborador_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    fecha = fecha_valida(datos.get("fecha"))
    if fecha is None:
        return jsonify(error="datos inválidos", campos={"fecha": "Fecha inválida"}), 422

    try:
        get_db().rpc(
            "reactivar_colaborador",
            {"p_colaborador": str(colaborador_id), "p_fecha": fecha.isoformat(), "p_usuario": g.usuario["id"]},
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)


@bp.post("/<uuid:colaborador_id>/licencias")
@requiere_rol("rrhh")
def registrar_licencia(colaborador_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    try:
        tipo_id = str(UUID(str(datos.get("tipo_id"))))
    except ValueError:
        tipo_id = None
        errores["tipo_id"] = "Elige el tipo"

    desde = fecha_valida(datos.get("desde"), adelante=366)
    hasta = fecha_valida(datos.get("hasta"), adelante=366)
    if desde is None:
        errores["desde"] = "Fecha inválida"
    if hasta is None:
        errores["hasta"] = "Fecha inválida"
    if desde and hasta and hasta < desde:
        errores["hasta"] = "No puede ser antes del inicio"

    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo es obligatorio (hasta 500 caracteres)"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "registrar_licencia",
                {
                    "p_colaborador": str(colaborador_id),
                    "p_tipo": tipo_id,
                    "p_desde": desde.isoformat(),
                    "p_hasta": hasta.isoformat(),
                    "p_motivo": motivo,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(id=respuesta.data), 201


@bp.delete("/licencias/<uuid:licencia_id>")
@requiere_rol("rrhh")
def anular_licencia(licencia_id):
    try:
        get_db().rpc("anular_licencia", {"p_licencia": str(licencia_id), "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)
