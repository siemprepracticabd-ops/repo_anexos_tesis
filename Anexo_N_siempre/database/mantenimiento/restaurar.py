"""devuelve a la base reconstruida los datos que respaldar.py guardo"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _conexion import conectar, leer_todo  # noqa: E402

RESPALDOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "respaldo")

parser = argparse.ArgumentParser()
parser.add_argument("--env", required=True)
parser.add_argument("--respaldo", help="carpeta del respaldo; por defecto, el más reciente")
parser.add_argument("--aplicar", action="store_true", help="escribe de verdad en la base")
args = parser.parse_args()

carpeta = args.respaldo or os.path.join(RESPALDOS, sorted(os.listdir(RESPALDOS))[-1])
print("Respaldo:", os.path.abspath(carpeta))


def cargar(tabla):
    ruta = os.path.join(carpeta, tabla + ".json")
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


dispositivos = cargar("dispositivos")
usuarios = cargar("dispositivo_usuarios")
marcaciones = sorted(cargar("marcaciones"), key=lambda m: m["marcado_en"])
perfiles = cargar("profiles")

print(f"A restaurar: {len(dispositivos)} reloj(es), {len(usuarios)} nombre(s), "
      f"{len(marcaciones)} marcación(es), {len(perfiles)} perfil(es)")
if not args.aplicar:
    print("\nSIMULACIÓN: no se escribió nada. Agrega --aplicar para restaurar.")
    raise SystemExit(0)

db = conectar(args.env)

# la tabla debe estar vacia de datos propios: si no, es que no se hizo el reinicio
if leer_todo(db, "dispositivos"):
    raise SystemExit("La base ya tiene dispositivos. ¿Ya restauraste antes? No se escribió nada.")

# 1) sucursales: el nombre se deduce del reloj ("reloj sucursal norte" -> "sucursal norte")
ids_sucursal = {}
for d in dispositivos:
    nombre = d["nombre"].removeprefix("Reloj ").strip() or "Sucursal restaurada"
    if nombre not in ids_sucursal:
        db.table("sucursales").upsert({"nombre": nombre}, on_conflict="nombre").execute()
        fila = db.table("sucursales").select("id").eq("nombre", nombre).limit(1).execute().data[0]
        ids_sucursal[nombre] = fila["id"]
    d["sucursal_id"] = ids_sucursal[nombre]
print("Sucursales:", ", ".join(ids_sucursal))

# 2) relojes, con su mismo id y su misma clave (hash)
if dispositivos:
    db.table("dispositivos").insert(dispositivos).execute()
print(f"Relojes: {len(dispositivos)}")

# 3) nombres que reporto el reloj
if usuarios:
    db.table("dispositivo_usuarios").insert(usuarios).execute()
print(f"Nombres: {len(usuarios)}")

# 4) marcaciones, en orden cronologico y de a lotes
nuevas = 0
for i in range(0, len(marcaciones), 200):
    lote = marcaciones[i:i + 200]
    res = db.table("marcaciones").upsert(
        lote, on_conflict="dispositivo_id,id_en_dispositivo,marcado_en", ignore_duplicates=True
    ).execute()
    nuevas += len(res.data)
print(f"Marcaciones: {nuevas} de {len(marcaciones)}")

# 5) perfiles de usuario (el usuario ya existe en authentication)
if perfiles:
    db.table("profiles").upsert(perfiles, on_conflict="id").execute()
print(f"Perfiles: {len(perfiles)}")

print("\nListo. Verifica con la vista marcaciones_resueltas en el SQL Editor.")
