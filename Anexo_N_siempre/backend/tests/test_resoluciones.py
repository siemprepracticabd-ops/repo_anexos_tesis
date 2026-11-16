"""pruebas de los descuentos por tardanza y de resolver jornadas"""

import os
import sys
import unittest
from decimal import Decimal  # noqa: F401
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import resoluciones  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
DESCUENTO = "55555555-5555-4555-8555-555555555555"
JORNADA = "66666666-6666-4666-8666-666666666666"
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
            patch.object(resoluciones, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class PrepararDescuentos(Base):
    RUTA = "/api/descuentos/preparar"

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json={}).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post(self.RUTA, json={"desde": "2026-10-16", "hasta": "2026-10-31"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_fechas_invalidas_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malas = [
            {"desde": "ayer", "hasta": "2026-10-31"},
            {"desde": "2026-10-16"},
            {"desde": "2026-10-31", "hasta": "2026-10-16"},
            {"desde": "2023-12-31", "hasta": "2024-01-10"},
            {"desde": "2026-01-01", "hasta": "2026-12-31"},
        ]
        for cuerpo in malas:
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_preparar_correcto_devuelve_cuantas_personas(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato=3)).post(
            self.RUTA, json={"desde": "2026-10-16", "hasta": "2026-10-31", "p_usuario": "otro"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"personas": 3})
        self.assertEqual(
            self.base.llamadas[0],
            ("preparar_descuentos", {"p_inicio": "2026-10-16", "p_fin": "2026-10-31", "p_usuario": USUARIO_RRHH["id"]}),
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(
                self.RUTA, json={"desde": "2026-10-16", "hasta": "2026-10-31"}
            )
            self.assertEqual(r.status_code, estado, codigo)


class DecidirDescuento(Base):
    RUTA = f"/api/descuentos/{DESCUENTO}/decision"

    def cuerpo(self, **cambios):
        base = {"decision": "aplicado", "justificacion": "Llego tarde varias veces", "autorizado_por": "Don Carlos"}
        base.update(cambios)
        return base

    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).put(self.RUTA, json=self.cuerpo()).status_code, 401)

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(decision="pendiente"),
            self.cuerpo(decision="autorizada"),
            self.cuerpo(justificacion=" "),
            self.cuerpo(decision="parcial", minutos_descontados=None),
            self.cuerpo(decision="parcial", minutos_descontados="mucho"),
            self.cuerpo(autorizado_por=""),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.put(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_decision_parcial_manda_los_minutos(self):
        r = self.preparar(USUARIO_RRHH).put(
            self.RUTA, json=self.cuerpo(decision="parcial", minutos_descontados="30", p_usuario="otro")
        )
        self.assertEqual(r.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "resolver_descuento")
        self.assertEqual(
            parametros,
            {
                "p_id": DESCUENTO,
                "p_decision": "parcial",
                "p_minutos": 30,
                "p_justificacion": "Llego tarde varias veces",
                "p_autorizado_por": "Don Carlos",
                "p_usuario": USUARIO_RRHH["id"],
            },
        )

    def test_aplicado_y_no_aplicado_no_mandan_minutos(self):
        cliente = self.preparar(USUARIO_RRHH)
        cliente.put(self.RUTA, json=self.cuerpo(decision="aplicado", minutos_descontados=10))
        cliente.put(self.RUTA, json=self.cuerpo(decision="no_aplicado", minutos_descontados=10))
        self.assertIsNone(self.base.llamadas[0][1]["p_minutos"])
        self.assertIsNone(self.base.llamadas[1][1]["p_minutos"])

    def test_el_jefe_se_registra_a_si_mismo(self):
        self.preparar(USUARIO_JEFE).put(self.RUTA, json=self.cuerpo(autorizado_por="Otra persona"))
        self.assertEqual(self.base.llamadas[0][1]["p_autorizado_por"], "Don Carlos")

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).put(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)


