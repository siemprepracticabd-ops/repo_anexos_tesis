"""pruebas del horario de oficina (modalidad diurna)"""

import os
import sys
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import oficina  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
COLABORADOR = "77777777-7777-4777-8777-777777777777"
HOY = date.today().isoformat()


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
        return SimpleNamespace(data={"ok": True})


def error_de_base(codigo, mensaje="mensaje de la base"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


class Base(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(oficina, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class TestGuardarDia(Base):
    def test_rrhh_marca_que_trabaja(self):
        cliente = self.preparar(USUARIO_RRHH)
        respuesta = cliente.put(
            "/api/oficina/dias",
            json={"colaborador_id": COLABORADOR, "fecha": HOY, "tipo": "trabaja", "motivo": "Cubre"},
        )
        self.assertEqual(respuesta.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "guardar_dia_diurno")
        self.assertEqual(parametros["p_tipo"], "trabaja")
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_tipo_vacio_vuelve_al_horario_base(self):
        cliente = self.preparar(USUARIO_RRHH)
        respuesta = cliente.put("/api/oficina/dias", json={"colaborador_id": COLABORADOR, "fecha": HOY, "tipo": None})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(self.base.llamadas[0][1]["p_tipo"])

    def test_el_jefe_no_puede_cambiar_dias(self):
        cliente = self.preparar(USUARIO_JEFE)
        respuesta = cliente.put("/api/oficina/dias", json={"colaborador_id": COLABORADOR, "fecha": HOY, "tipo": "libre"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos(self):
        cliente = self.preparar(USUARIO_RRHH)
        lejos = (date.today() + timedelta(days=400)).isoformat()
        respuesta = cliente.put(
            "/api/oficina/dias",
            json={"colaborador_id": "no-es-uuid", "fecha": lejos, "tipo": "vacaciones", "motivo": "x" * 300},
        )
        self.assertEqual(respuesta.status_code, 422)
        self.assertEqual(set(respuesta.get_json()["campos"]), {"colaborador_id", "fecha", "tipo", "motivo"})
        self.assertEqual(self.base.llamadas, [])

    def test_quincena_cerrada(self):
        cliente = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base("55000")))
        respuesta = cliente.put("/api/oficina/dias", json={"colaborador_id": COLABORADOR, "fecha": HOY, "tipo": "libre"})
        self.assertEqual(respuesta.status_code, 409)

    def test_no_es_diurna(self):
        cliente = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base("22023", "Solo las personas con modalidad diurna")))
        respuesta = cliente.put("/api/oficina/dias", json={"colaborador_id": COLABORADOR, "fecha": HOY, "tipo": "libre"})
        self.assertEqual(respuesta.status_code, 422)


if __name__ == "__main__":
    unittest.main()
