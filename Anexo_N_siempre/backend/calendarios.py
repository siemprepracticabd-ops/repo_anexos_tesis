"""endpoint que descarga el calendario de una programacion en pdf"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from flask import Blueprint, Response, jsonify, request

from auth import requiere_rol
from calendario_pdf import generar_calendario, generar_hoja_individual
from db import get_db

bp = Blueprint("calendarios", __name__, url_prefix="/api/programaciones")

TAMANO_LOTE = 1000
GUATEMALA = timezone(timedelta(hours=-6))


def dias_del_periodo(inicio, fin):
    return [inicio + timedelta(days=n) for n in range((fin - inicio).days + 1)]


def fecha_publicacion(texto):
    """pasa la fecha utc de la base a hora de guatemala (utc-6, sin horario de verano)"""
    if not texto:
        return None
    momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    return momento.astimezone(GUATEMALA).strftime("%d/%m/%Y %H:%M")


def leer_asignaciones(db, programacion_id):
    """supabase entrega como maximo 1000 filas por consulta, asi que se lee por lotes"""
    filas, desde = [], 0
    while True:
        lote = (
            db.table("asignaciones_turno")
            .select("colaborador_id, fecha, turno_id")
            .eq("programacion_id", programacion_id)
            .order("fecha")
            .order("colaborador_id")
            .range(desde, desde + TAMANO_LOTE - 1)
            .execute()
            .data
        )
        filas += lote
        if len(lote) < TAMANO_LOTE:
            return filas
        desde += TAMANO_LOTE


def horario(turno):
    texto = f"{turno['hora_inicio'][:5]} a {turno['hora_fin'][:5]}"
    return texto + " (día siguiente)" if turno["cruza_medianoche"] else texto


def vigente_en(persona, inicio, fin):
    """true si la persona trabajaba en algun dia del rango (iso)"""
    periodos = persona.get("periodos_laborales")
    if periodos is None:
        return True
    return any(
        p["fecha_ingreso"] <= fin and (p["fecha_baja"] is None or p["fecha_baja"] >= inicio) for p in periodos
    )


@bp.get("/<uuid:programacion_id>/calendario.pdf")
@requiere_rol("rrhh", "jefe")
def calendario(programacion_id):
    try:
        sucursal = str(UUID(request.args["sucursal"])) if "sucursal" in request.args else None
        colaborador = str(UUID(request.args["colaborador"])) if "colaborador" in request.args else None
    except ValueError:
        return jsonify(error="Filtro inválido"), 400
    if sucursal and colaborador:
        return jsonify(error="Elige una sucursal o un colaborador, no ambos"), 400

    db = get_db()
    encontradas = (
        db.table("programaciones")
        .select("id, tipo, fecha_inicio, fecha_fin, version, estado, publicada_en")
        .eq("id", str(programacion_id))
        .limit(1)
        .execute()
        .data
    )
    if not encontradas:
        return jsonify(error="La programación no existe"), 404
    programacion = encontradas[0]

    # el personal de oficina (diurna) no se programa aqui: su horario sale de la pantalla oficina
    consulta = (
        db.table("colaboradores")
        .select("id, nombres, apellidos, sucursal_base_id, sucursales(nombre), periodos_laborales(fecha_ingreso, fecha_baja)")
        .neq("modalidad", "diurna")
    )
    if colaborador:
        consulta = consulta.eq("id", colaborador)
    elif sucursal:
        consulta = consulta.eq("sucursal_base_id", sucursal)
    personas = consulta.order("apellidos").order("nombres").execute().data

    turnos = {
        t["id"]: t
        for t in db.table("turnos").select("id, nombre, hora_inicio, hora_fin, cruza_medianoche").execute().data
    }
    celdas = {(a["colaborador_id"], a["fecha"]): a["turno_id"] for a in leer_asignaciones(db, programacion["id"])}

    # quien ya estaba de baja (o aun no ingresaba) en esas fechas y no tiene turnos no sale
    if not colaborador:
        con_turnos = {persona_id for persona_id, _ in celdas}
        personas = [
            p for p in personas
            if p["id"] in con_turnos or vigente_en(p, programacion["fecha_inicio"], programacion["fecha_fin"])
        ]
    if not personas:
        return jsonify(error="No hay colaboradores para ese calendario"), 404

    inicio = date.fromisoformat(programacion["fecha_inicio"])
    fin = date.fromisoformat(programacion["fecha_fin"])
    dias = dias_del_periodo(inicio, fin)
    periodo = f"{programacion['tipo'].capitalize()} del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}"
    publicada_en = fecha_publicacion(programacion["publicada_en"])

    def turno_de(persona_id, dia):
        """devuelve (nombre del turno, datos del turno)"""
        clave = (persona_id, dia.isoformat())
        if clave not in celdas:
            return "", None
        if celdas[clave] is None:
            return "Libre", None
        turno = turnos.get(celdas[clave])
        return (turno["nombre"], turno) if turno else ("", None)

    if colaborador:
        persona = personas[0]
        filas = []
        for dia in dias:
            nombre_turno, turno = turno_de(persona["id"], dia)
            filas.append((dia, nombre_turno, horario(turno) if turno else ""))
        pdf = generar_hoja_individual(
            f"{persona['apellidos']}, {persona['nombres']}",
            persona["sucursales"]["nombre"],
            periodo,
            programacion["version"],
            programacion["estado"],
            publicada_en,
            filas,
        )
        archivo = f"hoja-{programacion['fecha_inicio']}-v{programacion['version']}.pdf"
    else:
        filas = [
            (f"{p['apellidos']}, {p['nombres']}", [turno_de(p["id"], dia)[0] for dia in dias])
            for p in personas
        ]
        donde = personas[0]["sucursales"]["nombre"] if sucursal else "todas las sucursales"
        pdf = generar_calendario(
            f"Calendario de turnos: {donde}",
            periodo,
            programacion["version"],
            programacion["estado"],
            publicada_en,
            dias,
            filas,
        )
        archivo = f"calendario-{programacion['fecha_inicio']}-v{programacion['version']}.pdf"

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{archivo}"', "Cache-Control": "no-store"},
    )