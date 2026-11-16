"""pruebas de la vista previa de la planilla y de los ajustes de hora"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import planilla  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
COLABORADOR = "77777777-7777-4777-8777-777777777777"


class FalsaBase:
    def __init__(self, error=None, dato=None):
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


def error_de_base(codigo, mensaje="mensaje de la base"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


class Base(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(planilla, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class VerPlanilla(Base):
    RUTA = "/api/planilla"

    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).get(self.RUTA).status_code, 401)

    def test_rrhh_y_jefe_pueden_verla(self):
        for usuario in (USUARIO_RRHH, USUARIO_JEFE):
            r = self.preparar(usuario, FalsaBase(dato=[{"nombre": "Ana"}])).get(
                self.RUTA + "?desde=2026-10-01&hasta=2026-10-15"
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_json(), {"personas": [{"nombre": "Ana"}]})
            self.assertEqual(
                self.base.llamadas[0],
                ("calcular_planilla", {"p_inicio": "2026-10-01", "p_fin": "2026-10-15"}),
            )

    def test_la_quincena_en_curso_se_puede_ver(self):
        r = self.preparar(USUARIO_JEFE, FalsaBase(dato=[])).get(self.RUTA + "?desde=2026-10-16&hasta=2026-10-31")
        self.assertEqual(r.status_code, 200)

    def test_fechas_invalidas_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malas = [
            "",
            "?desde=ayer&hasta=2026-10-15",
            "?desde=2026-10-01",
            "?desde=2026-10-15&hasta=2026-10-01",
            "?desde=2023-12-01&hasta=2023-12-15",
            "?desde=2026-01-01&hasta=2026-12-31",
        ]
        for consulta in malas:
            self.assertEqual(cliente.get(self.RUTA + consulta).status_code, 422, consulta)
        self.assertEqual(self.base.llamadas, [])

    def test_errores_de_la_base(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base("22023"))).get(
            self.RUTA + "?desde=2026-10-01&hasta=2026-10-15"
        )
        self.assertEqual(r.status_code, 422)


class GuardarAjuste(Base):
    RUTA = "/api/planilla/ajustes"

    def cuerpo(self, **cambios):
        base = {
            "colaborador_id": COLABORADOR,
            "desde": "2026-10-01",
            "hasta": "2026-10-15",
            "valor_hora": "22",
            "valor_hora_extra": "",
            "motivo": "Trabajo mas esta quincena",
        }
        base.update(cambios)
        return base

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).put(self.RUTA, json=self.cuerpo()).status_code, 401)
        r = self.preparar(USUARIO_JEFE).put(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(colaborador_id="no-es-uuid"),
            self.cuerpo(desde="ayer"),
            self.cuerpo(hasta="2026-09-01"),
            self.cuerpo(valor_hora="0"),
            self.cuerpo(valor_hora="-5"),
            self.cuerpo(valor_hora="mucho"),
            self.cuerpo(valor_hora="NaN"),
            self.cuerpo(valor_hora="1000000"),
            self.cuerpo(valor_hora_extra="-1"),
            self.cuerpo(motivo="x" * 501),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.put(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_ajuste_correcto_manda_los_valores(self):
        r = self.preparar(USUARIO_RRHH).put(self.RUTA, json=self.cuerpo(valor_hora_extra=30, p_usuario="otro"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.base.llamadas[0],
            (
                "guardar_ajuste_planilla",
                {
                    "p_inicio": "2026-10-01",
                    "p_fin": "2026-10-15",
                    "p_colaborador": COLABORADOR,
                    "p_valor_hora": "22",
                    "p_valor_extra": "30",
                    "p_motivo": "Trabajo mas esta quincena",
                    "p_usuario": USUARIO_RRHH["id"],
                },
            ),
        )

    def test_campos_vacios_quitan_el_ajuste(self):
        r = self.preparar(USUARIO_RRHH).put(self.RUTA, json=self.cuerpo(valor_hora="", valor_hora_extra=None, motivo=""))
        self.assertEqual(r.status_code, 200)
        parametros = self.base.llamadas[0][1]
        self.assertIsNone(parametros["p_valor_hora"])
        self.assertIsNone(parametros["p_valor_extra"])
        self.assertIsNone(parametros["p_motivo"])

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).put(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)

class DescuentosManuales(Base):
    RUTA = "/api/planilla/descuentos"

    def cuerpo(self, **cambios):
        base = {
            "colaborador_id": COLABORADOR,
            "desde": "2026-10-01",
            "hasta": "2026-10-15",
            "monto": "50.50",
            "motivo": "Adelanto de sueldo",
        }
        base.update(cambios)
        return base

    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)

    def test_rrhh_y_jefe_pueden_agregar(self):
        for usuario in (USUARIO_RRHH, USUARIO_JEFE):
            r = self.preparar(usuario, FalsaBase(dato="id-nuevo")).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, 201)
            self.assertEqual(r.get_json(), {"id": "id-nuevo"})

    def test_manda_los_valores_a_la_base(self):
        self.preparar(USUARIO_RRHH, FalsaBase(dato="x")).post(self.RUTA, json=self.cuerpo(p_usuario="otro"))
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "agregar_descuento_manual")
        self.assertEqual(
            parametros,
            {
                "p_colaborador": COLABORADOR,
                "p_inicio": "2026-10-01",
                "p_fin": "2026-10-15",
                "p_monto": "50.50",
                "p_motivo": "Adelanto de sueldo",
                "p_usuario": USUARIO_RRHH["id"],
            },
        )

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(colaborador_id="no-es-uuid"),
            self.cuerpo(desde="ayer"),
            self.cuerpo(monto=""),
            self.cuerpo(monto="0"),
            self.cuerpo(monto="-5"),
            self.cuerpo(monto="abc"),
            self.cuerpo(monto="999999999"),
            self.cuerpo(motivo=" "),
            self.cuerpo(motivo="ab"),
            self.cuerpo(motivo="x" * 201),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)

    def test_quitar_un_descuento(self):
        ruta = f"{self.RUTA}/66666666-6666-4666-8666-666666666666"
        self.assertEqual(self.preparar(None).delete(ruta).status_code, 401)
        r = self.preparar(USUARIO_JEFE).delete(ruta)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.base.llamadas[0][0], "quitar_descuento_manual")

    def test_quitar_con_la_quincena_cerrada(self):
        ruta = f"{self.RUTA}/66666666-6666-4666-8666-666666666666"
        r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base("55000"))).delete(ruta)
        self.assertEqual(r.status_code, 409)


class CerrarQuincena(Base):
    RUTA = "/api/planilla/cierre"

    def cuerpo(self, **cambios):
        base = {"desde": "2026-10-01", "hasta": "2026-10-15"}
        base.update(cambios)
        return base

    def test_solo_el_jefe_puede_cerrar(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)
        r = self.preparar(USUARIO_RRHH).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_fechas_invalidas_dan_422(self):
        cliente = self.preparar(USUARIO_JEFE)
        malas = [
            self.cuerpo(desde="ayer"),
            self.cuerpo(hasta=None),
            self.cuerpo(hasta="2026-09-01"),
            self.cuerpo(desde="2023-01-01", hasta="2023-01-15"),
            self.cuerpo(desde="2099-01-01", hasta="2099-01-15"),
        ]
        for cuerpo in malas:
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_cierre_correcto(self):
        resultado = {"periodo_id": "p1", "boletas": 12, "neto_total": 15699.67}
        r = self.preparar(USUARIO_JEFE, FalsaBase(dato=resultado)).post(self.RUTA, json=self.cuerpo(p_usuario="otro"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json(), resultado)
        self.assertEqual(
            self.base.llamadas[0],
            ("cerrar_planilla", {"p_inicio": "2026-10-01", "p_fin": "2026-10-15", "p_usuario": USUARIO_JEFE["id"]}),
        )

    def test_con_pendientes_devuelve_el_mensaje_de_la_base(self):
        mensaje = "Todavia hay pendientes: 2 jornada(s) incompleta(s)"
        r = self.preparar(USUARIO_JEFE, FalsaBase(error_de_base("22023", mensaje))).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error"], mensaje)

    def test_quincena_ya_cerrada_da_409(self):
        r = self.preparar(USUARIO_JEFE, FalsaBase(error_de_base("55000"))).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 409)


class PagarBoletas(Base):
    PERIODO = "88888888-8888-4888-8888-888888888888"
    RUTA = f"/api/planilla/periodos/{PERIODO}/pago"

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post(self.RUTA).status_code, 401)
        self.assertEqual(self.preparar(USUARIO_JEFE).post(self.RUTA).status_code, 403)

    def test_pago_correcto(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato=12)).post(self.RUTA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"boletas": 12})
        self.assertEqual(
            self.base.llamadas[0],
            ("marcar_boletas_pagadas", {"p_periodo": self.PERIODO, "p_usuario": USUARIO_RRHH["id"]}),
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA)
            self.assertEqual(r.status_code, estado, codigo)


if __name__ == "__main__":
    unittest.main()

