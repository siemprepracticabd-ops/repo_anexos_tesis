"""pruebas del endpoint que calcula las jornadas"""

import os
import sys
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import jornadas  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}
RUTA = "/api/jornadas/calcular"
RESULTADO = {"jornadas": 13, "sin_programacion": 1, "ausencias": 2, "horas_extra": 1}


class FalsaBase:
    def __init__(self, error=None):
        self.error = error
        self.llamadas = []

    def rpc(self, nombre, parametros):
        self.llamadas.append((nombre, parametros))
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=RESULTADO)


class Endpoint(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(jornadas, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def test_sin_sesion_da_401(self):
        r = self.preparar(None).post(RUTA, json={"desde": "2026-10-01", "hasta": "2026-10-15"})
        self.assertEqual(r.status_code, 401)

    def test_el_jefe_no_puede_calcular(self):
        r = self.preparar(USUARIO_JEFE).post(RUTA, json={"desde": "2026-10-01", "hasta": "2026-10-15"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).post(RUTA, data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_fechas_invalidas_dan_422_y_no_tocan_la_base(self):
        cliente = self.preparar(USUARIO_RRHH)
        hoy = date.today()
        malas = [
            {"desde": "ayer", "hasta": "2026-10-15"},
            {"desde": "2026-10-01"},
            {"desde": "2026-10-15", "hasta": "2026-10-01"},
            {"desde": "2023-12-31", "hasta": "2024-01-05"},
            {"desde": "2026-01-01", "hasta": "2026-12-31"},
            {"desde": hoy.isoformat(), "hasta": (hoy + timedelta(days=5)).isoformat()},
        ]
        for cuerpo in malas:
            r = cliente.post(RUTA, json=cuerpo)
            self.assertEqual(r.status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_calculo_correcto_usa_el_token_y_devuelve_el_resumen(self):
        r = self.preparar(USUARIO_RRHH).post(
            RUTA, json={"desde": "2026-10-01", "hasta": "2026-10-15", "p_usuario": "otro", "p_ahora": "2020-01-01"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), RESULTADO)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "calcular_jornadas")
        self.assertEqual(parametros, {"p_desde": "2026-10-01", "p_hasta": "2026-10-15", "p_usuario": USUARIO_RRHH["id"]})

    def test_un_solo_dia_es_valido(self):
        r = self.preparar(USUARIO_RRHH).post(RUTA, json={"desde": "2026-10-01", "hasta": "2026-10-01"})
        self.assertEqual(r.status_code, 200)

    def test_el_rango_de_la_base_se_traduce_a_422(self):
        error = APIError({"message": "El rango no puede pasar de 62 dias", "code": "22023", "hint": None, "details": None})
        r = self.preparar(USUARIO_RRHH, FalsaBase(error)).post(RUTA, json={"desde": "2026-10-01", "hasta": "2026-10-15"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("62", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
