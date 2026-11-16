"""endpoints de asignaciones: guardar las celdas de la parrilla de una programacion"""

from datetime import date
from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("asignaciones", __name__, url_prefix="/api/programaciones")

MAX_CELDAS = 2000
ERRORES_DE_LA_BASE = {
    "P0002": (404, "La programación no existe"),
    "55000": (409, "La programación ya no es un borrador"),
    "23514": (422, "Hay fechas fuera del período, turnos desactivados o celdas repetidas"),
    "23503": (422, "Hay colaboradores, turnos o sucursales que no existen"),
}


def validar_celda(celda):
    """devuelve la celda limpia, o lanza valueerror si algun dato no sirve"""
    if not isinstance(celda, dict):
        raise ValueError("Celda inválida")

    turno = celda.get("turno_id")
    try:
        return {
            "colaborador_id": str(UUID(str(celda.get("colaborador_id")))),
            "sucursal_id": str(UUID(str(celda.get("sucursal_id")))),
            "turno_id": str(UUID(str(turno))) if turno else None,
            "fecha": date.fromisoformat(str(celda.get("fecha"))).isoformat(),
        }
    except ValueError:
        raise ValueError("Celda inválida")


@bp.put("/<uuid:programacion_id>/asignaciones")
@requiere_rol("rrhh")
def guardar(programacion_id):
    datos = request.get_json(silent=True)
    celdas = datos.get("celdas") if isinstance(datos, dict) else None
    if not isinstance(celdas, list) or not celdas or len(celdas) > MAX_CELDAS:
        return jsonify(error="formato inválido"), 400

    try:
        limpias = [validar_celda(celda) for celda in celdas]
    except ValueError as motivo:
        return jsonify(error=str(motivo)), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "guardar_asignaciones",
                {
                    "p_programacion": str(programacion_id),
                    "p_asignaciones": limpias,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        if error.code in ERRORES_DE_LA_BASE:
            estado, mensaje = ERRORES_DE_LA_BASE[error.code]
            return jsonify(error=mensaje), estado
        raise

    return jsonify(guardadas=respuesta.data)