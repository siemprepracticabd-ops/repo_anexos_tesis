"""pruebas de las decisiones sobre horas extra y la justificacion de ausencias"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import pendientes  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
EXTRA = "55555555-5555-4555-8555-555555555555"
AUSENCIA = "66666666-6666-4666-8666-666666666666"
TIPO = "77777777-7777-4777-8777-777777777777"
RUTA_EXTRA = f"/api/horas-extra/{EXTRA}/decision"
RUTA_AUSENCIA = f"/api/ausencias/{AUSENCIA}/justificacion"


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


class Base(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(pendientes, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class DecidirHorasExtra(Base):
    def cuerpo(self, **cambios):
        base = {"decision": "autorizada", "justificacion": "Cierre de caja", "autorizado_por": "Don Carlos"}
        base.update(cambios)
        return base

    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).put(RUTA_EXTRA, json=self.cuerpo()).status_code, 401)

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA_EXTRA, data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_decision_o_justificacion_invalidas_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(decision="pendiente"),
            self.cuerpo(decision="quizas"),
            self.cuerpo(decision=None),
            self.cuerpo(justificacion="   "),
            self.cuerpo(justificacion="x" * 501),
            self.cuerpo(decision="parcial", minutos_pagados="mucho"),
            self.cuerpo(decision="parcial", minutos_pagados=-5),
            self.cuerpo(decision="parcial", minutos_pagados=None),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.put(RUTA_EXTRA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_rrhh_debe_decir_quien_autorizo(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA_EXTRA, json=self.cuerpo(autorizado_por=""))
        self.assertEqual(r.status_code, 422)
        self.assertIn("autorizado_por", r.get_json()["campos"])
        self.assertEqual(self.base.llamadas, [])

    def test_el_jefe_se_registra_a_si_mismo_como_quien_autorizo(self):
        r = self.preparar(USUARIO_JEFE).put(RUTA_EXTRA, json=self.cuerpo(autorizado_por="Otra persona"))
        self.assertEqual(r.status_code, 200)
        parametros = self.base.llamadas[0][1]
        self.assertEqual(parametros["p_autorizado_por"], "Don Carlos")
        self.assertEqual(parametros["p_usuario"], USUARIO_JEFE["id"])

    def test_decision_correcta_de_rrhh_manda_todo_a_la_base(self):
        r = self.preparar(USUARIO_RRHH).put(
            RUTA_EXTRA,
            json=self.cuerpo(decision="parcial", minutos_pagados="40", justificacion="  Solo hasta las 14:40 ", p_usuario="otro"),
        )
        self.assertEqual(r.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "resolver_horas_extra")
        self.assertEqual(
            parametros,
            {
                "p_horas_extra": EXTRA,
                "p_decision": "parcial",
                "p_minutos_pagados": 40,
                "p_justificacion": "Solo hasta las 14:40",
                "p_autorizado_por": "Don Carlos",
                "p_usuario": USUARIO_RRHH["id"],
            },
        )

    def test_autorizada_y_rechazada_no_mandan_minutos(self):
        cliente = self.preparar(USUARIO_RRHH)
        cliente.put(RUTA_EXTRA, json=self.cuerpo(decision="autorizada", minutos_pagados=10))
        cliente.put(RUTA_EXTRA, json=self.cuerpo(decision="rechazada", minutos_pagados=10))
        self.assertIsNone(self.base.llamadas[0][1]["p_minutos_pagados"])
        self.assertIsNone(self.base.llamadas[1][1]["p_minutos_pagados"])

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "55000": 409, "22023": 422}
        for codigo, estado in esperados.items():
            base = FalsaBase(error_de_base(codigo, "Los minutos pagados deben ser menores"))
            r = self.preparar(USUARIO_RRHH, base).put(RUTA_EXTRA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)

    def test_el_mensaje_de_la_base_llega_a_la_pantalla(self):
        base = FalsaBase(error_de_base("22023", "Los minutos pagados deben ser menores que los detectados (70)"))
        r = self.preparar(USUARIO_RRHH, base).put(RUTA_EXTRA, json=self.cuerpo())
        self.assertIn("70", r.get_json()["error"])


class JustificarAusencia(Base):
    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).put(RUTA_AUSENCIA, json={"tipo_id": TIPO, "motivo": "x"}).status_code, 401)

    def test_el_jefe_no_puede_justificar(self):
        r = self.preparar(USUARIO_JEFE).put(RUTA_AUSENCIA, json={"tipo_id": TIPO, "motivo": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).put(RUTA_AUSENCIA, data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            {"tipo_id": "no-es-uuid", "motivo": "x"},
            {"tipo_id": None, "motivo": "x"},
            {"tipo_id": TIPO, "motivo": "   "},
            {"tipo_id": TIPO},
            {"tipo_id": TIPO, "motivo": "x" * 501},
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.put(RUTA_AUSENCIA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_justificacion_correcta_usa_el_token(self):
        r = self.preparar(USUARIO_RRHH).put(
            RUTA_AUSENCIA, json={"tipo_id": TIPO.upper(), "motivo": " Cita medica ", "p_usuario": "otro"}
        )
        self.assertEqual(r.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "justificar_ausencia")
        self.assertEqual(
            parametros,
            {"p_ausencia": AUSENCIA, "p_tipo": TIPO, "p_motivo": "Cita medica", "p_usuario": USUARIO_RRHH["id"]},
        )

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "55000": 409, "23503": 422, "22023": 422}
        for codigo, estado in esperados.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).put(
                RUTA_AUSENCIA, json={"tipo_id": TIPO, "motivo": "x"}
            )
            self.assertEqual(r.status_code, estado, codigo)


if __name__ == "__main__":
    unittest.main()
