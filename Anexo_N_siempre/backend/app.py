import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from flask import Flask, g, jsonify, request
from postgrest.exceptions import APIError

from auth import requiere_rol
from db import get_db
from colaboradores import bp as colaboradores_bp
from programaciones import bp as programaciones_bp
from asignaciones import bp as asignaciones_bp
from calendarios import bp as calendarios_bp
from jornadas import bp as jornadas_bp
from pendientes import bp as pendientes_bp
from catalogos import bp as catalogos_bp
from resoluciones import bp as resoluciones_bp
from planilla import bp as planilla_bp
from boletas import bp as boletas_bp
from bajas import bp as bajas_bp
from alertas import bp as alertas_bp
from bitacora import bp as bitacora_bp
from relojes import bp as relojes_bp
from oficina import bp as oficina_bp


MAX_LOTE = 500
MAX_USUARIOS = 300
MAX_BYTES = 1_000_000  # tamano maximo de una peticion, antes de leer el json
CODIGO_PUNCH_MAX = 32767  # la columna marcaciones.codigo_punch es smallint
TIPOS = {"entrada", "salida", "desconocido"}

# errores que significan "este registro viene mal", no "el servidor fallo"
ERRORES_DE_DATO = (KeyError, ValueError, TypeError, AttributeError, OverflowError)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES
app.register_blueprint(colaboradores_bp)
app.register_blueprint(programaciones_bp)
app.register_blueprint(asignaciones_bp)
app.register_blueprint(calendarios_bp)
app.register_blueprint(jornadas_bp)
app.register_blueprint(pendientes_bp)
app.register_blueprint(catalogos_bp)
app.register_blueprint(resoluciones_bp)
app.register_blueprint(planilla_bp)
app.register_blueprint(boletas_bp)
app.register_blueprint(bajas_bp)
app.register_blueprint(alertas_bp)
app.register_blueprint(bitacora_bp)
app.register_blueprint(relojes_bp)
app.register_blueprint(oficina_bp)

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def autenticar_lector(serie: str, api_key: str):
    res = (
        get_db()
        .table("dispositivos")
        .select("id, api_key_hash, activo")
        .eq("serie", serie)
        .limit(1)
        .execute()
    )
    esperado = res.data[0]["api_key_hash"] if res.data else "0" * 64
    coincide = hmac.compare_digest(esperado, hash_api_key(api_key))
    if res.data and coincide and res.data[0]["activo"]:
        return res.data[0]
    return None


def normalizar(item: dict, dispositivo_id: str, limite_futuro: datetime):
    id_en_lector = str(item["id_en_lector"]).strip()
    if not 1 <= len(id_en_lector) <= 24:
        raise ValueError("id_en_lector inválido")

    fecha = datetime.fromisoformat(item["fecha_hora"])
    if fecha.tzinfo is None:
        raise ValueError("fecha_hora sin zona horaria")
    fecha = fecha.astimezone(timezone.utc)
    if fecha > limite_futuro:
        raise ValueError("fecha_hora en el futuro")

    tipo = item.get("tipo", "desconocido")
    if tipo not in TIPOS:
        tipo = "desconocido"

    codigo_punch = int(item.get("codigo_punch", 0))
    if not 0 <= codigo_punch <= CODIGO_PUNCH_MAX:
        raise ValueError("codigo_punch fuera de rango")

    return {
        "dispositivo_id": dispositivo_id,
        "id_en_dispositivo": id_en_lector,
        "marcado_en": fecha.isoformat(),
        "tipo": tipo,
        "origen": "lector",
        "codigo_punch": codigo_punch,
        "payload_crudo": {
            "id_en_lector": id_en_lector,
            "fecha_hora": str(item["fecha_hora"])[:40],
            "tipo": str(item.get("tipo", ""))[:20],
            "codigo_punch": item.get("codigo_punch"),
        },
    }


def guardar_marcaciones(filas: list):
    """guarda las marcaciones y devuelve (nuevas, rechazadas)"""
    opciones = {
        "on_conflict": "dispositivo_id,id_en_dispositivo,marcado_en",
        "ignore_duplicates": True,
    }
    try:
        res = get_db().table("marcaciones").upsert(filas, **opciones).execute()
        return len(res.data), 0
    except APIError as error:
        app.logger.warning("Lote rechazado por la base, se reintenta fila por fila: %s", error.message)

    nuevas = rechazadas = 0
    for fila in filas:
        try:
            res = get_db().table("marcaciones").upsert(fila, **opciones).execute()
            nuevas += len(res.data)
        except APIError as error:
            rechazadas += 1
            app.logger.warning("Marcación rechazada por la base: %s", error.message)
    return nuevas, rechazadas


@app.get("/api/salud")
def salud():
    return jsonify(ok=True)


@app.get("/api/yo")
@requiere_rol("rrhh", "jefe")
def yo():
    return jsonify(g.usuario)


@app.post("/api/marcaciones")
def recibir_marcaciones():
    api_key = request.headers.get("X-API-Key", "")
    body = request.get_json(silent=True) or {}
    serie = str(body.get("lector_serie", ""))[:64]

    if not api_key or not serie:
        return jsonify(error="credenciales requeridas"), 401

    lector = autenticar_lector(serie, api_key)
    if lector is None:
        return jsonify(error="credenciales inválidas"), 401

    items = body.get("marcaciones", [])
    usuarios = body.get("usuarios", [])
    if not isinstance(items, list) or not isinstance(usuarios, list):
        return jsonify(error="formato inválido"), 400
    if len(items) > MAX_LOTE or len(usuarios) > MAX_USUARIOS or not (items or usuarios):
        return jsonify(error=f"se esperan hasta {MAX_LOTE} marcaciones o {MAX_USUARIOS} usuarios"), 400

    limite_futuro = datetime.now(timezone.utc) + timedelta(days=1)
    filas, rechazadas = [], 0
    for item in items:
        try:
            filas.append(normalizar(item, lector["id"], limite_futuro))
        except ERRORES_DE_DATO:
            rechazadas += 1

    nuevas = 0
    if filas:
        nuevas, fallidas = guardar_marcaciones(filas)
        rechazadas += fallidas
        filas = filas[: len(filas) - fallidas]

    ahora = datetime.now(timezone.utc).isoformat()
    nombres = []
    for u in usuarios:
        try:
            id_en_lector = str(u["id_en_lector"]).strip()
            nombre = " ".join(str(u["nombre"]).split())[:60]
        except ERRORES_DE_DATO:
            continue
        if 1 <= len(id_en_lector) <= 24 and nombre:
            nombres.append(
                {
                    "dispositivo_id": lector["id"],
                    "id_en_dispositivo": id_en_lector,
                    "nombre": nombre,
                    "actualizado_en": ahora,
                }
            )

    if nombres:
        get_db().table("dispositivo_usuarios").upsert(
            nombres, on_conflict="dispositivo_id,id_en_dispositivo"
        ).execute()

    get_db().table("dispositivos").update({"ultima_sincronizacion": ahora}).eq("id", lector["id"]).execute()

    # recibidas: validas y aceptadas | nuevas: realmente insertadas (sin duplicados)
    return jsonify(recibidas=len(filas), nuevas=nuevas, rechazadas=rechazadas, nombres=len(nombres))


if __name__ == "__main__":
    # solo para desarrollo local
    from dotenv import load_dotenv

    load_dotenv(".env.local")
    load_dotenv()
    app.run(host="127.0.0.1", port=5000)
