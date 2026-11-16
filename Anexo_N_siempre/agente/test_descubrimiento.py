import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import importer


def config_base(ip="10.0.0.2"):
    return {
        "lector_serie": "ESU1",
        "device": {"ip": ip, "port": 4370, "password": 0, "timeout": 15},
        "api": {"url": "http://x", "api_key": "k"},
        "queue_db": "queue.sqlite3",
    }


class ScanPortTest(unittest.TestCase):
    def test_encuentra_el_equipo_con_el_puerto_abierto(self):
        servidor = socket.socket()
        servidor.bind(("127.0.0.1", 0))
        servidor.listen()
        puerto = servidor.getsockname()[1]
        try:
            self.assertEqual(importer.scan_port(["127.0.0.9"], puerto, timeout=0.5), ["127.0.0.1"])
        finally:
            servidor.close()

    def test_sin_puerto_abierto_devuelve_vacio(self):
        libre = socket.socket()
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
        libre.close()
        self.assertEqual(importer.scan_port(["127.0.0.9"], puerto, timeout=0.5), [])


class FindReaderTest(unittest.TestCase):
    def test_elige_el_de_la_serie_correcta(self):
        series = {"10.0.0.5": "OTRO", "10.0.0.7": "ESU1"}
        with mock.patch.object(importer, "local_ips", return_value=["10.0.0.3"]), \
                mock.patch.object(importer, "scan_port", return_value=["10.0.0.5", "10.0.0.7"]), \
                mock.patch.object(importer, "serial_at", side_effect=lambda ip, cfg: series[ip]):
            self.assertEqual(importer.find_reader(config_base()), "10.0.0.7")

    def test_si_ninguno_coincide_devuelve_vacio(self):
        with mock.patch.object(importer, "local_ips", return_value=["10.0.0.3"]), \
                mock.patch.object(importer, "scan_port", return_value=["10.0.0.5"]), \
                mock.patch.object(importer, "serial_at", return_value="OTRO"):
            self.assertEqual(importer.find_reader(config_base()), "")


class RunOnceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.ruta = str(self.dir / "config.json")
        self.config = config_base()
        Path(self.ruta).write_text(json.dumps(self.config), encoding="utf-8")
        importer.estado_busqueda.update({"fallos": 0, "ultima": 0.0})
        self.parches = [
            mock.patch.object(importer, "base_dir", return_value=self.dir),
            mock.patch.object(importer, "send_pending", return_value=(0, 0)),
            mock.patch.object(importer, "fetch_from_device", side_effect=OSError("timed out")),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        mock.patch.stopall()
        self.tmp.cleanup()

    def test_busca_solo_despues_de_varios_fallos_y_guarda_la_ip(self):
        with mock.patch.object(importer, "find_reader", return_value="10.0.0.9") as buscar:
            importer.run_once(self.config, self.ruta)
            importer.run_once(self.config, self.ruta)
            buscar.assert_not_called()
            importer.run_once(self.config, self.ruta)
            buscar.assert_called_once()
        self.assertEqual(self.config["device"]["ip"], "10.0.0.9")
        guardado = json.loads(Path(self.ruta).read_text(encoding="utf-8"))
        self.assertEqual(guardado["device"]["ip"], "10.0.0.9")
        self.assertEqual(guardado["api"]["api_key"], "k")

    def test_no_busca_en_cada_ciclo(self):
        with mock.patch.object(importer, "find_reader", return_value="") as buscar:
            for _ in range(6):
                importer.run_once(self.config, self.ruta)
            buscar.assert_called_once()

    def test_sin_ruta_de_config_no_busca(self):
        with mock.patch.object(importer, "find_reader") as buscar:
            for _ in range(4):
                importer.run_once(self.config)
            buscar.assert_not_called()

    def test_una_lectura_buena_reinicia_el_conteo(self):
        importer.estado_busqueda["fallos"] = 2
        with mock.patch.object(importer, "fetch_from_device", return_value=([], {}, {})):
            importer.run_once(self.config, self.ruta)
        self.assertEqual(importer.estado_busqueda["fallos"], 0)

    def test_un_error_del_protocolo_del_reloj_no_corta_el_envio(self):
        from zk.exception import ZKErrorResponse
        with mock.patch.object(importer, "fetch_from_device", side_effect=ZKErrorResponse("Can't read serial number")), \
                mock.patch.object(importer, "send_pending", return_value=(0, 0)) as enviar:
            importer.run_once(self.config, self.ruta)
            enviar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
