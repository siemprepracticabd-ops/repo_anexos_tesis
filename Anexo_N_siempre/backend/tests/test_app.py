"""ejecutar desde la carpeta backend"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

AHORA = datetime.now(timezone.utc)
LIMITE = AHORA + timedelta(days=1)


def marca(id_en_lector="7", fecha="2026-10-07T08:00:00-06:00", **extra):
    return {"id_en_lector": id_en_lector, "fecha_hora": fecha, "tipo": "entrada", "codigo_punch": 0, **extra}


class FalsaBase:
    """imita lo minimo de supabase-py"""

    def __init__(self):
        self.guardadas = []
        self.llamadas_upsert = 0

    def table(self, nombre):
        self._tabla = nombre
        return self

    def upsert(self, datos, **opciones):
        self.llamadas_upsert += 1
        filas = datos if isinstance(datos, list) else [datos]
        if self._tabla == "marcaciones" and any(f["id_en_dispositivo"] == "MALA" for f in filas):
            raise APIError({"message": "violates check constraint", "code": "23514", "hint": None, "details": None})
        if self._tabla == "marcaciones":
            self.guardadas.extend(filas)
        self._resultado = SimpleNamespace(data=filas)
        return self

    def update(self, *_a, **_k):
        self._resultado = SimpleNamespace(data=[])
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return self._resultado


class Normalizar(unittest.TestCase):
    def test_marca_valida_se_convierte_a_utc(self):
        fila = api.normalizar(marca(), "disp-1", LIMITE)
        self.assertEqual(fila["marcado_en"], "2026-10-07T14:00:00+00:00")
        self.assertEqual(fila["id_en_dispositivo"], "7")
        self.assertEqual(fila["origen"], "lector")

    def test_sin_zona_horaria_se_rechaza(self):
        with self.assertRaises(ValueError):
            api.normalizar(marca(fecha="2026-10-07T08:00:00"), "d", LIMITE)

    def test_fecha_en_el_futuro_se_rechaza(self):
        futura = (AHORA + timedelta(days=30)).isoformat()
        with self.assertRaises(ValueError):
            api.normalizar(marca(fecha=futura), "d", LIMITE)

    def test_codigo_punch_fuera_de_rango_se_rechaza(self):
        with self.assertRaises(ValueError):
            api.normalizar(marca(codigo_punch=40000), "d", LIMITE)
        with self.assertRaises(ValueError):
            api.normalizar(marca(codigo_punch=-1), "d", LIMITE)


class Endpoint(unittest.TestCase):
    def setUp(self):
        self.base = FalsaBase()
        self.cliente = api.app.test_client()
        self.parches = [
            patch.object(api, "get_db", return_value=self.base),
            patch.object(api, "autenticar_lector", return_value={"id": "disp-1"}),
        ]
        for p in self.parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.parches])

    def enviar(self, marcaciones, **cuerpo):
        return self.cliente.post(
            "/api/marcaciones",
            headers={"X-API-Key": "clave"},
            json={"lector_serie": "ESU1", "marcaciones": marcaciones, **cuerpo},
        )

    def test_sin_credenciales_da_401(self):
        r = self.cliente.post("/api/marcaciones", json={"marcaciones": [marca()]})
        self.assertEqual(r.status_code, 401)

    def test_lote_normal(self):
        r = self.enviar([marca("1"), marca("2")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["recibidas"], 2)
        self.assertEqual(r.get_json()["nuevas"], 2)
        self.assertEqual(r.get_json()["rechazadas"], 0)

    def test_fecha_extrema_no_tumba_el_lote(self):
        # antes provocaba overflowerror sin capturar y un 500 para todo el lote
        r = self.enviar([marca("1"), marca("2", fecha="0001-01-01T00:00:00+14:00")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["recibidas"], 1)
        self.assertEqual(r.get_json()["rechazadas"], 1)

    def test_una_marca_mala_no_bloquea_a_las_demas(self):
        r = self.enviar([marca("1"), marca("MALA"), marca("3")])
        cuerpo = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cuerpo["recibidas"], 2)
        self.assertEqual(cuerpo["nuevas"], 2)
        self.assertEqual(cuerpo["rechazadas"], 1)
        self.assertEqual({f["id_en_dispositivo"] for f in self.base.guardadas}, {"1", "3"})

    def test_peticion_demasiado_grande_da_413(self):
        relleno = "x" * (api.MAX_BYTES + 1)
        r = self.enviar([marca()], relleno=relleno)
        self.assertEqual(r.status_code, 413)


if __name__ == "__main__":
    unittest.main()
