"""pruebas de publicar una programacion y crear versiones"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import programaciones  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}

PROGRAMACION = "55555555-5555-4555-8555-555555555555"
NUEVA = "77777777-7777-4777-8777-777777777777"
RUTA_PUBLICAR = f"/api/programaciones/{PROGRAMACION}/publicar"
RUTA_VERSIONES = f"/api/programaciones/{PROGRAMACION}/versiones"


class FalsaBase:
    def __init__(self, error=None, dato=2):
        self.error = error
        self.dato = dato
        self.llamadas = []

    def rpc(self, nombre, parametros):
        self.llamadas.append((nombre, parametros))
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.dato)


def error_de_base(codigo, mensaje="x"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


class Base(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(programaciones, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class Publicar(Base):
    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).post(RUTA_PUBLICAR).status_code, 401)

    def test_el_jefe_no_puede_publicar(self):
        r = self.preparar(USUARIO_JEFE).post(RUTA_PUBLICAR, json={})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_publicar_sin_cuerpo_es_valido_y_usa_el_token(self):
        r = self.preparar(USUARIO_RRHH).post(RUTA_PUBLICAR)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"version": 2})
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "publicar_programacion")
        self.assertEqual(parametros["p_programacion"], PROGRAMACION)
        self.assertIsNone(parametros["p_motivo"])
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_el_motivo_se_limpia_y_se_envia(self):
        self.preparar(USUARIO_RRHH).post(RUTA_PUBLICAR, json={"motivo": "  Incapacidad  ", "p_usuario": "otro"})
        parametros = self.base.llamadas[0][1]
        self.assertEqual(parametros["p_motivo"], "Incapacidad")
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_motivo_demasiado_largo_da_422(self):
        r = self.preparar(USUARIO_RRHH).post(RUTA_PUBLICAR, json={"motivo": "a" * 501})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.base.llamadas, [])

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "55000": 409, "22023": 422}
        for codigo, estado in esperados.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo, "Escribe el motivo del cambio"))).post(
                RUTA_PUBLICAR
            )
            self.assertEqual(r.status_code, estado, codigo)

    def test_el_mensaje_de_motivo_faltante_llega_a_la_pantalla(self):
        base = FalsaBase(error_de_base("22023", "Escribe el motivo del cambio"))
        r = self.preparar(USUARIO_RRHH, base).post(RUTA_PUBLICAR)
        self.assertEqual(r.get_json()["error"], "Escribe el motivo del cambio")


class CrearVersion(Base):
    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).post(RUTA_VERSIONES).status_code, 401)

    def test_el_jefe_no_puede_crear_versiones(self):
        r = self.preparar(USUARIO_JEFE).post(RUTA_VERSIONES)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_creacion_correcta_devuelve_201_con_el_id_nuevo(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato=NUEVA)).post(RUTA_VERSIONES)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json(), {"id": NUEVA})
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "crear_version_programacion")
        self.assertEqual(parametros, {"p_programacion": PROGRAMACION, "p_usuario": USUARIO_RRHH["id"]})

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "55000": 409, "23505": 409}
        for codigo, estado in esperados.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(RUTA_VERSIONES)
            self.assertEqual(r.status_code, estado, codigo)


if __name__ == "__main__":
    unittest.main()
