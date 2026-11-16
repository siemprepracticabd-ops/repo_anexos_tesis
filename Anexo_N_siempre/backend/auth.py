from functools import wraps

from flask import g, jsonify, request

from db import get_db


def usuario_actual():
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        return None

    try:
        respuesta = get_db().auth.get_user(cabecera[7:].strip())
        usuario = respuesta.user if respuesta else None
    except Exception:
        return None
    if usuario is None:
        return None

    perfil = (
        get_db()
        .table("profiles")
        .select("full_name, role")
        .eq("id", usuario.id)
        .limit(1)
        .execute()
    )
    fila = perfil.data[0] if perfil.data else {}
    return {"id": usuario.id, "nombre": fila.get("full_name"), "rol": fila.get("role")}


def requiere_rol(*roles):
    def decorador(funcion):
        @wraps(funcion)
        def envuelta(*args, **kwargs):
            usuario = usuario_actual()
            if usuario is None:
                return jsonify(error="no autenticado"), 401
            if usuario["rol"] not in roles:
                return jsonify(error="sin permiso"), 403
            g.usuario = usuario
            return funcion(*args, **kwargs)

        return envuelta

    return decorador
