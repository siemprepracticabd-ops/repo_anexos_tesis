"""endpoints de la planilla: vista previa del pago y valores de hora editables por quincena"""

from decimal import Decimal, InvalidOperation
from datetime import date
from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db
from jornadas import FECHA_MINIMA, leer_fecha
from pendientes import MAX_TEXTO, texto
from resoluciones import responder_error

bp = Blueprint("planilla", __name__, url_prefix="/api/planilla")

DIAS_MAXIMOS_PLANILLA = 32
VALOR_MAXIMO = Decimal("100000")
MAX_MOTIVO_DESCUENTO = 200


def leer_periodo(desde, hasta):
    """devuelve (desde, hasta, errores) a partir de dos textos aaaa-mm-dd"""
    desde = leer_fecha(desde)
    hasta = leer_fecha(hasta)
    errores = {}
    if desde is None or desde < FECHA_MINIMA:
        errores["desde"] = "Fecha inválida"
    if hasta is None:
        errores["hasta"] = "Fecha inválida"
    if not errores and (hasta < desde or (hasta - desde).days >= DIAS_MAXIMOS_PLANILLA):
        errores["hasta"] = "El período debe ser de 1 a 31 días"
    return desde, hasta, errores


def leer_valor(dato):
    """devuelve (valor, error)"""
    if dato is None or str(dato).strip() == "":
        return None, False
    try:
        monto = Decimal(str(dato).strip())
    except InvalidOperation:
        return None, True
    if not monto.is_finite() or not 0 < monto <= VALOR_MAXIMO:
        return None, True
    return monto, False


@bp.get("")
@requiere_rol("rrhh", "jefe")
def ver_planilla():
    desde, hasta, errores = leer_periodo(request.args.get("desde"), request.args.get("hasta"))
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc("calcular_planilla", {"p_inicio": desde.isoformat(), "p_fin": hasta.isoformat()})
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(personas=respuesta.data)


@bp.put("/ajustes")
@requiere_rol("rrhh")
def guardar_ajuste():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    desde, hasta, errores = leer_periodo(datos.get("desde"), datos.get("hasta"))

    try:
        colaborador_id = str(UUID(str(datos.get("colaborador_id"))))
    except ValueError:
        colaborador_id = None
        errores["colaborador_id"] = "Elige a la persona"

    valor_hora, mala_hora = leer_valor(datos.get("valor_hora"))
    if mala_hora:
        errores["valor_hora"] = "Debe ser un número mayor que 0"

    valor_extra, mala_extra = leer_valor(datos.get("valor_hora_extra"))
    if mala_extra:
        errores["valor_hora_extra"] = "Debe ser un número mayor que 0"

    motivo = texto(datos.get("motivo"))
    if len(motivo) > MAX_TEXTO:
        errores["motivo"] = "El motivo no puede pasar de 500 caracteres"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "guardar_ajuste_planilla",
            {
                "p_inicio": desde.isoformat(),
                "p_fin": hasta.isoformat(),
                "p_colaborador": colaborador_id,
                "p_valor_hora": str(valor_hora) if valor_hora is not None else None,
                "p_valor_extra": str(valor_extra) if valor_extra is not None else None,
                "p_motivo": motivo or None,
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)

@bp.post("/descuentos")
@requiere_rol("rrhh", "jefe")
def agregar_descuento():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    desde, hasta, errores = leer_periodo(datos.get("desde"), datos.get("hasta"))

    try:
        colaborador_id = str(UUID(str(datos.get("colaborador_id"))))
    except ValueError:
        colaborador_id = None
        errores["colaborador_id"] = "Elige a la persona"

    monto, malo = leer_valor(datos.get("monto"))
    if malo or monto is None:
        errores["monto"] = "Debe ser un número mayor que 0"

    motivo = texto(datos.get("motivo"))
    if len(motivo) < 3 or len(motivo) > MAX_MOTIVO_DESCUENTO:
        errores["motivo"] = "El motivo es obligatorio (de 3 a 200 caracteres)"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = get_db().rpc(
            "agregar_descuento_manual",
            {
                "p_colaborador": colaborador_id,
                "p_inicio": desde.isoformat(),
                "p_fin": hasta.isoformat(),
                "p_monto": str(monto),
                "p_motivo": motivo,
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(id=respuesta.data), 201


@bp.delete("/descuentos/<uuid:descuento_id>")
@requiere_rol("rrhh", "jefe")
def quitar_descuento(descuento_id):
    try:
        get_db().rpc(
            "quitar_descuento_manual",
            {"p_id": str(descuento_id), "p_usuario": g.usuario["id"]},
        ).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)


@bp.post("/cierre")
@requiere_rol("jefe")
def cerrar_quincena():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    desde, hasta, errores = leer_periodo(datos.get("desde"), datos.get("hasta"))
    if not errores and hasta >= date.today():
        errores["hasta"] = "La quincena todavía no termina"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "cerrar_planilla",
                {"p_inicio": desde.isoformat(), "p_fin": hasta.isoformat(), "p_usuario": g.usuario["id"]},
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(respuesta.data), 201


@bp.post("/periodos/<uuid:periodo_id>/pago")
@requiere_rol("rrhh")
def pagar_boletas(periodo_id):
    try:
        respuesta = (
            get_db()
            .rpc("marcar_boletas_pagadas", {"p_periodo": str(periodo_id), "p_usuario": g.usuario["id"]})
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(boletas=respuesta.data)