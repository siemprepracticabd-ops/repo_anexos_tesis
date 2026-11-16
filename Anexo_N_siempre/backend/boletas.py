"""endpoints de las boletas de pago y la planilla general en pdf"""

from datetime import date

from flask import Blueprint, Response, jsonify

from auth import requiere_rol
from boletas_pdf import generar_boletas, generar_planilla_general
from db import get_db

bp = Blueprint("boletas", __name__, url_prefix="/api/boletas")

SELECT_BOLETAS = (
    "id, numero, estado, total_ingresos, total_descuentos, neto, snapshot_valores, periodo_id, "
    "colaboradores(nombres, apellidos, puestos(nombre), sucursales(nombre)), "
    "boleta_detalles(tipo, concepto, cantidad, valor_unitario, monto)"
)


def leer_periodo(db, periodo_id):
    filas = (
        db.table("periodos_planilla")
        .select("id, fecha_inicio, fecha_fin, estado")
        .eq("id", str(periodo_id))
        .execute()
        .data
    )
    if not filas:
        return None
    periodo = filas[0]
    periodo["fecha_inicio"] = date.fromisoformat(periodo["fecha_inicio"])
    periodo["fecha_fin"] = date.fromisoformat(periodo["fecha_fin"])
    return periodo


def respuesta_pdf(pdf, archivo):
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{archivo}"', "Cache-Control": "no-store"},
    )


@bp.get("/<uuid:boleta_id>/boleta.pdf")
@requiere_rol("rrhh", "jefe")
def boleta_individual(boleta_id):
    db = get_db()
    boletas = db.table("boletas").select(SELECT_BOLETAS).eq("id", str(boleta_id)).execute().data
    if not boletas:
        return jsonify(error="No existe la boleta"), 404
    periodo = leer_periodo(db, boletas[0]["periodo_id"])
    return respuesta_pdf(generar_boletas(periodo, boletas), f"boleta-{boletas[0]['numero']}.pdf")


@bp.get("/periodo/<uuid:periodo_id>/planilla.pdf")
@requiere_rol("rrhh", "jefe")
def planilla_general(periodo_id):
    db = get_db()
    periodo = leer_periodo(db, periodo_id)
    if periodo is None:
        return jsonify(error="No existe el periodo"), 404
    boletas = db.table("boletas").select(SELECT_BOLETAS).eq("periodo_id", str(periodo_id)).order("numero").execute().data
    return respuesta_pdf(generar_planilla_general(periodo, boletas), f"planilla-{periodo['fecha_inicio']}.pdf")


@bp.get("/periodo/<uuid:periodo_id>/boletas.pdf")
@requiere_rol("rrhh", "jefe")
def boletas_del_periodo(periodo_id):
    db = get_db()
    periodo = leer_periodo(db, periodo_id)
    if periodo is None:
        return jsonify(error="No existe el periodo"), 404
    boletas = db.table("boletas").select(SELECT_BOLETAS).eq("periodo_id", str(periodo_id)).order("numero").execute().data
    if not boletas:
        return jsonify(error="El periodo no tiene boletas"), 404
    return respuesta_pdf(generar_boletas(periodo, boletas), f"boletas-{periodo['fecha_inicio']}.pdf")