"""pruebas del alta de colaboradores"""

import os
import sys
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import colaboradores  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

PUESTO = "11111111-1111-4111-8111-111111111111"
SUCURSAL = "22222222-2222-4222-8222-222222222222"
USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}


def datos(**cambios):
    base = {
        "nombres": "Ana María",
        "apellidos": "Pérez López",
        "dpi": "2345 67890 1234",
        "telefono": "5555-0000",
        "puesto_id": PUESTO,
        "sucursal_id": SUCURSAL,
        "fecha_ingreso": "2026-10-01",
        "salario_mensual": 3500,
    }
    base.update(cambios)
    return base


class Validar(unittest.TestCase):
    def test_datos_validos_se_limpian(self):
        valores, errores = colaboradores.validar(datos(nombres="  Ana   María "))
        self.assertEqual(errores, {})
        self.assertEqual(valores["p_nombres"], "Ana María")
        self.assertEqual(valores["p_dpi"], "2345678901234")
        self.assertEqual(valores["p_telefono"], "55550000")
        self.assertEqual(Decimal(valores["p_salario"]), Decimal("3500"))

    def test_dpi_incorrecto(self):
        for malo in ("123", "12345678901234", "abcdefghijklm", ""):
            _, errores = colaboradores.validar(datos(dpi=malo))
            self.assertIn("dpi", errores, malo)

    def test_telefono_es_opcional_pero_si_viene_debe_ser_valido(self):
        _, errores = colaboradores.validar(datos(telefono=""))
        self.assertNotIn("telefono", errores)
        _, errores = colaboradores.validar(datos(telefono="123"))
        self.assertIn("telefono", errores)

    def test_nombres_vacios(self):
        _, errores = colaboradores.validar(datos(nombres="   ", apellidos=""))
        self.assertIn("nombres", errores)
        self.assertIn("apellidos", errores)

    def test_ids_deben_ser_uuid(self):
        _, errores = colaboradores.validar(datos(puesto_id="1; drop table colaboradores", sucursal_id=None))
        self.assertIn("puesto_id", errores)
        self.assertIn("sucursal_id", errores)

    def test_fecha_invalida_o_fuera_de_rango(self):
        for mala in ("2026-13-45", "ayer", "2099-01-01", "1950-01-01", None):
            _, errores = colaboradores.validar(datos(fecha_ingreso=mala))
            self.assertIn("fecha_ingreso", errores, str(mala))

    def test_salario_invalido(self):
        for malo in (0, -5, "mucho", None, True, "NaN", 10**9):
            _, errores = colaboradores.validar(datos(salario_mensual=malo))
            self.assertIn("salario_mensual", errores, str(malo))


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
        return SimpleNamespace(data="55555555-5555-4555-8555-555555555555")


class Endpoint(unittest.TestCase):
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
        r = self.preparar(None).post("/api/colaboradores", json=datos())
        self.assertEqual(r.status_code, 401)

    def test_el_jefe_no_puede_dar_de_alta(self):
        r = self.preparar(USUARIO_JEFE).post("/api/colaboradores", json=datos())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422_y_no_tocan_la_base(self):
        r = self.preparar(USUARIO_RRHH).post("/api/colaboradores", json=datos(dpi="123"))
        self.assertEqual(r.status_code, 422)
        self.assertIn("dpi", r.get_json()["campos"])
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).post("/api/colaboradores", data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_alta_correcta_da_201_y_manda_al_usuario_a_la_bitacora(self):
        r = self.preparar(USUARIO_RRHH).post("/api/colaboradores", json=datos())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["id"], "55555555-5555-4555-8555-555555555555")
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "crear_colaborador")
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])
        self.assertEqual(parametros["p_dpi"], "2345678901234")

    def test_campos_de_mas_se_ignoran(self):
        self.preparar(USUARIO_RRHH).post("/api/colaboradores", json=datos(role="jefe", id="x", p_usuario="otro"))
        _, parametros = self.base.llamadas[0]
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_dpi_repetido_da_409(self):
        error = APIError({"message": "duplicate key", "code": "23505", "hint": None, "details": None})
        r = self.preparar(USUARIO_RRHH, FalsaBase(error)).post("/api/colaboradores", json=datos())
        self.assertEqual(r.status_code, 409)

    def test_puesto_inexistente_da_400(self):
        error = APIError({"message": "foreign key", "code": "23503", "hint": None, "details": None})
        r = self.preparar(USUARIO_RRHH, FalsaBase(error)).post("/api/colaboradores", json=datos())
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
