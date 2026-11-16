"""pruebas de la creacion de programaciones de turnos"""

import os
import sys
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import programaciones  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}


class CalcularPeriodo(unittest.TestCase):
    def test_semana_empieza_en_lunes_y_dura_siete_dias(self):
        self.assertEqual(programaciones.calcular_periodo("semanal", "2026-10-26"), (date(2026, 10, 26), date(2026, 11, 1)))

    def test_semana_que_no_empieza_en_lunes_se_rechaza(self):
        for dia in ("2026-10-27", "2026-10-31", "2026-11-01"):
            with self.assertRaises(ValueError, msg=dia):
                programaciones.calcular_periodo("semanal", dia)

    def test_primera_quincena(self):
        self.assertEqual(programaciones.calcular_periodo("quincenal", "2026-11-01"), (date(2026, 11, 1), date(2026, 11, 15)))

    def test_segunda_quincena_termina_el_ultimo_dia_del_mes(self):
        self.assertEqual(programaciones.calcular_periodo("quincenal", "2026-11-16"), (date(2026, 11, 16), date(2026, 11, 30)))
        self.assertEqual(programaciones.calcular_periodo("quincenal", "2026-12-16"), (date(2026, 12, 16), date(2026, 12, 31)))
        self.assertEqual(programaciones.calcular_periodo("quincenal", "2026-02-16"), (date(2026, 2, 16), date(2026, 2, 28)))
        self.assertEqual(programaciones.calcular_periodo("quincenal", "2027-02-16"), (date(2027, 2, 16), date(2027, 2, 28)))

    def test_quincena_que_no_empieza_el_1_o_el_16_se_rechaza(self):
        for dia in ("2026-11-02", "2026-11-10", "2026-11-15", "2026-11-17"):
            with self.assertRaises(ValueError, msg=dia):
                programaciones.calcular_periodo("quincenal", dia)

    def test_fechas_invalidas_o_fuera_de_rango(self):
        for mala in ("ayer", "2026-13-45", "", "2099-01-01", "1999-01-01"):
            with self.assertRaises(ValueError, msg=mala):
                programaciones.calcular_periodo("semanal", mala)

    def test_tipo_desconocido(self):
        with self.assertRaises(ValueError):
            programaciones.calcular_periodo("mensual", "2026-11-01")


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
        return SimpleNamespace(data="77777777-7777-4777-8777-777777777777")


class Endpoint(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(programaciones, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def test_sin_sesion_da_401(self):
        r = self.preparar(None).post("/api/programaciones", json={"tipo": "semanal", "fecha_inicio": "2026-10-26"})
        self.assertEqual(r.status_code, 401)

    def test_el_jefe_no_puede_crear(self):
        r = self.preparar(USUARIO_JEFE).post("/api/programaciones", json={"tipo": "semanal", "fecha_inicio": "2026-10-26"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).post("/api/programaciones", data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_tipo_invalido_da_422(self):
        r = self.preparar(USUARIO_RRHH).post("/api/programaciones", json={"tipo": "mensual", "fecha_inicio": "2026-10-26"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("tipo", r.get_json()["campos"])
        self.assertEqual(self.base.llamadas, [])

    def test_fecha_invalida_da_422_con_el_motivo(self):
        r = self.preparar(USUARIO_RRHH).post("/api/programaciones", json={"tipo": "semanal", "fecha_inicio": "2026-10-27"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["campos"]["fecha_inicio"], "La semana debe empezar en lunes")
        self.assertEqual(self.base.llamadas, [])

    def test_creacion_correcta_calcula_el_fin_y_usa_el_token(self):
        r = self.preparar(USUARIO_RRHH).post(
            "/api/programaciones",
            json={"tipo": "quincenal", "fecha_inicio": "2026-11-16", "p_fin": "1999-01-01", "p_usuario": "otro"},
        )
        self.assertEqual(r.status_code, 201)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "crear_programacion")
        self.assertEqual(parametros["p_tipo"], "quincenal")
        self.assertEqual(parametros["p_inicio"], "2026-11-16")
        self.assertEqual(parametros["p_fin"], "2026-11-30")
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_periodo_repetido_da_409(self):
        error = APIError({"message": "duplicate", "code": "23505", "hint": None, "details": None})
        r = self.preparar(USUARIO_RRHH, FalsaBase(error)).post(
            "/api/programaciones", json={"tipo": "semanal", "fecha_inicio": "2026-10-26"}
        )
        self.assertEqual(r.status_code, 409)


if __name__ == "__main__":
    unittest.main()
