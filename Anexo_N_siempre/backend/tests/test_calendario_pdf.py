"""pruebas de los calendarios en pdf"""

import os
import re
import sys
import unittest
from datetime import date, timedelta

from reportlab import rl_config

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calendario_pdf  # noqa: E402

DIAS_SEMANA = [date(2026, 10, 26) + timedelta(days=i) for i in range(7)]
DIAS_QUINCENA = [date(2026, 11, 16) + timedelta(days=i) for i in range(15)]


def paginas(pdf):
    return len(re.findall(rb"/Type /Page[^s]", pdf))


class SinCompresion(unittest.TestCase):
    """con la compresion apagada el texto del pdf se puede buscar en los bytes"""

    def setUp(self):
        anterior = rl_config.pageCompression
        rl_config.pageCompression = 0
        self.addCleanup(setattr, rl_config, "pageCompression", anterior)


class Calendario(SinCompresion):
    def generar(self, **cambios):
        datos = {
            "titulo": "Calendario de turnos: Sucursal Norte",
            "periodo": "Semanal del 26/10/2026 al 01/11/2026",
            "version": 1,
            "estado": "publicada",
            "publicada_en": "20/10/2026 08:15",
            "dias": DIAS_SEMANA,
            "filas": [("Lopez, Maria", ["Manana", "Tarde", "Libre", "", "Noche", "Libre", "Libre"])],
        }
        datos.update(cambios)
        return calendario_pdf.generar_calendario(**datos)

    def test_es_un_pdf_valido(self):
        pdf = self.generar()
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf[-32:])
        self.assertEqual(paginas(pdf), 1)

    def test_publicada_muestra_la_version_y_la_fecha(self):
        pdf = self.generar()
        self.assertIn(b"Versi", pdf)
        self.assertIn(b"Publicada el 20/10/2026 08:15", pdf)
        self.assertNotIn(b"BORRADOR", pdf)

    def test_borrador_se_marca_como_no_oficial(self):
        pdf = self.generar(estado="borrador", publicada_en=None)
        self.assertIn(b"BORRADOR", pdf)
        self.assertNotIn(b"Publicada el", pdf)

    def test_muchos_colaboradores_pasan_a_otra_pagina(self):
        filas = [(f"Persona {n}", ["Tarde"] * 15) for n in range(60)]
        pdf = self.generar(dias=DIAS_QUINCENA, filas=filas)
        self.assertGreaterEqual(paginas(pdf), 2)

    def test_la_leyenda_solo_incluye_los_turnos_usados(self):
        pdf = self.generar(filas=[("Lopez, Maria", ["Noche"] * 7)])
        self.assertIn(b"Noche", pdf)
        self.assertNotIn(b"Guardia", pdf)

    def test_nombres_con_simbolos_de_marcado_no_rompen_el_pdf(self):
        pdf = self.generar(filas=[("Perez & Hijos <b>x</b>", ["Tarde"] * 7)], titulo="Sucursal <A> & B")
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_un_turno_desconocido_no_rompe_el_pdf(self):
        pdf = self.generar(filas=[("Lopez, Maria", ["Turno nuevo"] * 7)])
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_sin_filas_genera_solo_el_encabezado(self):
        self.assertTrue(self.generar(filas=[]).startswith(b"%PDF-"))

    def test_sin_dias_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.generar(dias=[], filas=[])


class HojaIndividual(SinCompresion):
    def test_genera_una_pagina_con_los_datos_de_la_persona(self):
        filas = [(d, "Tarde", "13:00 a 21:00") for d in DIAS_SEMANA]
        pdf = calendario_pdf.generar_hoja_individual(
            "Lopez, Maria", "Sucursal Norte", "Semanal del 26/10/2026 al 01/11/2026", 2, "publicada", "20/10/2026 08:15", filas
        )
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(paginas(pdf), 1)
        self.assertIn(b"26/10/2026", pdf)
        self.assertIn(b"13:00 a 21:00", pdf)

    def test_dia_sin_asignar_se_rotula(self):
        pdf = calendario_pdf.generar_hoja_individual(
            "Lopez, Maria", "Sucursal Norte", "Semanal", 1, "borrador", None, [(DIAS_SEMANA[0], "", "")]
        )
        self.assertIn(b"Sin asignar", pdf)


if __name__ == "__main__":
    unittest.main()
