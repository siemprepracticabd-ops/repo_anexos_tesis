"""pruebas de quitar el enlace colaborador <-> reloj"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import colaboradores  # noqa: E402

COLABORADOR = "55555555-5555-4555-8555-555555555555"
RELOJ = "66666666-6666-4666-8666-666666666666"
USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}
RUTA = f"/api/colaboradores/{COLABORADOR}/enlaces/{RELOJ}"


class FalsaBase:
    def __init__(self, resultado=True):
        self.resultado = resultado
        self.llamadas = []

    def rpc(self, nombre, parametros):
        self.llamadas.append((nombre, parametros))
        return self

    def execute(self):
        return SimpleNamespace(data=self.resultado)


class Desenlazar(unittest.TestCase):
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
        self.assertEqual(self.preparar(None).delete(RUTA).status_code, 401)

    def test_el_jefe_no_puede_quitar_enlaces(self):
        r = self.preparar(USUARIO_JEFE).delete(RUTA)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_identificadores_que_no_son_uuid_dan_404(self):
        cliente = self.preparar(USUARIO_RRHH)
        self.assertEqual(cliente.delete(f"/api/colaboradores/xyz/enlaces/{RELOJ}").status_code, 404)
        self.assertEqual(cliente.delete(f"/api/colaboradores/{COLABORADOR}/enlaces/xyz").status_code, 404)
        self.assertEqual(self.base.llamadas, [])

    def test_quitar_un_enlace_existente_da_200(self):
        r = self.preparar(USUARIO_RRHH).delete(RUTA)
        self.assertEqual(r.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "desenlazar_colaborador")
        self.assertEqual(parametros["p_colaborador"], COLABORADOR)
        self.assertEqual(parametros["p_dispositivo"], RELOJ)
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_enlace_que_no_existe_da_404(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(resultado=False)).delete(RUTA)
        self.assertEqual(r.status_code, 404)

    def test_otros_metodos_no_estan_permitidos(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA, json={})
        self.assertEqual(r.status_code, 405)


if __name__ == "__main__":
    unittest.main()
