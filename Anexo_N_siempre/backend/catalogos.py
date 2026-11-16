"""endpoints de los catalogos: puestos y turnos"""

from datetime import time
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("catalogos", __name__, url_prefix="/api")

TIPOS_DE_JORNADA = ("diurna", "mixta", "nocturna")


def limpiar(valor):
    """quita espacios sobrantes: ' ana maria ' -> 'ana maria'"""
    return " ".join(str(valor or "").split())


def leer_hora(valor):
    """convierte '07:00' o '07:00:00' en 'hh:mm', o devuelve none si no sirve"""
    try:
        hora = time.fromisoformat(str(valor))
    except ValueError:
        return None
    return hora.strftime("%H:%M")


def leer_horas(valor):
    """devuelve las horas ordinarias como decimal (mayor que 0 y hasta 24), o none"""
    try:
        horas = Decimal(str(valor))
        return horas if 0 < horas <= 24 else None
    except InvalidOperation:
        return None


def responder_error(error, mensajes):
    """traduce un error de la base a una respuesta"""
    if error.code not in mensajes:
        raise error
    estado, texto = mensajes[error.code]
    return jsonify(error=texto or error.message), estado


ERRORES = {
    "P0002": (404, "No existe"),
    "23505": (409, None),
    "23503": (409, None),
    "55000": (409, None),
    "22023": (422, None),
    "23514": (422, "Los datos no son válidos"),
}


def validar_nombre(datos):
    nombre = limpiar(datos.get("nombre"))
    if not 2 <= len(nombre) <= 60:
        return None, {"nombre": "Debe tener entre 2 y 60 caracteres"}
    return nombre, {}


# ---------------------------------------------------------------- puestos


@bp.post("/puestos")
@requiere_rol("rrhh")
def crear_puesto():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    nombre, errores = validar_nombre(datos)
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = get_db().rpc("crear_puesto", {"p_nombre": nombre, "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(id=respuesta.data), 201


@bp.put("/puestos/<uuid:puesto_id>")
@requiere_rol("rrhh")
def renombrar_puesto(puesto_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    nombre, errores = validar_nombre(datos)
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "renombrar_puesto", {"p_id": str(puesto_id), "p_nombre": nombre, "p_usuario": g.usuario["id"]}
        ).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(ok=True)


@bp.delete("/puestos/<uuid:puesto_id>")
@requiere_rol("rrhh")
def eliminar_puesto(puesto_id):
    try:
        get_db().rpc("eliminar_puesto", {"p_id": str(puesto_id), "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(ok=True)


# ----------------------------------------------------------------- turnos


def validar_turno(datos):
    """revisa y limpia los datos de un turno"""
    nombre, errores = validar_nombre(datos)

    inicio = leer_hora(datos.get("hora_inicio"))
    if inicio is None:
        errores["hora_inicio"] = "Hora inválida (por ejemplo 07:00)"

    fin = leer_hora(datos.get("hora_fin"))
    if fin is None:
        errores["hora_fin"] = "Hora inválida (por ejemplo 17:00)"

    tipo = str(datos.get("tipo_jornada") or "")
    if tipo not in TIPOS_DE_JORNADA:
        errores["tipo_jornada"] = "Elige diurna, mixta o nocturna"

    horas = leer_horas(datos.get("horas_ordinarias"))
    if horas is None:
        errores["horas_ordinarias"] = "Debe ser mayor que 0 y no pasar de 24"

    valores = {"p_nombre": nombre, "p_inicio": inicio, "p_fin": fin, "p_tipo": tipo, "p_horas": str(horas)}
    return valores, errores


@bp.post("/turnos")
@requiere_rol("rrhh")
def crear_turno():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    valores, errores = validar_turno(datos)
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = get_db().rpc("crear_turno", {**valores, "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(id=respuesta.data), 201


@bp.put("/turnos/<uuid:turno_id>")
@requiere_rol("rrhh")
def editar_turno(turno_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    valores, errores = validar_turno(datos)
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc("editar_turno", {"p_id": str(turno_id), **valores, "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(ok=True)


@bp.patch("/turnos/<uuid:turno_id>/estado")
@requiere_rol("rrhh")
def cambiar_estado_turno(turno_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or not isinstance(datos.get("activo"), bool):
        return jsonify(error="datos inválidos", campos={"activo": "Indica true o false"}), 422

    try:
        get_db().rpc(
            "cambiar_estado_turno",
            {"p_id": str(turno_id), "p_activo": datos["activo"], "p_usuario": g.usuario["id"]},
        ).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(ok=True)


@bp.delete("/turnos/<uuid:turno_id>")
@requiere_rol("rrhh")
def eliminar_turno(turno_id):
    try:
        get_db().rpc("eliminar_turno", {"p_id": str(turno_id), "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error, ERRORES)
    return jsonify(ok=True)