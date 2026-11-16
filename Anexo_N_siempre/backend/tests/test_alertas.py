"""pruebas del endpoint para resolver alertas"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alertas  # noqa: E402
import app as api  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

USUARIO_RRHH = {"id": "33333333-3333-4333-8333-333333333333", "nombre": "Ana RRHH", "rol": "rrhh"}
USUARIO_JEFE = {"id": "44444444-4444-4444-8444-444444444444", "nombre": "Don Carlos", "rol": "jefe"}
ALERTA = "99999999-9999-4999-8999-999999999999"
RUTA = f"/api/alertas/{ALERTA}/resolver"


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
        return SimpleNamespace(data=None)


class ResolverAlerta(unittest.TestCase):
    def preparar(self, usuario, base=None):
        self.base = base or FalsaBase()
        for parche in (
            patch("auth.usuario_actual", return_value=usuario),
            patch.object(alertas, "get_db", return_value=self.base),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        return api.app.test_client()

    def test_sin_sesion_da_401(self):
        self.assertEqual(self.preparar(None).post(RUTA).status_code, 401)

    def test_rrhh_y_jefe_pueden_resolver(self):
        for usuario in (USUARIO_RRHH, USUARIO_JEFE):
            r = self.preparar(usuario).post(RUTA)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(
                self.base.llamadas[0], ("resolver_alerta", {"p_alerta": ALERTA, "p_usuario": usuario["id"]})
            )

    def test_alerta_inexistente_da_404(self):
        error = APIError({"message": "x", "code": "P0002", "hint": None, "details": None})
        self.assertEqual(self.preparar(USUARIO_RRHH, FalsaBase(error)).post(RUTA).status_code, 404)

    def test_ruta_que_no_es_uuid_da_404(self):
        self.assertEqual(self.preparar(USUARIO_RRHH).post("/api/alertas/uno/resolver").status_code, 404)


if __name__ == "__main__":
    unittest.main()
