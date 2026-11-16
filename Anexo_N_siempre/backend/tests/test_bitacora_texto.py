"""pruebas del texto legible de la bitacora"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bitacora_texto import Contexto, describir, lineas  # noqa: E402

ANA = "11111111-1111-4111-8111-111111111111"
RELOJ = "22222222-2222-4222-8222-222222222222"
CASO = "33333333-3333-4333-8333-333333333333"
BORRADO = "44444444-4444-4444-8444-444444444444"


def fila(accion, tabla, detalle=None, registro=None):
    return {"accion": accion, "tabla": tabla, "detalle": detalle, "registro_id": registro}


CONTEXTO = Contexto(
    personas={ANA: "Ana Pérez"},
    relojes={RELOJ: "Reloj Sucursal Sur"},
    periodos={CASO: "del 01/10/2026 al 15/10/2026"},
    casos={CASO: {"persona": "Ana Pérez", "fecha": "2026-10-23", "tipo": "ausencia"}},
)


class TestDescribir(unittest.TestCase):
    def test_marcacion_manual_usa_el_nombre_y_la_hora_local(self):
        texto = describir(
            fila("agregar_marcacion", "marcaciones", {"colaborador_id": ANA, "tipo": "salida", "momento": "2026-10-21T11:06:00+00:00"}),
            CONTEXTO,
        )
        self.assertEqual(texto, "Agregó una marcación de salida a Ana Pérez (21/10/2026 05:06)")

    def test_horas_extra_dicen_de_quien_y_que_se_decidio(self):
        detalle = {"estado_nuevo": "autorizada", "pagados_nuevo": 105, "detectados": 105}
        texto = describir(fila("decidir", "horas_extra", detalle, CASO), CONTEXTO)
        self.assertIn("Ana Pérez del 23/10/2026: autorizada, 105 de 105 min", texto)

    def test_enlazar_nombra_a_la_persona_y_al_reloj(self):
        detalle = {"dispositivo_id": RELOJ, "id_en_dispositivo": "3"}
        texto = describir(fila("enlazar", "colaborador_dispositivo", detalle, ANA), CONTEXTO)
        self.assertEqual(texto, "Enlazó a Ana Pérez con el reloj «Reloj Sucursal Sur» (número 3)")

    def test_cierre_de_quincena(self):
        detalle = {"inicio": "2026-10-01", "fin": "2026-10-15", "boletas": 12, "neto_total": 15701.79}
        texto = describir(fila("cerrar", "periodos_planilla", detalle, CASO), CONTEXTO)
        self.assertEqual(texto, "Cerró la quincena del 01/10/2026 al 15/10/2026: 12 boletas, neto Q 15,701.79")

    def test_correccion_de_horas(self):
        detalle = {
            "colaborador_id": ANA,
            "fecha": "2026-10-12",
            "entrada_antes": "2026-10-12T16:30:00+00:00",
            "entrada_despues": "2026-10-12T14:00:00+00:00",
            "salida_antes": "2026-10-12T23:00:00+00:00",
            "salida_despues": None,
        }
        texto = describir(fila("corregir", "jornadas", detalle, CASO), CONTEXTO)
        self.assertEqual(texto, "Corrigió la jornada de Ana Pérez del 12/10/2026: entrada 10:30 a 08:00")

    def test_asistencia_registrada_en_una_ausencia(self):
        detalle = {
            "colaborador_id": ANA,
            "fecha": "2026-10-12",
            "entrada": "2026-10-12T14:00:00+00:00",
            "salida": "2026-10-12T23:00:00+00:00",
            "motivo": "Olvido marcar",
        }
        texto = describir(fila("registrar_asistencia", "ausencias", detalle, CASO), CONTEXTO)
        self.assertEqual(
            texto, "Registró la asistencia de Ana Pérez del 12/10/2026 (08:00 a 17:00) porque olvidó marcar"
        )

    def test_descuento_manual_con_su_nota(self):
        detalle = {"colaborador_id": ANA, "inicio": "2026-10-01", "fin": "2026-10-15", "monto": 50, "motivo": "Adelanto"}
        texto = describir(fila("crear", "descuentos_manuales", detalle, CASO), CONTEXTO)
        self.assertEqual(texto, "Descontó Q 50.00 a Ana Pérez en la quincena del 01/10/2026 al 15/10/2026: Adelanto")

    def test_registro_borrado_no_muestra_ids(self):
        texto = describir(fila("baja", "colaboradores", {"fecha": "2026-10-25"}, BORRADO), CONTEXTO)
        self.assertIn("(ya no existe)", texto)
        self.assertNotIn(BORRADO, texto)

    def test_accion_desconocida_no_falla(self):
        self.assertEqual(describir(fila("inventada", "tabla_rara"), CONTEXTO), "Inventada · tabla rara")


class TestLineas(unittest.TestCase):
    def test_cambia_ids_por_nombres_y_traduce_las_etiquetas(self):
        resultado = lineas({"colaborador_id": ANA, "dispositivo_id": RELOJ, "modalidad": "tiempo_completo"}, CONTEXTO)
        self.assertEqual(
            resultado,
            [("Colaborador", "Ana Pérez"), ("Reloj", "Reloj Sucursal Sur"), ("Modalidad", "Tiempo completo")],
        )

    def test_un_id_que_no_se_encuentra_no_se_muestra(self):
        self.assertEqual(lineas({"colaborador_id": BORRADO}, CONTEXTO), [("Colaborador", "(ya no existe)")])

    def test_omite_vacios_y_formatea_fechas_y_dinero(self):
        resultado = lineas({"motivo": None, "desde": "2026-10-24", "neto_total": 1200}, CONTEXTO)
        self.assertEqual(resultado, [("Desde", "24/10/2026"), ("Neto total", "Q 1,200.00")])

    def test_diurna_de_un_turno_no_dice_oficina(self):
        self.assertEqual(lineas({"tipo": "diurna"}, CONTEXTO), [("Tipo", "Diurna")])
        self.assertEqual(lineas({"modalidad": "diurna"}, CONTEXTO), [("Modalidad", "Diurna (oficina)")])


if __name__ == "__main__":
    unittest.main()
