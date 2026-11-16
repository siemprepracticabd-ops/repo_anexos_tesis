"""pruebas de la consulta de la bitacora"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import bitacora  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
OTRO = "55555555-5555-4555-8555-555555555555"


def fila(numero, usuario="Ana"):
    return {
        "id": f"id{numero}",
        "accion": "crear",
        "tabla": "colaboradores",
        "registro_id": None,
        "detalle": {"motivo": "x"},
        "creado_en": "2026-10-20T15:00:00+00:00",
        "profiles": {"full_name": usuario} if usuario else None,
    }


class FalsaConsulta:
    def __init__(self, filas):
        self.filas = filas
        self.llamadas = []

    def table(self, nombre):
        self.llamadas.append(("table", nombre))
        return self

    def __getattr__(self, nombre):
        def metodo(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))
            return self

        return metodo

    def execute(self):
        return SimpleNamespace(data=self.filas)


class Base(unittest.TestCase):
    def preparar(self, usuario, filas=None):
        self.base = FalsaConsulta(filas or [])
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(bitacora, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def usado(self, nombre):
        return [c for c in self.base.llamadas if c[0] == nombre]


class ListarBitacora(Base):
    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).get("/api/bitacora").status_code, 401)

    def test_rrhh_y_jefe_pueden_verla(self):
        for usuario in (USUARIO_RRHH, USUARIO_JEFE):
            r = self.preparar(usuario, [fila(1), fila(2, usuario=None)]).get("/api/bitacora")
            self.assertEqual(r.status_code, 200)
            cuerpo = r.get_json()
            self.assertEqual([f["usuario"] for f in cuerpo["filas"]], ["Ana", None])
            self.assertFalse(cuerpo["hay_mas"])

    def test_hay_mas_cuando_llegan_mas_de_una_pagina(self):
        r = self.preparar(USUARIO_RRHH, [fila(i) for i in range(51)]).get("/api/bitacora")
        cuerpo = r.get_json()
        self.assertEqual(len(cuerpo["filas"]), 50)
        self.assertTrue(cuerpo["hay_mas"])

    def test_la_pagina_pide_el_rango_correcto(self):
        self.preparar(USUARIO_RRHH).get("/api/bitacora?pagina=3")
        self.assertEqual(self.usado("range")[0][1], (100, 150))

    def test_filtros_se_pasan_a_la_consulta(self):
        self.preparar(USUARIO_RRHH).get(
            f"/api/bitacora?desde=2026-10-01&hasta=2026-10-15&usuario={OTRO}&accion=cerrar&tabla=periodos_planilla"
        )
        self.assertEqual(self.usado("eq")[0][1], ("usuario_id", OTRO))
        self.assertEqual(self.usado("eq")[1][1], ("accion", "cerrar"))
        self.assertEqual(self.usado("eq")[2][1], ("tabla", "periodos_planilla"))
        self.assertEqual(self.usado("gte")[0][1], ("creado_en", "2026-10-01T00:00:00-06:00"))
        self.assertEqual(self.usado("lt")[0][1], ("creado_en", "2026-10-16T00:00:00-06:00"))

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        for consulta in (
            "?desde=ayer",
            "?desde=2020-01-01",
            "?hasta=x",
            "?usuario=no-es-uuid",
            "?accion=DROP TABLE",
            "?tabla=a-b",
            "?pagina=0",
            "?pagina=abc",
            "?pagina=5000",
        ):
            self.assertEqual(cliente.get("/api/bitacora" + consulta).status_code, 422, consulta)
        self.assertEqual(self.base.llamadas, [])


class Opciones(Base):
    def test_solo_rrhh_y_jefe(self):
        self.assertEqual(self.preparar(None).get("/api/bitacora/opciones").status_code, 401)

    def test_devuelve_acciones_tablas_y_usuarios_sin_repetir(self):
        base = FalsaConsulta(None)
        respuestas = [
            [{"accion": "crear", "tabla": "colaboradores"}, {"accion": "crear", "tabla": "jornadas"}],
            [{"id": OTRO, "full_name": "Ana"}],
        ]
        base.execute = lambda: SimpleNamespace(data=respuestas.pop(0))
        with patch("auth.usuario_actual", return_value=USUARIO_JEFE), patch.object(bitacora, "get_db", return_value=base):
            r = api.app.test_client().get("/api/bitacora/opciones")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.get_json(),
            {"acciones": ["crear"], "tablas": ["colaboradores", "jornadas"], "usuarios": [{"id": OTRO, "nombre": "Ana"}]},
        )


if __name__ == "__main__":
    unittest.main()
