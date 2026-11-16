"""endpoints de programacion de turnos"""

from calendar import monthrange
from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("programaciones", __name__, url_prefix="/api/programaciones")

TIPOS = ("semanal", "quincenal")
FECHA_MINIMA = date(2024, 1, 1)


def calcular_periodo(tipo, texto):
    """devuelve (inicio, fin) de la programacion, o lanza valueerror con el motivo"""
    try:
        inicio = date.fromisoformat(texto)
    except ValueError:
        raise ValueError("Fecha inválida")

    if inicio < FECHA_MINIMA or inicio > date.today() + timedelta(days=366):
        raise ValueError("Fecha fuera de rango")

    if tipo == "semanal":
        if inicio.weekday() != 0:
            raise ValueError("La semana debe empezar en lunes")
        return inicio, inicio + timedelta(days=6)

    if tipo == "quincenal":
        if inicio.day == 1:
            return inicio, inicio.replace(day=15)
        if inicio.day == 16:
            return inicio, inicio.replace(day=monthrange(inicio.year, inicio.month)[1])
        raise ValueError("La quincena debe empezar el día 1 o el 16")

    raise ValueError("Tipo inválido")


@bp.post("")
@requiere_rol("rrhh")
def crear():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    tipo = str(datos.get("tipo") or "")
    if tipo not in TIPOS:
        return jsonify(error="datos inválidos", campos={"tipo": "Elige semanal o quincenal"}), 422

    try:
        inicio, fin = calcular_periodo(tipo, str(datos.get("fecha_inicio") or ""))
    except ValueError as motivo:
        return jsonify(error="datos inválidos", campos={"fecha_inicio": str(motivo)}), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "crear_programacion",
                {
                    "p_tipo": tipo,
                    "p_inicio": inicio.isoformat(),
                    "p_fin": fin.isoformat(),
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        if error.code == "23505":
            return jsonify(error="Ya existe una programación para ese período"), 409
        raise

    return jsonify(id=respuesta.data), 201


MAX_MOTIVO = 500


@bp.post("/<uuid:programacion_id>/publicar")
@requiere_rol("rrhh")
def publicar(programacion_id):
    datos = request.get_json(silent=True)
    motivo = str(datos.get("motivo") or "").strip() if isinstance(datos, dict) else ""
    if len(motivo) > MAX_MOTIVO:
        return jsonify(error="El motivo es demasiado largo"), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "publicar_programacion",
                {
                    "p_programacion": str(programacion_id),
                    "p_motivo": motivo or None,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        if error.code == "P0002":
            return jsonify(error="La programación no existe"), 404
        if error.code == "55000":
            return jsonify(error="La programación ya no es un borrador"), 409
        if error.code == "22023":
            return jsonify(error=error.message), 422
        raise

    return jsonify(version=respuesta.data)


@bp.post("/<uuid:programacion_id>/versiones")
@requiere_rol("rrhh")
def crear_version(programacion_id):
    try:
        respuesta = (
            get_db()
            .rpc(
                "crear_version_programacion",
                {"p_programacion": str(programacion_id), "p_usuario": g.usuario["id"]},
            )
            .execute()
        )
    except APIError as error:
        if error.code == "P0002":
            return jsonify(error="La programación no existe"), 404
        if error.code == "55000":
            return jsonify(error="Solo se puede crear una versión desde una programación publicada"), 409
        if error.code == "23505":
            return jsonify(error="Ya hay una versión en borrador para este período"), 409
        raise

    return jsonify(id=respuesta.data), 201