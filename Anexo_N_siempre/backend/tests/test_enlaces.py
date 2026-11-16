"""pruebas del enlace colaborador <-> id en el reloj"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import colaboradores  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

COLABORADOR = "55555555-5555-4555-8555-555555555555"
RELOJ = "66666666-6666-4666-8666-666666666666"
USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}
RUTA = f"/api/colaboradores/{COLABORADOR}/enlaces"


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
        return SimpleNamespace(data=True)


def error_sql(codigo):
    return APIError({"message": "error", "code": codigo, "hint": None, "details": None})


class Enlaces(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(colaboradores, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def test_sin_sesion_da_401(self):
        r = self.preparar(None).post(RUTA, json={"dispositivo_id": RELOJ, "id_en_dispositivo": "5"})
        self.assertEqual(r.status_code, 401)

    def test_el_jefe_no_puede_enlazar(self):
        r = self.preparar(USUARIO_JEFE).post(RUTA, json={"dispositivo_id": RELOJ, "id_en_dispositivo": "5"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_colaborador_que_no_es_uuid_da_404(self):
        r = self.preparar(USUARIO_RRHH).post(
            "/api/colaboradores/no-es-un-uuid/enlaces", json={"dispositivo_id": RELOJ, "id_en_dispositivo": "5"}
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422_y_no_tocan_la_base(self):
        cliente = self.preparar(USUARIO_RRHH)
        for cuerpo in (
            {"dispositivo_id": "xyz", "id_en_dispositivo": "5"},
            {"dispositivo_id": RELOJ, "id_en_dispositivo": ""},
            {"dispositivo_id": RELOJ, "id_en_dispositivo": "5; drop table x"},
            {"dispositivo_id": RELOJ, "id_en_dispositivo": "9" * 30},
            {},
        ):
            r = cliente.post(RUTA, json=cuerpo)
            self.assertEqual(r.status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).post(RUTA, data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_enlace_correcto_da_201(self):
        r = self.preparar(USUARIO_RRHH).post(RUTA, json={"dispositivo_id": RELOJ, "id_en_dispositivo": " 005 "})
        self.assertEqual(r.status_code, 201)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "enlazar_colaborador")
        self.assertEqual(parametros["p_colaborador"], COLABORADOR)
        self.assertEqual(parametros["p_dispositivo"], RELOJ)
        self.assertEqual(parametros["p_id"], "005")
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_el_usuario_sale_del_token_no_del_cuerpo(self):
        self.preparar(USUARIO_RRHH).post(
            RUTA, json={"dispositivo_id": RELOJ, "id_en_dispositivo": "5", "p_usuario": "otro", "usuario": "otro"}
        )
        self.assertEqual(self.base.llamadas[0][1]["p_usuario"], USUARIO_RRHH["id"])

    def test_id_repetido_da_409(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(error_sql("23505"))).post(
            RUTA, json={"dispositivo_id": RELOJ, "id_en_dispositivo": "5"}
        )
        self.assertEqual(r.status_code, 409)

    def test_colaborador_o_reloj_inexistente_da_404(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(error_sql("23503"))).post(
            RUTA, json={"dispositivo_id": RELOJ, "id_en_dispositivo": "5"}
        )
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
