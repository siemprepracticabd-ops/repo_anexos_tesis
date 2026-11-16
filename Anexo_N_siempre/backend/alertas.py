"""endpoint para resolver alertas"""

from flask import Blueprint, g, jsonify
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db
from resoluciones import responder_error

bp = Blueprint("alertas", __name__, url_prefix="/api/alertas")


@bp.post("/<uuid:alerta_id>/resolver")
@requiere_rol("rrhh", "jefe")
def resolver(alerta_id):
    try:
        get_db().rpc("resolver_alerta", {"p_alerta": str(alerta_id), "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        return responder_error(error)

    return jsonify(ok=True)
