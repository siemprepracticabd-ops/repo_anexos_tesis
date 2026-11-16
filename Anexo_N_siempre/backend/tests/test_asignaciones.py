"""pruebas de guardar las celdas de la parrilla"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import asignaciones  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}

PROGRAMACION = "55555555-5555-4555-8555-555555555555"
RUTA = f"/api/programaciones/{PROGRAMACION}/asignaciones"
COLABORADOR = "11111111-1111-4111-8111-111111111111"
TURNO = "22222222-2222-4222-8222-222222222222"
SUCURSAL = "66666666-6666-4666-8666-666666666666"


def celda(**cambios):
    base = {"colaborador_id": COLABORADOR, "fecha": "2026-10-26", "turno_id": TURNO, "sucursal_id": SUCURSAL}
    base.update(cambios)
    return base


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
        return SimpleNamespace(data=2)


def error_de_base(codigo):
    return APIError({"message": "x", "code": codigo, "hint": None, "details": None})


class Endpoint(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(asignaciones, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def test_sin_sesion_da_401(self):
        r = self.preparar(None).put(RUTA, json={"celdas": [celda()]})
        self.assertEqual(r.status_code, 401)

    def test_el_jefe_no_puede_guardar(self):
        r = self.preparar(USUARIO_JEFE).put(RUTA, json={"celdas": [celda()]})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_programacion_con_id_malformado_da_404(self):
        r = self.preparar(USUARIO_RRHH).put("/api/programaciones/abc/asignaciones", json={"celdas": [celda()]})
        self.assertEqual(r.status_code, 404)

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA, data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_sin_celdas_o_con_formato_malo_da_400(self):
        cliente = self.preparar(USUARIO_RRHH)
        for cuerpo in ({}, {"celdas": []}, {"celdas": "hola"}, [celda()]):
            self.assertEqual(cliente.put(RUTA, json=cuerpo).status_code, 400, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_demasiadas_celdas_da_400(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA, json={"celdas": [celda()] * (asignaciones.MAX_CELDAS + 1)})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.base.llamadas, [])

    def test_celda_invalida_da_422_y_no_llama_a_la_base(self):
        cliente = self.preparar(USUARIO_RRHH)
        malas = [
            "texto",
            celda(colaborador_id="no-es-uuid"),
            celda(colaborador_id=None),
            celda(sucursal_id=None),
            celda(turno_id="no-es-uuid"),
            celda(fecha="mañana"),
            celda(fecha=None),
        ]
        for mala in malas:
            r = cliente.put(RUTA, json={"celdas": [celda(), mala]})
            self.assertEqual(r.status_code, 422, mala)
        self.assertEqual(self.base.llamadas, [])

    def test_guardado_correcto_usa_el_token_y_acepta_libre(self):
        r = self.preparar(USUARIO_RRHH).put(
            RUTA,
            json={
                "celdas": [celda(), celda(fecha="2026-10-27", turno_id=None)],
                "p_usuario": "otro",
                "p_programacion": "otra",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"guardadas": 2})
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "guardar_asignaciones")
        self.assertEqual(parametros["p_programacion"], PROGRAMACION)
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])
        self.assertEqual(parametros["p_asignaciones"][0], celda())
        self.assertIsNone(parametros["p_asignaciones"][1]["turno_id"])

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "55000": 409, "23514": 422, "23503": 422}
        for codigo, estado in esperados.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).put(RUTA, json={"celdas": [celda()]})
            self.assertEqual(r.status_code, estado, codigo)


if __name__ == "__main__":
    unittest.main()
