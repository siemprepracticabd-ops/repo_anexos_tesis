"""pruebas del endpoint que descarga los calendarios en pdf"""

import os
import sys
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import calendarios  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}

PROGRAMACION = "55555555-5555-4555-8555-555555555555"
RUTA = f"/api/programaciones/{PROGRAMACION}/calendario.pdf"
SUC_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUC_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ANA = "11111111-1111-4111-8111-111111111111"
LUIS = "22222222-2222-4222-8222-222222222222"
MANANA = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
NOCHE = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


class Consulta:
    """imita la cadena table().select().eq().order().range().limit().execute() de supabase"""

    def __init__(self, filas):
        self.filas = filas
        self.filtros = []
        self.excluidos = []
        self.rango = None

    def select(self, *_):
        return self

    def eq(self, columna, valor):
        self.filtros.append((columna, valor))
        return self

    def neq(self, columna, valor):
        self.excluidos.append((columna, valor))
        return self

    def order(self, *_):
        return self

    def limit(self, *_):
        return self

    def range(self, desde, hasta):
        self.rango = (desde, hasta)
        return self

    def execute(self):
        filas = [
            f
            for f in self.filas
            if all(f.get(c) == v for c, v in self.filtros) and not any(f.get(c) == v for c, v in self.excluidos)
        ]
        if self.rango:
            filas = filas[self.rango[0] : self.rango[1] + 1]
        return SimpleNamespace(data=filas)


class FalsaBase:
    def __init__(self, programacion=None, asignaciones=None):
        self.programacion = {
            "id": PROGRAMACION,
            "tipo": "semanal",
            "fecha_inicio": "2026-10-26",
            "fecha_fin": "2026-11-01",
            "version": 2,
            "estado": "publicada",
            "publicada_en": "2026-10-20T14:15:00.123456+00:00",
        }
        if programacion is not None:
            self.programacion = programacion
        self.tablas = {
            "programaciones": [self.programacion] if programacion != "ninguna" else [],
            "colaboradores": [
                {"id": ANA, "nombres": "Ana", "apellidos": "Lopez", "sucursal_base_id": SUC_A, "sucursales": {"nombre": "Sucursal Norte"}},
                {"id": LUIS, "nombres": "Luis", "apellidos": "Perez", "sucursal_base_id": SUC_B, "sucursales": {"nombre": "Sucursal Sur"}},
            ],
            "turnos": [
                {"id": MANANA, "nombre": "Mañana", "hora_inicio": "05:00:00", "hora_fin": "13:00:00", "cruza_medianoche": False},
                {"id": NOCHE, "nombre": "Noche", "hora_inicio": "21:00:00", "hora_fin": "05:00:00", "cruza_medianoche": True},
            ],
            "asignaciones_turno": asignaciones
            if asignaciones is not None
            else [
                {"programacion_id": PROGRAMACION, "colaborador_id": ANA, "fecha": "2026-10-26", "turno_id": MANANA},
                {"programacion_id": PROGRAMACION, "colaborador_id": ANA, "fecha": "2026-10-27", "turno_id": None},
                {"programacion_id": PROGRAMACION, "colaborador_id": ANA, "fecha": "2026-10-28", "turno_id": NOCHE},
                {"programacion_id": PROGRAMACION, "colaborador_id": LUIS, "fecha": "2026-10-26", "turno_id": NOCHE},
                {"programacion_id": "otra", "colaborador_id": ANA, "fecha": "2026-10-29", "turno_id": MANANA},
            ],
        }

    def table(self, nombre):
        return Consulta(self.tablas[nombre])


