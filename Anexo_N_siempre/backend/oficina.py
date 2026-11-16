"""horario de la oficina (modalidad diurna): rr hh marca quien trabaja o descansa cada dia"""

from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from bajas import fecha_valida
from db import get_db
from pendientes import texto
from resoluciones import responder_error

bp = Blueprint("oficina", __name__, url_prefix="/api/oficina")

TIPOS = ("trabaja", "libre")
MAX_MOTIVO = 200


@bp.put("/dias")
@requiere_rol("rrhh")
def guardar_dia():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    try:
        colaborador = str(UUID(str(datos.get("colaborador_id"))))
    except ValueError:
        colaborador = None
        errores["colaborador_id"] = "Colaborador inválido"
    fecha = fecha_valida(datos.get("fecha"))
    if fecha is None:
        errores["fecha"] = "Fecha inválida"
    tipo = datos.get("tipo")
    if tipo is not None and tipo not in TIPOS:
        errores["tipo"] = "El tipo debe ser trabaja, libre o vacío para volver al horario base"
    motivo = texto(datos.get("motivo")) if datos.get("motivo") else ""
    if len(motivo) > MAX_MOTIVO:
        errores["motivo"] = "El motivo es demasiado largo"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = (
            get_db()
            .rpc(
                "guardar_dia_diurno",
                {
                    "p_colaborador": colaborador,
                    "p_fecha": fecha.isoformat(),
                    "p_tipo": tipo,
                    "p_motivo": motivo,
                    "p_usuario": g.usuario["id"],
                },
            )
            .execute()
        )
    except APIError as error:
        return responder_error(error)

    return jsonify(respuesta.data)
