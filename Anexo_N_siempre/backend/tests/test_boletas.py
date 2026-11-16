"""pruebas de los pdf de boletas y de la planilla general"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import boletas  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
PERIODO = "88888888-8888-4888-8888-888888888888"
BOLETA = "99999999-9999-4999-8999-999999999999"

PERIODO_DATOS = {"id": PERIODO, "fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15", "estado": "cerrado"}


def boleta(numero, nombre, snapshot=None, **cambios):
    datos = {
        "id": BOLETA,
        "numero": numero,
        "estado": "generada",
        "total_ingresos": 1000.5,
        "total_descuentos": 100,
        "neto": 900.5,
        "periodo_id": PERIODO,
        "snapshot_valores": snapshot or {"forma_pago": "por_hora", "minutos_trabajados": 3000},
        "colaboradores": {
            "nombres": nombre,
            "apellidos": "Prueba",
            "puestos": {"nombre": "Cajero"},
            "sucursales": {"nombre": "Sucursal Norte"},
        },
        "boleta_detalles": [
            {"tipo": "descuento", "concepto": "Dias de ausencia", "cantidad": 1, "valor_unitario": 100, "monto": 100},
            {"tipo": "ingreso", "concepto": "Horas trabajadas", "cantidad": 50, "valor_unitario": 20.01, "monto": 1000.5},
        ],
    }
    datos.update(cambios)
    return datos


class FalsaBase:
    def __init__(self, periodos, boletas_):
        self.periodos = periodos
        self.boletas = boletas_
        self.tabla = None

    def table(self, nombre):
        self.tabla = nombre
        return self

    def select(self, columnas):
        return self

    def eq(self, columna, valor):
        return self

    def order(self, columna):
        return self

    def execute(self):
        return SimpleNamespace(data=self.periodos if self.tabla == "periodos_planilla" else self.boletas)


class Base(unittest.TestCase):
    def preparar(self, usuario, periodos=None, boletas_=None):
        self.base = FalsaBase([PERIODO_DATOS.copy()] if periodos is None else periodos,
                              [boleta(1, "Ana"), boleta(2, "Bea", {"forma_pago": "por_turno", "turnos": 7})] if boletas_ is None else boletas_)
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(boletas, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class PdfDeBoletas(Base):
    def test_sin_sesion_da_401(self):
        for ruta in (f"/api/boletas/{BOLETA}/boleta.pdf", f"/api/boletas/periodo/{PERIODO}/planilla.pdf",
                     f"/api/boletas/periodo/{PERIODO}/boletas.pdf"):
            self.assertEqual(self.preparar(None).get(ruta).status_code, 401, ruta)

    def test_rrhh_y_jefe_reciben_un_pdf(self):
        for usuario in (USUARIO_RRHH, USUARIO_JEFE):
            for ruta in (f"/api/boletas/{BOLETA}/boleta.pdf", f"/api/boletas/periodo/{PERIODO}/planilla.pdf",
                         f"/api/boletas/periodo/{PERIODO}/boletas.pdf"):
                r = self.preparar(usuario).get(ruta)
                self.assertEqual(r.status_code, 200, ruta)
                self.assertEqual(r.mimetype, "application/pdf")
                self.assertTrue(r.data.startswith(b"%PDF"), ruta)

    def test_la_boleta_individual_lleva_el_numero_en_el_nombre(self):
        r = self.preparar(USUARIO_RRHH).get(f"/api/boletas/{BOLETA}/boleta.pdf")
        self.assertIn("boleta-1.pdf", r.headers["Content-Disposition"])

    def test_boleta_con_ajuste_y_forma_de_pago_distinta(self):
        ajustada = boleta(3, "Eva", {"forma_pago": "salario_fijo", "minutos_trabajados": 0,
                                     "ajuste": {"valor_hora": 22, "motivo": "Trabajo mas"}})
        r = self.preparar(USUARIO_RRHH, boletas_=[ajustada]).get(f"/api/boletas/{BOLETA}/boleta.pdf")
        self.assertEqual(r.status_code, 200)

    def test_no_existe_da_404(self):
        cliente = self.preparar(USUARIO_RRHH, periodos=[], boletas_=[])
        self.assertEqual(cliente.get(f"/api/boletas/{BOLETA}/boleta.pdf").status_code, 404)
        self.assertEqual(cliente.get(f"/api/boletas/periodo/{PERIODO}/planilla.pdf").status_code, 404)
        self.assertEqual(cliente.get(f"/api/boletas/periodo/{PERIODO}/boletas.pdf").status_code, 404)

    def test_periodo_sin_boletas_no_da_boletas_pdf(self):
        r = self.preparar(USUARIO_RRHH, boletas_=[]).get(f"/api/boletas/periodo/{PERIODO}/boletas.pdf")
        self.assertEqual(r.status_code, 404)

    def test_ruta_que_no_es_uuid_da_404(self):
        self.assertEqual(self.preparar(USUARIO_RRHH).get("/api/boletas/uno/boleta.pdf").status_code, 404)


if __name__ == "__main__":
    unittest.main()