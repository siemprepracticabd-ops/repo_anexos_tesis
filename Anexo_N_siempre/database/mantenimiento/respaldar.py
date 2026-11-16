"""guarda en archivos json todos los datos de la base antes de un reinicio"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _conexion import conectar, leer_todo  # noqa: E402

TABLAS = [
    "profiles", "bitacora", "sucursales", "puestos", "dispositivos", "tipos_ausencia", "turnos",
    "parametros", "colaboradores", "colaborador_dispositivo", "dispositivo_usuarios",
    "periodos_laborales", "colaborador_salarios", "licencias", "programaciones",
    "asignaciones_turno", "cambios_turno", "marcaciones", "correcciones_marcacion", "jornadas",
    "ausencias", "notas_asistencia", "horas_extra", "alertas", "periodos_planilla", "boletas",
    "boleta_detalles",
]

parser = argparse.ArgumentParser()
parser.add_argument("--env", required=True, help="ruta del .env con SUPABASE_URL y la clave service_role")
args = parser.parse_args()

db = conectar(args.env)
carpeta = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "respaldo", datetime.now().strftime("%Y-%m-%d_%H%M%S")
)
os.makedirs(carpeta)

resumen = {}
for tabla in TABLAS:
    try:
        filas = leer_todo(db, tabla)
    except Exception as error:  # la tabla puede no existir
        resumen[tabla] = "no existe"
        continue
    resumen[tabla] = len(filas)
    if filas:
        with open(os.path.join(carpeta, tabla + ".json"), "w", encoding="utf-8") as archivo:
            json.dump(filas, archivo, ensure_ascii=False, indent=1, default=str)

with open(os.path.join(carpeta, "_resumen.json"), "w", encoding="utf-8") as archivo:
    json.dump(resumen, archivo, indent=1)

print("Respaldo en:", os.path.abspath(carpeta))
for tabla, cantidad in resumen.items():
    if cantidad:
        print(f"  {tabla:26} {cantidad}")
