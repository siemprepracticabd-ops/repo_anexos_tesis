"""pruebas del alta de relojes"""

import hashlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as api  # noqa: E402
import relojes  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
SUCURSAL = "55555555-5555-4555-8555-555555555555"
RELOJ = "66666666-6666-4666-8666-666666666666"


class FalsaBase:
    """responde por tabla y guarda lo que se inserto o actualizo"""

    def __init__(self, sucursales=None, fila=None, error=None):
        self.sucursales = [{"id": SUCURSAL}] if sucursales is None else sucursales
        self.fila = fila
        self.error = error
        self.escrituras = []
        self.tabla = None
        self.operacion = None

    def table(self, nombre):
        self.tabla = nombre
        self.operacion = "leer"
        return self

    def insert(self, valores):
        self.operacion = "insertar"
        self.escrituras.append((self.tabla, "insertar", valores))
        return self

    def update(self, valores):
        self.operacion = "actualizar"
        self.escrituras.append((self.tabla, "actualizar", valores))
        return self

    def __getattr__(self, nombre):
        return lambda *args, **kwargs: self

    def execute(self):
        if self.error and self.tabla == "dispositivos" and self.operacion == "insertar":
            raise self.error
        if self.tabla == "sucursales":
            if self.operacion == "insertar":
                return SimpleNamespace(data=[{"id": SUCURSAL}])
            return SimpleNamespace(data=self.sucursales)
        if self.tabla == "dispositivos":
            return SimpleNamespace(data=[self.fila] if self.fila else [])
        return SimpleNamespace(data=[{}])


def reloj(**cambios):
    return {"id": RELOJ, "serie": "ABC1234567", "activo": True, **cambios}


VALIDO = {"serie": "ABC1234567", "nombre": "Reloj Sucursal Norte", "modelo": "CLK-960", "sucursal_id": SUCURSAL}


class Base(unittest.TestCase):
    def preparar(self, usuario, base):
        self.base = base
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(relojes, "get_db", return_value=base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()


class TestRegistrar(Base):
    def test_el_jefe_registra_y_recibe_la_clave_una_vez(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(fila=reloj()))
        respuesta = cliente.post("/api/relojes", json=VALIDO)

        self.assertEqual(respuesta.status_code, 201)
        clave = respuesta.get_json()["api_key"]
        guardado = next(v for t, o, v in self.base.escrituras if t == "dispositivos")
        self.assertEqual(guardado["api_key_hash"], hashlib.sha256(clave.encode()).hexdigest())
        self.assertNotIn(clave, str(self.base.escrituras))

    def test_rrhh_no_puede_registrar(self):
        cliente = self.preparar(USUARIO_RRHH, FalsaBase())
        self.assertEqual(cliente.post("/api/relojes", json=VALIDO).status_code, 403)
        self.assertEqual(self.base.escrituras, [])

    def test_serie_invalida(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase())
        respuesta = cliente.post("/api/relojes", json={**VALIDO, "serie": "a b'; drop"})
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("serie", respuesta.get_json()["campos"])

    def test_nombre_y_sucursal_obligatorios(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase())
        respuesta = cliente.post("/api/relojes", json={"serie": "ABC1234567"})
        self.assertEqual(set(respuesta.get_json()["campos"]), {"nombre", "sucursal_id"})

    def test_sucursal_inexistente(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(sucursales=[]))
        respuesta = cliente.post("/api/relojes", json=VALIDO)
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("sucursal_id", respuesta.get_json()["campos"])

    def test_serie_repetida(self):
        duplicado = APIError({"message": "duplicate", "code": "23505", "hint": None, "details": None})
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(error=duplicado))
        respuesta = cliente.post("/api/relojes", json=VALIDO)
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("serie", respuesta.get_json()["campos"])


class TestSucursalNueva(Base):
    def test_crea_la_sucursal_si_no_existe(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(sucursales=[], fila=reloj()))
        datos = {k: v for k, v in VALIDO.items() if k != "sucursal_id"}
        respuesta = cliente.post("/api/relojes", json={**datos, "sucursal_nueva": "Oficina Central"})
        self.assertEqual(respuesta.status_code, 201)
        creada = [v for t, o, v in self.base.escrituras if t == "sucursales"]
        self.assertEqual(creada, [{"nombre": "Oficina Central"}])
        anotada = [v for t, o, v in self.base.escrituras if t == "bitacora" and v["tabla"] == "sucursales"]
        self.assertEqual(len(anotada), 1)

    def test_usa_la_que_ya_existe_con_ese_nombre(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(fila=reloj()))
        datos = {k: v for k, v in VALIDO.items() if k != "sucursal_id"}
        respuesta = cliente.post("/api/relojes", json={**datos, "sucursal_nueva": "sucursal norte"})
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual([v for t, o, v in self.base.escrituras if t == "sucursales"], [])

    def test_nombre_de_sucursal_muy_corto(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase())
        datos = {k: v for k, v in VALIDO.items() if k != "sucursal_id"}
        respuesta = cliente.post("/api/relojes", json={**datos, "sucursal_nueva": "A"})
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("sucursal_nueva", respuesta.get_json()["campos"])

    def test_sin_sucursal_ni_nombre(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase())
        datos = {k: v for k, v in VALIDO.items() if k != "sucursal_id"}
        respuesta = cliente.post("/api/relojes", json=datos)
        self.assertIn("sucursal_id", respuesta.get_json()["campos"])


class TestClaveYEstado(Base):
    def test_regenerar_clave(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(fila=reloj()))
        respuesta = cliente.post(f"/api/relojes/{RELOJ}/clave")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.get_json()["api_key"])

    def test_regenerar_reloj_inexistente(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase())
        self.assertEqual(cliente.post(f"/api/relojes/{RELOJ}/clave").status_code, 404)

    def test_desactivar(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(fila=reloj(activo=False)))
        respuesta = cliente.post(f"/api/relojes/{RELOJ}/estado", json={"activo": False})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.base.escrituras[0][2], {"activo": False})

    def test_estado_invalido(self):
        cliente = self.preparar(USUARIO_JEFE, FalsaBase(fila=reloj()))
        self.assertEqual(cliente.post(f"/api/relojes/{RELOJ}/estado", json={"activo": "si"}).status_code, 422)

    def test_rrhh_no_cambia_el_estado(self):
        cliente = self.preparar(USUARIO_RRHH, FalsaBase(fila=reloj()))
        self.assertEqual(cliente.post(f"/api/relojes/{RELOJ}/estado", json={"activo": False}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
