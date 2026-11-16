"""endpoints de pendientes: decidir las horas extra y justificar las ausencias"""

from decimal import Decimal, InvalidOperation
from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("pendientes", __name__, url_prefix="/api")

DECISIONES = ("autorizada", "parcial", "rechazada")
MAX_TEXTO = 500


def texto(valor):
    return str(valor or "").strip()


def minutos(valor):
    """devuelve un entero de minutos mayores que 0, o none si no sirve"""
    try:
        numero = Decimal(str(valor))
        if numero == numero.to_integral_value() and 0 < numero <= 24 * 60:
            return int(numero)
    except InvalidOperation:
        pass
    return None


@bp.put("/horas-extra/<uuid:horas_extra_id>/decision")
@requiere_rol("rrhh", "jefe")
def decidir_horas_extra(horas_extra_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    decision = texto(datos.get("decision"))
    if decision not in DECISIONES:
        errores["decision"] = "Elige autorizar, autorizar parcial o rechazar"

    justificacion = texto(datos.get("justificacion"))
    if not justificacion or len(justificacion) > MAX_TEXTO:
        errores["justificacion"] = "La justificación es obligatoria (hasta 500 caracteres)"

    pagados = None
    if decision == "parcial":
        pagados = minutos(datos.get("minutos_pagados"))
        if pagados is None:
            errores["minutos_pagados"] = "Indica los minutos que se pagan"

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
            "resolver_horas_extra",
            {
                "p_horas_extra": str(horas_extra_id),
                "p_decision": decision,
                "p_minutos_pagados": pagados,
                "p_justificacion": justificacion,
                "p_autorizado_por": autorizado_por,
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        if error.code == "P0002":
            return jsonify(error="El registro de horas extra no existe"), 404
        if error.code == "55000":
            return jsonify(error="Esa quincena ya está cerrada"), 409
        if error.code == "22023":
            return jsonify(error=error.message), 422
        raise

    return jsonify(ok=True)


@bp.put("/ausencias/<uuid:ausencia_id>/justificacion")
@requiere_rol("rrhh")
def justificar_ausencia(ausencia_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    try:
        tipo_id = str(UUID(str(datos.get("tipo_id"))))
    except ValueError:
        tipo_id = None
        errores["tipo_id"] = "Elige el tipo de ausencia"

    motivo = texto(datos.get("motivo"))
    if not motivo or len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo es obligatorio (hasta 500 caracteres)"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "justificar_ausencia",
            {"p_ausencia": str(ausencia_id), "p_tipo": tipo_id, "p_motivo": motivo, "p_usuario": g.usuario["id"]},
        ).execute()
    except APIError as error:
        if error.code == "P0002":
            return jsonify(error="La ausencia no existe"), 404
        if error.code == "55000":
            return jsonify(error="Esa quincena ya está cerrada"), 409
        if error.code == "23503":
            return jsonify(error="datos inválidos", campos={"tipo_id": "El tipo de ausencia no existe"}), 422
        if error.code == "22023":
            return jsonify(error=error.message), 422
        raise

    return jsonify(ok=True)