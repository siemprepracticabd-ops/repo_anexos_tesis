"""pruebas de baja, reactivacion y licencias"""

import os
import sys
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import bajas  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
COLABORADOR = "77777777-7777-4777-8777-777777777777"
TIPO = "55555555-5555-4555-8555-555555555555"
LICENCIA = "66666666-6666-4666-8666-666666666666"


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
            patch.object(bajas, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class DarDeBaja(Base):
    RUTA = f"/api/colaboradores/{COLABORADOR}/baja"

    def cuerpo(self, **cambios):
        base = {"fecha": "2026-10-10", "motivo": "Renunció"}
        base.update(cambios)
        return base

    def test_solo_rrhh(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)
        self.assertEqual(self.preparar(USUARIO_JEFE).post(self.RUTA, json=self.cuerpo()).status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        lejos = (date.today() + timedelta(days=400)).isoformat()
        for cuerpo in (
            self.cuerpo(fecha="ayer"),
            self.cuerpo(fecha="2023-01-01"),
            self.cuerpo(fecha=lejos),
            self.cuerpo(motivo="  "),
            self.cuerpo(motivo="x" * 501),
        ):
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_baja_correcta(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato={"turnos_liberados": 3})).post(
            self.RUTA, json=self.cuerpo(motivo=" Renunció ", p_usuario="otro")
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"turnos_liberados": 3})
        self.assertEqual(
            self.base.llamadas[0],
            (
                "dar_de_baja",
                {"p_colaborador": COLABORADOR, "p_fecha": "2026-10-10", "p_motivo": "Renunció", "p_usuario": USUARIO_RRHH["id"]},
            ),
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)


class Reactivar(Base):
    RUTA = f"/api/colaboradores/{COLABORADOR}/reactivacion"

    def test_solo_rrhh(self):
        self.assertEqual(self.preparar(USUARIO_JEFE).post(self.RUTA, json={"fecha": "2026-10-20"}).status_code, 403)

    def test_fecha_invalida(self):
        self.assertEqual(self.preparar(USUARIO_RRHH).post(self.RUTA, json={"fecha": "x"}).status_code, 422)
        self.assertEqual(self.base.llamadas, [])

    def test_reactivacion_correcta(self):
        r = self.preparar(USUARIO_RRHH).post(self.RUTA, json={"fecha": "2026-10-20"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.base.llamadas[0],
            ("reactivar_colaborador", {"p_colaborador": COLABORADOR, "p_fecha": "2026-10-20", "p_usuario": USUARIO_RRHH["id"]}),
        )

    def test_ya_activo_da_422(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base("22023", "Ese colaborador ya esta activo"))).post(
            self.RUTA, json={"fecha": "2026-10-20"}
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error"], "Ese colaborador ya esta activo")


class RegistrarLicencia(Base):
    RUTA = f"/api/colaboradores/{COLABORADOR}/licencias"

    def cuerpo(self, **cambios):
        base = {"tipo_id": TIPO, "desde": "2026-10-20", "hasta": "2026-10-22", "motivo": "Cita médica"}
        base.update(cambios)
        return base

    def test_solo_rrhh(self):
        self.assertEqual(self.preparar(None).post(self.RUTA, json=self.cuerpo()).status_code, 401)
        self.assertEqual(self.preparar(USUARIO_JEFE).post(self.RUTA, json=self.cuerpo()).status_code, 403)

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        for cuerpo in (
            self.cuerpo(tipo_id="no-es-uuid"),
            self.cuerpo(desde="ayer"),
            self.cuerpo(hasta=None),
            self.cuerpo(desde="2026-10-22", hasta="2026-10-20"),
            self.cuerpo(motivo=""),
        ):
            self.assertEqual(cliente.post(self.RUTA, json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_licencia_correcta(self):
        r = self.preparar(USUARIO_RRHH, FalsaBase(dato=LICENCIA)).post(self.RUTA, json=self.cuerpo())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json(), {"id": LICENCIA})
        self.assertEqual(
            self.base.llamadas[0],
            (
                "registrar_licencia",
                {
                    "p_colaborador": COLABORADOR,
                    "p_tipo": TIPO,
                    "p_desde": "2026-10-20",
                    "p_hasta": "2026-10-22",
                    "p_motivo": "Cita médica",
                    "p_usuario": USUARIO_RRHH["id"],
                },
            ),
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409, "22023": 422}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).post(self.RUTA, json=self.cuerpo())
            self.assertEqual(r.status_code, estado, codigo)


class AnularLicencia(Base):
    RUTA = f"/api/colaboradores/licencias/{LICENCIA}"

    def test_solo_rrhh(self):
        self.assertEqual(self.preparar(None).delete(self.RUTA).status_code, 401)
        self.assertEqual(self.preparar(USUARIO_JEFE).delete(self.RUTA).status_code, 403)

    def test_anular_correcto(self):
        r = self.preparar(USUARIO_RRHH).delete(self.RUTA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.base.llamadas[0], ("anular_licencia", {"p_licencia": LICENCIA, "p_usuario": USUARIO_RRHH["id"]})
        )

    def test_errores_de_la_base(self):
        for codigo, estado in {"P0002": 404, "55000": 409}.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).delete(self.RUTA)
            self.assertEqual(r.status_code, estado, codigo)


if __name__ == "__main__":
    unittest.main()