class Endpoint(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        self.espia_calendario = unittest.mock.Mock(return_value=b"%PDF-calendario")
        self.espia_hoja = unittest.mock.Mock(return_value=b"%PDF-hoja")
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(calendarios, "get_db", return_value=self.base),
            patch.object(calendarios, "generar_calendario", self.espia_calendario),
            patch.object(calendarios, "generar_hoja_individual", self.espia_hoja),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).get(RUTA).status_code, 401)

    def test_el_jefe_puede_descargar(self):
        r = self.preparar(USUARIO_JEFE).get(RUTA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertEqual(r.data, b"%PDF-calendario")

    def test_el_pdf_no_se_guarda_en_cache(self):
        r = self.preparar(USUARIO_RRHH).get(RUTA)
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertIn("calendario-2026-10-26-v2.pdf", r.headers["Content-Disposition"])

    def test_quien_estaba_de_baja_y_sin_turnos_no_sale(self):
        base = FalsaBase(
            asignaciones=[{"programacion_id": PROGRAMACION, "colaborador_id": ANA, "fecha": "2026-10-26", "turno_id": MANANA}]
        )
        base.tablas["colaboradores"][0]["periodos_laborales"] = [{"fecha_ingreso": "2026-01-05", "fecha_baja": None}]
        base.tablas["colaboradores"][1]["periodos_laborales"] = [{"fecha_ingreso": "2026-01-05", "fecha_baja": "2026-10-10"}]
        self.preparar(USUARIO_RRHH, base).get(RUTA)
        argumentos = self.espia_calendario.call_args.kwargs or dict(
            zip(("titulo", "periodo", "version", "estado", "publicada_en", "dias", "filas"), self.espia_calendario.call_args.args)
        )
        self.assertEqual([fila[0] for fila in argumentos["filas"]], ["Lopez, Ana"])

    def test_quien_se_dio_de_baja_pero_tiene_turnos_si_sale(self):
        base = FalsaBase()
        base.tablas["colaboradores"][1]["periodos_laborales"] = [{"fecha_ingreso": "2026-01-05", "fecha_baja": "2026-10-10"}]
        base.tablas["colaboradores"][0]["periodos_laborales"] = [{"fecha_ingreso": "2026-01-05", "fecha_baja": None}]
        self.preparar(USUARIO_RRHH, base).get(RUTA)
        argumentos = self.espia_calendario.call_args.kwargs or dict(
            zip(("titulo", "periodo", "version", "estado", "publicada_en", "dias", "filas"), self.espia_calendario.call_args.args)
        )
        self.assertEqual(len(argumentos["filas"]), 2)

    def test_programacion_inexistente_da_404(self):
        self.assertEqual(self.preparar(USUARIO_RRHH, FalsaBase(programacion="ninguna")).get(RUTA).status_code, 404)

    def test_filtros_invalidos_dan_400(self):
        cliente = self.preparar(USUARIO_RRHH)
        self.assertEqual(cliente.get(RUTA + "?sucursal=abc").status_code, 400)
        self.assertEqual(cliente.get(RUTA + "?colaborador=abc").status_code, 400)
        self.assertEqual(cliente.get(f"{RUTA}?sucursal={SUC_A}&colaborador={ANA}").status_code, 400)

    def test_calendario_completo_arma_las_filas_y_el_encabezado(self):
        self.preparar(USUARIO_RRHH).get(RUTA)
        argumentos = self.espia_calendario.call_args.kwargs or dict(
            zip(("titulo", "periodo", "version", "estado", "publicada_en", "dias", "filas"), self.espia_calendario.call_args.args)
        )
        self.assertEqual(argumentos["periodo"], "Semanal del 26/10/2026 al 01/11/2026")
        self.assertEqual(argumentos["version"], 2)
        self.assertEqual(argumentos["publicada_en"], "20/10/2026 08:15")
        self.assertEqual(len(argumentos["dias"]), 7)
        self.assertEqual(argumentos["dias"][0], date(2026, 10, 26))
        nombres = [f[0] for f in argumentos["filas"]]
        self.assertEqual(nombres, ["Lopez, Ana", "Perez, Luis"])
        self.assertEqual(argumentos["filas"][0][1], ["Mañana", "Libre", "Noche", "", "", "", ""])
        self.assertEqual(argumentos["filas"][1][1], ["Noche", "", "", "", "", "", ""])

    def test_filtrar_por_sucursal_deja_solo_su_gente(self):
        self.preparar(USUARIO_RRHH).get(f"{RUTA}?sucursal={SUC_B}")
        argumentos = self.espia_calendario.call_args.kwargs or dict(
            zip(("titulo", "periodo", "version", "estado", "publicada_en", "dias", "filas"), self.espia_calendario.call_args.args)
        )
        self.assertEqual([f[0] for f in argumentos["filas"]], ["Perez, Luis"])
        self.assertIn("Sucursal Sur", argumentos["titulo"])

    def test_sucursal_sin_colaboradores_da_404(self):
        otra = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
        self.assertEqual(self.preparar(USUARIO_RRHH).get(f"{RUTA}?sucursal={otra}").status_code, 404)

    def test_hoja_individual_lleva_turno_y_horario_de_cada_dia(self):
        r = self.preparar(USUARIO_RRHH).get(f"{RUTA}?colaborador={ANA}")
        self.assertEqual(r.data, b"%PDF-hoja")
        self.assertIn("hoja-2026-10-26-v2.pdf", r.headers["Content-Disposition"])
        argumentos = self.espia_hoja.call_args.args
        self.assertEqual(argumentos[0], "Lopez, Ana")
        self.assertEqual(argumentos[1], "Sucursal Norte")
        filas = argumentos[6]
        self.assertEqual(len(filas), 7)
        self.assertEqual(filas[0], (date(2026, 10, 26), "Mañana", "05:00 a 13:00"))
        self.assertEqual(filas[1], (date(2026, 10, 27), "Libre", ""))
        self.assertEqual(filas[2], (date(2026, 10, 28), "Noche", "21:00 a 05:00 (día siguiente)"))
        self.assertEqual(filas[3], (date(2026, 10, 29), "", ""))

    def test_colaborador_inexistente_da_404(self):
        otro = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
        self.assertEqual(self.preparar(USUARIO_RRHH).get(f"{RUTA}?colaborador={otro}").status_code, 404)

    def test_lee_todas_las_asignaciones_aunque_pasen_de_mil(self):
        celdas = [
            {"programacion_id": PROGRAMACION, "colaborador_id": ANA, "fecha": f"2026-10-{(n % 7) + 26:02d}", "turno_id": MANANA}
            for n in range(2500)
        ]
        leidas = calendarios.leer_asignaciones(FalsaBase(asignaciones=celdas), PROGRAMACION)
        self.assertEqual(len(leidas), 2500)

    def test_publicada_en_se_muestra_en_hora_de_guatemala(self):
        self.assertEqual(calendarios.fecha_publicacion("2026-10-20T14:15:00+00:00"), "20/10/2026 08:15")
        self.assertEqual(calendarios.fecha_publicacion("2026-10-20T03:00:00Z"), "19/10/2026 21:00")
        self.assertIsNone(calendarios.fecha_publicacion(None))


if __name__ == "__main__":
    unittest.main()
