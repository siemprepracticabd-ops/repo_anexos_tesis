"""pruebas de los puestos y los turnos administrables"""

import os
import sys
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import catalogos  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Jefe", "rol": "jefe"}
ID = "55555555-5555-4555-8555-555555555555"
NUEVO = "77777777-7777-4777-8777-777777777777"


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
        return SimpleNamespace(data=NUEVO)


def error_de_base(codigo, mensaje="mensaje de la base"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


class Base(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(catalogos, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class Puestos(Base):
    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post("/api/puestos", json={"nombre": "X"}).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post("/api/puestos", json={"nombre": "Supervisora"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_nombre_invalido_da_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        for malo in ("", "  ", "A", "x" * 61, None):
            self.assertEqual(cliente.post("/api/puestos", json={"nombre": malo}).status_code, 422, str(malo))
        self.assertEqual(self.base.llamadas, [])

    def test_crear_limpia_los_espacios_y_devuelve_201(self):
        r = self.preparar(USUARIO_RRHH).post("/api/puestos", json={"nombre": "  Encargada   de  facturas "})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json(), {"id": NUEVO})
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "crear_puesto")
        self.assertEqual(parametros, {"p_nombre": "Encargada de facturas", "p_usuario": USUARIO_RRHH["id"]})

    def test_renombrar_y_eliminar_llaman_a_la_base(self):
        cliente = self.preparar(USUARIO_RRHH)
        self.assertEqual(cliente.put(f"/api/puestos/{ID}", json={"nombre": "Supervisora"}).status_code, 200)
        self.assertEqual(cliente.delete(f"/api/puestos/{ID}").status_code, 200)
        self.assertEqual(self.base.llamadas[0][0], "renombrar_puesto")
        self.assertEqual(self.base.llamadas[0][1]["p_id"], ID)
        self.assertEqual(self.base.llamadas[1], ("eliminar_puesto", {"p_id": ID, "p_usuario": USUARIO_RRHH["id"]}))

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "23505": 409, "23503": 409, "22023": 422}
        for codigo, estado in esperados.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).delete(f"/api/puestos/{ID}")
            self.assertEqual(r.status_code, estado, codigo)

    def test_el_mensaje_de_puesto_en_uso_llega_a_la_pantalla(self):
        base = FalsaBase(error_de_base("23503", "No se puede eliminar: 2 colaborador(es) tienen este puesto"))
        r = self.preparar(USUARIO_RRHH, base).delete(f"/api/puestos/{ID}")
        self.assertIn("2 colaborador", r.get_json()["error"])


def turno(**cambios):
    base = {
        "nombre": "Administrativo",
        "hora_inicio": "07:00",
        "hora_fin": "17:00",
        "tipo_jornada": "diurna",
        "horas_ordinarias": 8,
    }
    base.update(cambios)
    return base


class Turnos(Base):
    def test_sin_sesion_y_jefe_no_pueden(self):
        self.assertEqual(self.preparar(None).post("/api/turnos", json=turno()).status_code, 401)
        r = self.preparar(USUARIO_JEFE).post("/api/turnos", json=turno())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.base.llamadas, [])

    def test_cuerpo_que_no_es_json_da_400(self):
        r = self.preparar(USUARIO_RRHH).post("/api/turnos", data="hola", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_datos_invalidos_dan_422(self):
        cliente = self.preparar(USUARIO_RRHH)
        malos = [
            turno(nombre=""),
            turno(nombre="x" * 61),
            turno(hora_inicio="25:00"),
            turno(hora_inicio="mañana"),
            turno(hora_fin=None),
            turno(tipo_jornada="rara"),
            turno(horas_ordinarias=0),
            turno(horas_ordinarias=25),
            turno(horas_ordinarias="mucho"),
            turno(horas_ordinarias="NaN"),
        ]
        for cuerpo in malos:
            self.assertEqual(cliente.post("/api/turnos", json=cuerpo).status_code, 422, cuerpo)
        self.assertEqual(self.base.llamadas, [])

    def test_crear_turno_manda_los_valores_limpios(self):
        r = self.preparar(USUARIO_RRHH).post(
            "/api/turnos", json=turno(nombre=" Sabado  oficina ", hora_fin="12:00:00", horas_ordinarias="5.5", p_usuario="otro")
        )
        self.assertEqual(r.status_code, 201)
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "crear_turno")
        self.assertEqual(parametros["p_nombre"], "Sabado oficina")
        self.assertEqual(parametros["p_inicio"], "07:00")
        self.assertEqual(parametros["p_fin"], "12:00")
        self.assertEqual(parametros["p_tipo"], "diurna")
        self.assertEqual(Decimal(parametros["p_horas"]), Decimal("5.5"))
        self.assertEqual(parametros["p_usuario"], USUARIO_RRHH["id"])

    def test_editar_manda_el_id(self):
        self.preparar(USUARIO_RRHH).put(f"/api/turnos/{ID}", json=turno())
        nombre, parametros = self.base.llamadas[0]
        self.assertEqual(nombre, "editar_turno")
        self.assertEqual(parametros["p_id"], ID)

    def test_activar_y_desactivar(self):
        cliente = self.preparar(USUARIO_RRHH)
        self.assertEqual(cliente.patch(f"/api/turnos/{ID}/estado", json={"activo": False}).status_code, 200)
        self.assertEqual(self.base.llamadas[0], ("cambiar_estado_turno", {"p_id": ID, "p_activo": False, "p_usuario": USUARIO_RRHH["id"]}))
        for malo in ({}, {"activo": "si"}, {"activo": None}):
            self.assertEqual(cliente.patch(f"/api/turnos/{ID}/estado", json=malo).status_code, 422, malo)

    def test_eliminar_llama_a_la_base(self):
        r = self.preparar(USUARIO_RRHH).delete(f"/api/turnos/{ID}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.base.llamadas[0], ("eliminar_turno", {"p_id": ID, "p_usuario": USUARIO_RRHH["id"]}))

    def test_errores_de_la_base_se_traducen(self):
        esperados = {"P0002": 404, "23505": 409, "55000": 409, "22023": 422, "23514": 422}
        for codigo, estado in esperados.items():
            r = self.preparar(USUARIO_RRHH, FalsaBase(error_de_base(codigo))).put(f"/api/turnos/{ID}", json=turno())
            self.assertEqual(r.status_code, estado, codigo)

    def test_el_mensaje_de_turno_usado_llega_a_la_pantalla(self):
        base = FalsaBase(error_de_base("55000", "Este turno ya se uso en una programacion: crea uno nuevo y desactiva este"))
        r = self.preparar(USUARIO_RRHH, base).put(f"/api/turnos/{ID}", json=turno())
        self.assertIn("desactiva", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
