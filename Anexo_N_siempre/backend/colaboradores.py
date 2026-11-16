"""endpoints de colaboradores: alta, enlace con el reloj y condiciones de pago"""

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db

bp = Blueprint("colaboradores", __name__, url_prefix="/api/colaboradores")

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SALARIO_MAXIMO = Decimal("1000000")
TARIFA_MAXIMA = Decimal("100000")
MODALIDADES = ("tiempo_completo", "parcial_nocturno", "guardia", "diurna")
FORMAS_DE_PAGO = ("salario_fijo", "por_hora", "por_turno")
FECHA_MINIMA_PAGO = date(2024, 1, 1)


def texto(valor):
    """quita espacios sobrantes: ' ana maria ' -> 'ana maria'"""
    return " ".join(str(valor or "").split())


def dinero(valor, maximo):
    """devuelve el monto como decimal si es mayor que 0 y no pasa del maximo; si no, none"""
    try:
        monto = Decimal(str(valor))
        return monto if 0 < monto <= maximo else None
    except InvalidOperation:
        return None


def validar_pago(datos):
    """revisa modalidad, forma de pago y monto"""
    errores = {}

    modalidad = str(datos.get("modalidad") or "tiempo_completo")
    if modalidad not in MODALIDADES:
        errores["modalidad"] = "Elige una modalidad"

    forma = str(datos.get("forma_pago") or "salario_fijo")
    if forma not in FORMAS_DE_PAGO:
        errores["forma_pago"] = "Elige una forma de pago"

    salario = tarifa = None
    if forma == "salario_fijo":
        salario = dinero(datos.get("salario_mensual"), SALARIO_MAXIMO)
        if salario is None:
            errores["salario_mensual"] = "Debe ser un número mayor que 0"
    elif forma in FORMAS_DE_PAGO:
        tarifa = dinero(datos.get("tarifa"), TARIFA_MAXIMA)
        if tarifa is None:
            errores["tarifa"] = "Debe ser un número mayor que 0"

    valores = {
        "p_modalidad": modalidad,
        "p_forma_pago": forma,
        "p_salario": str(salario) if salario is not None else None,
        "p_tarifa": str(tarifa) if tarifa is not None else None,
    }
    return valores, errores


def validar(datos):
    """revisa y limpia lo que llega"""
    errores = {}

    nombres = texto(datos.get("nombres"))
    if not 2 <= len(nombres) <= 80:
        errores["nombres"] = "Debe tener entre 2 y 80 caracteres"

    apellidos = texto(datos.get("apellidos"))
    if not 2 <= len(apellidos) <= 80:
        errores["apellidos"] = "Debe tener entre 2 y 80 caracteres"

    dpi = re.sub(r"[\s-]", "", str(datos.get("dpi") or ""))
    if not re.fullmatch(r"\d{13}", dpi):
        errores["dpi"] = "Debe tener 13 dígitos"

    telefono = re.sub(r"[\s-]", "", str(datos.get("telefono") or ""))
    if telefono and not re.fullmatch(r"\d{8}", telefono):
        errores["telefono"] = "Debe tener 8 dígitos"

    for campo in ("puesto_id", "sucursal_id"):
        if not UUID.match(str(datos.get(campo) or "")):
            errores[campo] = "Selecciona una opción"

    try:
        fecha = date.fromisoformat(str(datos.get("fecha_ingreso") or ""))
        if fecha < date(1990, 1, 1) or fecha > date.today() + timedelta(days=31):
            errores["fecha_ingreso"] = "Fecha fuera de rango"
    except ValueError:
        fecha = None
        errores["fecha_ingreso"] = "Fecha inválida"

    pago, errores_pago = validar_pago(datos)
    errores.update(errores_pago)

    valores = {
        "p_nombres": nombres,
        "p_apellidos": apellidos,
        "p_dpi": dpi,
        "p_telefono": telefono,
        "p_puesto_id": datos.get("puesto_id"),
        "p_sucursal_id": datos.get("sucursal_id"),
        "p_fecha_ingreso": fecha.isoformat() if fecha else None,
        **pago,
    }
    return valores, errores


@bp.post("")
@requiere_rol("rrhh")
def crear():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    valores, errores = validar(datos)
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        respuesta = get_db().rpc("crear_colaborador", {**valores, "p_usuario": g.usuario["id"]}).execute()
    except APIError as error:
        if error.code == "23505":
            return jsonify(error="Ya existe un colaborador con ese DPI"), 409
        if error.code in ("23503", "23514"):
            return jsonify(error="Puesto, sucursal o salario no válidos"), 400
        raise

    return jsonify(id=respuesta.data), 201


@bp.put("/<uuid:colaborador_id>/condiciones")
@requiere_rol("rrhh")
def cambiar_condiciones(colaborador_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    pago, errores = validar_pago(datos)
    for campo in ("modalidad", "forma_pago"):
        if not datos.get(campo):
            errores[campo] = "Obligatorio"

    try:
        desde = date.fromisoformat(str(datos.get("desde") or ""))
        if desde < FECHA_MINIMA_PAGO or desde > date.today() + timedelta(days=366):
            errores["desde"] = "Fecha fuera de rango"
    except ValueError:
        desde = None
        errores["desde"] = "Fecha inválida"

    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "cambiar_condiciones_pago",
            {
                "p_colaborador": str(colaborador_id),
                **pago,
                "p_desde": desde.isoformat(),
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        if error.code == "P0002":
            return jsonify(error="El colaborador no existe"), 404
        if error.code == "22023":
            return jsonify(error="datos inválidos", campos={"desde": error.message}), 422
        if error.code == "23514":
            return jsonify(error="La combinación de forma de pago y monto no es válida"), 422
        raise

    return jsonify(ok=True)


ID_RELOJ = re.compile(r"^[A-Za-z0-9]{1,24}$")


@bp.post("/<uuid:colaborador_id>/enlaces")
@requiere_rol("rrhh")
def enlazar(colaborador_id):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="formato inválido"), 400

    dispositivo_id = str(datos.get("dispositivo_id") or "").lower()
    id_en_reloj = str(datos.get("id_en_dispositivo") or "").strip()

    errores = {}
    if not UUID.match(dispositivo_id):
        errores["dispositivo_id"] = "Selecciona un reloj"
    if not ID_RELOJ.match(id_en_reloj):
        errores["id_en_dispositivo"] = "Solo letras y números, hasta 24 caracteres"
    if errores:
        return jsonify(error="datos inválidos", campos=errores), 422

    try:
        get_db().rpc(
            "enlazar_colaborador",
            {
                "p_colaborador": str(colaborador_id),
                "p_dispositivo": dispositivo_id,
                "p_id": id_en_reloj,
                "p_usuario": g.usuario["id"],
            },
        ).execute()
    except APIError as error:
        if error.code == "23505":
            return jsonify(error="Ese ID ya pertenece a otra persona, o esta persona ya tiene un ID en ese reloj"), 409
        if error.code == "23503":
            return jsonify(error="El colaborador o el reloj no existe"), 404
        raise

    return jsonify(ok=True), 201


@bp.delete("/<uuid:colaborador_id>/enlaces/<uuid:dispositivo_id>")
@requiere_rol("rrhh")
def desenlazar(colaborador_id, dispositivo_id):
    respuesta = (
        get_db()
        .rpc(
            "desenlazar_colaborador",
            {
                "p_colaborador": str(colaborador_id),
                "p_dispositivo": str(dispositivo_id),
                "p_usuario": g.usuario["id"],
            },
        )
        .execute()
    )

    if not respuesta.data:
        return jsonify(error="Ese enlace no existe"), 404

    return jsonify(ok=True)