"""alta de relojes: el jefe registra el numero de serie y recibe la clave que se instala en el agente"""

import hashlib
import re
import secrets
from uuid import UUID

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("relojes", __name__, url_prefix="/api/relojes")

SERIE = re.compile(r"^[A-Za-z0-9._-]{4,40}$")
MAX_TEXTO = 60


def limpiar(valor):
    return valor.strip() if isinstance(valor, str) else ""


def clave_nueva():
    """devuelve (clave, hash)"""
    clave = secrets.token_urlsafe(32)
    return clave, hashlib.sha256(clave.encode()).hexdigest()


def anotar(accion, reloj_id, detalle):
    get_db().table("bitacora").insert(
        {
            "usuario_id": g.usuario["id"],
            "accion": accion,
            "tabla": "dispositivos",
            "registro_id": reloj_id,
            "detalle": detalle,
        }
    ).execute()


def obtener_o_crear_sucursal(db, nombre):
    """usa la sucursal que ya tenga ese nombre (sin importar mayusculas) o la crea"""
    existente = db.table("sucursales").select("id").ilike("nombre", nombre.replace("%", "").replace("_", "")).execute().data
    for fila in existente:
        return fila["id"]
    try:
        fila = db.table("sucursales").insert({"nombre": nombre}).execute().data[0]
    except APIError as error:
        if error.code != "23505":
            raise
        return db.table("sucursales").select("id").eq("nombre", nombre).limit(1).execute().data[0]["id"]
    anotar_sucursal(fila["id"], nombre)
    return fila["id"]


def anotar_sucursal(sucursal_id, nombre):
    get_db().table("bitacora").insert(
        {
            "usuario_id": g.usuario["id"],
            "accion": "crear",
            "tabla": "sucursales",
            "registro_id": sucursal_id,
            "detalle": {"nombre": nombre},
        }
    ).execute()


@bp.post("")
@requiere_rol("jefe")
def registrar():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    errores = {}
    serie = limpiar(datos.get("serie"))
    if not SERIE.match(serie):
        errores["serie"] = "El número de serie debe tener de 4 a 40 letras, números, punto, guion o guion bajo"
    nombre = limpiar(datos.get("nombre"))
    if not nombre or len(nombre) > MAX_TEXTO:
        errores["nombre"] = "El nombre es obligatorio (hasta 60 caracteres)"
    modelo = limpiar(datos.get("modelo")) or None
    if modelo and len(modelo) > MAX_TEXTO:
        errores["modelo"] = "El modelo es demasiado largo"
    sucursal_id = None
    sucursal_nueva = limpiar(datos.get("sucursal_nueva"))
    if sucursal_nueva:
        if len(sucursal_nueva) < 2 or len(sucursal_nueva) > MAX_TEXTO:
            errores["sucursal_nueva"] = "El nombre de la sucursal debe tener de 2 a 60 caracteres"
    else:
        try:
            sucursal_id = str(UUID(str(datos.get("sucursal_id"))))
        except ValueError:
            errores["sucursal_id"] = "Elige la sucursal o escribe el nombre de una nueva"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    db = get_db()
    if sucursal_nueva:
        sucursal_id = obtener_o_crear_sucursal(db, sucursal_nueva)
    elif not db.table("sucursales").select("id").eq("id", sucursal_id).limit(1).execute().data:
        return jsonify(error="datos inválidos", campos={"sucursal_id": "La sucursal no existe"}), 422

    clave, clave_hash = clave_nueva()
    try:
        fila = (
            db.table("dispositivos")
            .insert(
                {
                    "sucursal_id": sucursal_id,
                    "serie": serie,
                    "nombre": nombre,
                    "modelo": modelo,
                    "api_key_hash": clave_hash,
                }
            )
            .execute()
            .data[0]
        )
    except APIError as error:
        if error.code == "23505":
            return jsonify(error="datos inválidos", campos={"serie": "Ya hay un reloj con ese número de serie"}), 422
        raise

    anotar("crear", fila["id"], {"serie": serie, "nombre": nombre, "sucursal_id": sucursal_id})
    return jsonify(id=fila["id"], serie=serie, api_key=clave), 201


@bp.post("/<uuid:reloj_id>/clave")
@requiere_rol("jefe")
def regenerar_clave(reloj_id):
    clave, clave_hash = clave_nueva()
    filas = (
        get_db()
        .table("dispositivos")
        .update({"api_key_hash": clave_hash})
        .eq("id", str(reloj_id))
        .execute()
        .data
    )
    if not filas:
        return jsonify(error="reloj no encontrado"), 404

    anotar("regenerar_clave", str(reloj_id), {"serie": filas[0]["serie"]})
    return jsonify(id=filas[0]["id"], serie=filas[0]["serie"], api_key=clave)


@bp.post("/<uuid:reloj_id>/estado")
@requiere_rol("jefe")
def cambiar_estado(reloj_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or not isinstance(datos.get("activo"), bool):
        return jsonify(error="datos inválidos", campos={"activo": "Indica si el reloj queda activo"}), 422

    filas = (
        get_db()
        .table("dispositivos")
        .update({"activo": datos["activo"]})
        .eq("id", str(reloj_id))
        .execute()
        .data
    )
    if not filas:
        return jsonify(error="reloj no encontrado"), 404

    anotar("activar" if datos["activo"] else "desactivar", str(reloj_id), {"serie": filas[0]["serie"]})
    return jsonify(id=filas[0]["id"], activo=filas[0]["activo"])