class CorreccionDeJornada(Base):
    RUTA = f"/api/jornadas/{JORNADA}/correccion"

    def cuerpo(self, **cambios):
        base = {"entrada": "2026-10-20T06:00", "salida": None, "motivo": "Marco tarde por error del reloj"}
        base.update(cambios)
        return base

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(entrada=None),
            self.cuerpo(entrada="ayer"),
            self.cuerpo(salida="25:99"),
            self.cuerpo(motivo="  "),
            self.cuerpo(motivo="x" * 501),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_las_horas_se_interpretan_en_hora_de_guatemala(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato=True)).post(
            self.RUTA, json=self.cuerpo(salida="2026-10-20T14:05")
        )
        self.assertEqual(r.status_code, 200)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "corregir_jornada")
        self.assertEqual(
            parametros,
            {
                "p_jornada": JORNADA,
                "p_entrada": "2026-10-20T06:00:00-06:00",
                "p_salida": "2026-10-20T14:05:00-06:00",
                "p_motivo": "Marco tarde por error del reloj",
                "p_usuario": USUARIO_RRHH["id"],
            },
        )

    def test_solo_una_de_las_horas(self):
        self.preparar(USUARIO_RRHH, FalsaBase(dato=True)).post(self.RUTA, json=self.cuerpo(entrada="", salida="2026-10-20T14:05"))
        self.assertIsNone(self.base.llamadas[0][1]["p_entrada"])

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)


class AsistenciaEnAusencia(Base):
    AUSENCIA = "88888888-8888-4888-8888-888888888888"
    RUTA = f"/api/ausencias/{AUSENCIA}/asistencia"

    def cuerpo(self, **cambios):
        base = {"entrada": "2026-10-20T08:00", "salida": "2026-10-20T17:00", "motivo": "Olvido marcar"}
        base.update(cambios)
        return base

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(entrada=None),
            self.cuerpo(salida=""),
            self.cuerpo(entrada="ayer"),
            self.cuerpo(motivo="  "),
            self.cuerpo(motivo="x" * 501),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_las_horas_se_interpretan_en_hora_de_guatemala(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato={"jornada": True, "ausencia_vigente": False})).post(
            self.RUTA, json=self.cuerpo()
        )
        self.assertEqual(r.status_code, 201)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "registrar_asistencia_en_ausencia")
        self.assertEqual(
            parametros,
            {
                "p_ausencia": self.AUSENCIA,
                "p_entrada": "2026-10-20T08:00:00-06:00",
                "p_salida": "2026-10-20T17:00:00-06:00",
                "p_motivo": "Olvido marcar",
                "p_usuario": USUARIO_RRHH["id"],
            },
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)


class MarcacionManual(Base):
    RUTA = "/api/marcaciones-manuales"

    def cuerpo(self, **cambios):
        base = {
            "colaborador_id": COLABORADOR,
            "fecha": "2026-10-20",
            "hora": "13:03",
            "tipo": "salida",
            "motivo": "Olvido marcar la salida",
        }
        base.update(cambios)
        return base

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            self.cuerpo(colaborador_id="no-es-uuid"),
            self.cuerpo(fecha="ayer"),
            self.cuerpo(fecha="2023-01-01"),
            self.cuerpo(hora="25:00"),
            self.cuerpo(hora=None),
            self.cuerpo(tipo="desconocido"),
            self.cuerpo(motivo="  "),
            self.cuerpo(motivo="x" * 501),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_la_hora_se_interpreta_en_hora_de_guatemala(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato=JORNADA)).post(self.RUTA, json=self.cuerpo(p_usuario="otro"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json(), {"id": JORNADA})
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "agregar_marcacion_manual")
        self.assertEqual(
            parametros,
            {
                "p_colaborador": COLABORADOR,
                "p_momento": "2026-10-20T13:03:00-06:00",
                "p_tipo": "salida",
                "p_motivo": "Olvido marcar la salida",
                "p_usuario": USUARIO_RRHH["id"],
            },
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)


class ConfirmarJornada(Base):
    RUTA = f"/api/jornadas/{JORNADA}/confirmacion"

    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json={"motivo": "x"}).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post(self.RUTA, json={"motivo": "x"})
        self.assertEqual(r.status_code, 403)

    def test_motivo_obligatorio(self):
        cliente = self.preparar(USUARIO_RRHH)
        for malo in ({}, {"motivo": "   "}, {"motivo": "x" * 501}):
            self.assertEqual(cliente.post(self.RUTA, json=malo).status_code, 422, malo)
        self.assertEqual(self.base.llamadas, [])

    def test_confirmacion_correcta(self):
        r = self.preparar(USUARIO_RRHH).post(self.RUTA, json={"motivo": " Cubrio un turno "})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.base.llamadas[0],
            ("confirmar_jornada", {"p_jornada": JORNADA, "p_motivo": "Cubrio un turno", "p_usuario": USUARIO_RRHH["id"]}),
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json={"motivo": "x"})
            self.assertEqual(r.status_code, estado, codigo)


if __name__ == "__main__":
    unittest.main()
