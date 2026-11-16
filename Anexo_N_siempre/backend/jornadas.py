"""endpoint que calcula las jornadas (asistencia) de un rango de fechas"""

from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("jornadas", __name__, url_prefix="/api/jornadas")

FECHA_MINIMA = date(2024, 1, 1)
DIAS_MAXIMOS = 62


def leer_fecha(texto):
    """convierte un texto aaaa-mm-dd en fecha, o devuelve none si no sirve"""
    try:
        return date.fromisoformat(str(texto or ""))
    except ValueError:
        return None


@bp.post("/calcular")
@requiere_rol("rrhh")
def calcular():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    desde = leer_fecha(datos.get("desde"))
    hasta = leer_fecha(datos.get("hasta"))

    errores = {}
    if desde is None or desde < FECHA_MINIMA:
        errores["desde"] = "Fecha inválida"
    if hasta is None or hasta > date.today():
        errores["hasta"] = "Fecha inválida: no puede ser futura"
    if not errores and (hasta < desde or (hasta - desde).days >= DIAS_MAXIMOS):
        errores["hasta"] = f"El rango debe ir de 1 a {DIAS_MAXIMOS} días"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "calcular_jornadas",
                {"p_desde": desde.isoformat(), "p_hasta": hasta.isoformat(), "p_usuario": g.usuario["id"]},
            )
            .execute()
        )
    except APIError as error:
        if error.code == "22023":
            return jsonify(error=error.message), 422
        raise

    return jsonify(respuesta.data)