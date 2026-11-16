"""pruebas de la modalidad y la forma de pago de los colaboradores"""

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

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}
COLABORADOR = "55555555-5555-4555-8555-555555555555"
RUTA = f"/api/colaboradores/{COLABORADOR}/condiciones"


class ValidarPago(unittest.TestCase):
    def test_sin_datos_asume_tiempo_completo_con_salario_fijo_pero_pide_el_salario(self):
        valores, errores = colaboradores.validar_pago({})
        self.assertEqual(valores["p_modalidad"], "tiempo_completo")
        self.assertEqual(valores["p_forma_pago"], "salario_fijo")
        self.assertIn("salario_mensual", errores)

    def test_salario_fijo_usa_el_salario_e_ignora_la_tarifa(self):
        valores, errores = colaboradores.validar_pago({"forma_pago": "salario_fijo", "salario_mensual": 4000, "tarifa": 20})
        self.assertEqual(errores, {})
        self.assertEqual(Decimal(valores["p_salario"]), Decimal("4000"))
        self.assertIsNone(valores["p_tarifa"])

    def test_por_hora_y_por_turno_usan_la_tarifa_e_ignoran_el_salario(self):
        for forma in ("por_hora", "por_turno"):
            valores, errores = colaboradores.validar_pago(
                {"modalidad": "guardia", "forma_pago": forma, "salario_mensual": 4000, "tarifa": "250.50"}
            )
            self.assertEqual(errores, {}, forma)
            self.assertEqual(Decimal(valores["p_tarifa"]), Decimal("250.50"))
            self.assertIsNone(valores["p_salario"])

    def test_por_hora_sin_tarifa_da_error_de_tarifa(self):
        _, errores = colaboradores.validar_pago({"forma_pago": "por_hora", "salario_mensual": 4000})
        self.assertIn("tarifa", errores)
        self.assertNotIn("salario_mensual", errores)

    def test_montos_invalidos(self):
        for malo in (0, -5, "mucho", None, True, "NaN", "Infinity", 10**9):
            _, errores = colaboradores.validar_pago({"forma_pago": "por_hora", "tarifa": malo})
            self.assertIn("tarifa", errores, str(malo))
            _, errores = colaboradores.validar_pago({"forma_pago": "salario_fijo", "salario_mensual": malo})
            self.assertIn("salario_mensual", errores, str(malo))

    def test_modalidad_o_forma_desconocida(self):
        _, errores = colaboradores.validar_pago({"modalidad": "freelance", "forma_pago": "trueque"})
        self.assertIn("modalidad", errores)
        self.assertIn("forma_pago", errores)

    def test_el_alta_incluye_modalidad_y_forma_de_pago(self):
        valores, errores = colaboradores.validar(
            {
                "nombres": "Ana",
                "apellidos": "Lopez",
                "dpi": "2345678901234",
                "puesto_id": "11111111-1111-4111-8111-111111111111",
                "sucursal_id": "22222222-2222-4222-8222-222222222222",
                "fecha_ingreso": "2026-10-01",
                "modalidad": "guardia",
                "forma_pago": "por_turno",
                "tarifa": 250,
            }
        )
        self.assertEqual(errores, {})
        self.assertEqual(valores["p_modalidad"], "guardia")
        self.assertEqual(valores["p_forma_pago"], "por_turno")
        self.assertIsNone(valores["p_salario"])
        self.assertEqual(Decimal(valores["p_tarifa"]), Decimal("250"))


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
        return SimpleNamespace(data=None)


def error_de_base(codigo, mensaje="x"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


def cuerpo(**cambios):
    base = {"modalidad": "guardia", "forma_pago": "por_turno", "tarifa": 250, "desde": "2026-11-01"}
    base.update(cambios)
    return base


class CambiarCondiciones(unittest.TestCase):
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
        self.assertEqual(self.preparar(None).put(RUTA, json=cuerpo()).status_code, 401)

    def test_el_jefe_no_puede_cambiar_condiciones(self):
        r = self.preparar(USUARIO_JEFE).put(RUTA, json=cuerpo())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA, data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_modalidad_y_forma_son_obligatorias_aqui(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA, json={"tarifa": 250, "desde": "2026-11-01"})
        self.assertEqual(r.status_code, 422)
        campos = r.get_json()["campos"]
        self.assertIn("modalidad", campos)
        self.assertIn("forma_pago", campos)
        self.assertEqual(self.base.llamadas, [])

    def test_fechas_invalidas_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        for mala in ("ayer", "2023-12-31", "2099-01-01", "", None):
            r = cliente.put(RUTA, json=cuerpo(desde=mala))
            self.assertEqual(r.status_code, 422, str(mala))
            self.assertIn("desde", r.get_json()["campos"])
        self.assertEqual(self.base.llamadas, [])

    def test_cambio_correcto_usa_el_token_y_manda_los_montos_que_corresponden(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA, json=cuerpo(p_usuario="otro", salario_mensual=9999))
        self.assertEqual(r.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "cambiar_condiciones_pago")
        self.assertEqual(parametros["p_colaborador"], COLABORADOR)
        self.assertEqual(parametros["p_modalidad"], "guardia")
        self.assertEqual(parametros["p_forma_pago"], "por_turno")
        self.assertIsNone(parametros["p_salario"])
        self.assertEqual(Decimal(parametros["p_tarifa"]), Decimal("250"))
        self.assertEqual(parametros["p_desde"], "2026-11-01")
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "22023": 422, "23514": 422}
        for codigo, estado in esperados.items():
            base = FalsaBase(error_de_base(codigo, "La fecha debe ser posterior"))
            r = self.preparar(USUARIO_RRHH, base).put(RUTA, json=cuerpo())
            self.assertEqual(r.status_code, estado, codigo)

    def test_el_motivo_de_fecha_llega_al_campo_desde(self):
        base = FalsaBase(error_de_base("22023", "La fecha debe ser posterior al inicio actual (2026-01-05)"))
        r = self.preparar(USUARIO_RRHH, base).put(RUTA, json=cuerpo())
        self.assertIn("posterior", r.get_json()["campos"]["desde"])


if __name__ == "__main__":
    unittest.main()
