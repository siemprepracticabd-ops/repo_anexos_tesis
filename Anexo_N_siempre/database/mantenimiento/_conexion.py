"""conexion a supabase para los scripts de mantenimiento"""

from supabase import create_client


def leer_env(ruta: str) -> dict:
    valores = {}
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if "=" in linea and not linea.startswith("#"):
                nombre, valor = linea.split("=", 1)
                valores[nombre.strip()] = valor.strip().strip('"').strip("'")
    return valores


def conectar(ruta_env: str):
    env = leer_env(ruta_env)
    url = env.get("SUPABASE_URL", "")
    clave = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    # la url debe ser solo el dominio: se quita un "/rest/v1/" pegado por error
    url = url.split("/rest/v1")[0].rstrip("/")
    if not url or not clave:
        raise SystemExit("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en " + ruta_env)
    return create_client(url, clave)


def leer_todo(db, tabla: str, pagina: int = 1000) -> list:
    """lee todas las filas de una tabla, de a paginas (postgrest limita a 1000)"""
    filas, desde = [], 0
    while True:
        lote = db.table(tabla).select("*").range(desde, desde + pagina - 1).execute().data
        filas.extend(lote)
        if len(lote) < pagina:
            return filas
        desde += pagina
