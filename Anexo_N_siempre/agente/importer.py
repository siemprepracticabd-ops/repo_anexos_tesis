import argparse
import json
import logging
import os
import socket
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from struct import pack, unpack

import requests
from zk import ZK, const
from zk.exception import ZKError, ZKErrorConnection, ZKNetworkError

def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(base_dir() / "agente.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
    ],
)
log = logging.getLogger("steren_importer")

PUNCH_MAP = {0: "entrada", 1: "salida", 2: "salida", 3: "entrada", 4: "entrada", 5: "salida"}
CHUNK_SIZE = 4096
BATCH_SIZE = 200
FULL_REREAD_SECONDS = 6 * 3600
FALLOS_PARA_BUSCAR = 3  # ciclos seguidos sin poder leer el reloj antes de buscarlo en la red
BUSQUEDA_CADA_SEGUNDOS = 600
estado_busqueda = {"fallos": 0, "ultima": 0.0}
RECORD_LAYOUTS = {
    22: "<H10sB4s5s",
    40: "<H24sB4sB8s",
    16: "<I4sBB2sI",
}


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def open_queue(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS marcaciones (
            id_en_lector TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            punch_code INTEGER,
            sent INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id_en_lector, fecha_hora)
        )
        """
    )
    conn.execute("CREATE TABLE IF NOT EXISTS estado (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS nombres "
        "(id_en_lector TEXT PRIMARY KEY, nombre TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0)"
    )
    conn.commit()
    return conn


def load_state(queue: sqlite3.Connection) -> dict:
    row = queue.execute("SELECT v FROM estado WHERE k = 'lectura'").fetchone()
    return json.loads(row[0]) if row else {}


def save_state(queue: sqlite3.Connection, state: dict) -> None:
    queue.execute("INSERT OR REPLACE INTO estado (k, v) VALUES ('lectura', ?)", (json.dumps(state),))
    queue.commit()


def prepare_attendance(conn) -> int:
    cmd = pack("<bhii", 1, const.CMD_ATTLOG_RRQ, 0, 0)
    resp = conn._ZK__send_command(1503, cmd, 1024)
    if not resp.get("status"):
        raise ZKErrorConnection("El checador no soporta lectura de marcaciones")
    return unpack("I", conn._ZK__data[1:5])[0]


def read_buffer_range(conn, start: int, end: int) -> bytes:
    chunks = []
    while start < end:
        size = min(CHUNK_SIZE, end - start)
        chunks.append(conn._ZK__read_chunk(start, size))
        start += size
    return b"".join(chunks)


def parse_attendance(conn, body: bytes, tz: timezone, record_size: int = 0) -> tuple:
    record_size = record_size or next((s for s in RECORD_LAYOUTS if len(body) % s == 0), None)
    if record_size is None or len(body) % record_size:
        raise ValueError(f"Formato de marcaciones desconocido ({len(body)} bytes)")

    fmt = RECORD_LAYOUTS[record_size]
    out = []
    for i in range(0, len(body), record_size):
        fields = unpack(fmt, body[i:i + record_size])
        if record_size == 16:
            user_id, ts, punch = str(fields[0]), fields[1], fields[3]
        elif record_size == 22:
            user_id, ts, punch = fields[1].split(b"\x00")[0].decode(errors="ignore"), fields[3], fields[4][0]
        else:
            user_id, ts, punch = fields[1].split(b"\x00")[0].decode(errors="ignore"), fields[3], fields[4]
        try:
            moment = conn._ZK__decode_time(ts).replace(tzinfo=tz)
        except ValueError:
            continue
        out.append((user_id, moment.isoformat(), int(punch)))
    return out, record_size


def read_serial(device_cfg: dict) -> str:
    zk = ZK(
        device_cfg["ip"],
        port=device_cfg.get("port", 4370),
        password=device_cfg.get("password", 0),
        timeout=device_cfg.get("timeout", 15),
        ommit_ping=True,
    )
    conn = zk.connect()
    try:
        return conn.get_serialnumber()
    finally:
        conn.disconnect()


def local_ips() -> list:
    ips = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no envia nada, solo elige la interfaz de salida
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def port_open(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_port(own_ips: list, port: int, timeout: float = 1.0) -> list:
    """equipos con el puerto abierto en el /24 de cada ip de esta pc"""
    hosts = []
    for own in own_ips:
        prefix = own.rsplit(".", 1)[0]
        hosts += [f"{prefix}.{n}" for n in range(1, 255) if f"{prefix}.{n}" != own]
    hosts = list(dict.fromkeys(hosts))
    with ThreadPoolExecutor(max_workers=64) as pool:
        abiertos = list(pool.map(lambda h: port_open(h, port, timeout), hosts))
    return [h for h, abierto in zip(hosts, abiertos) if abierto]


def serial_at(ip: str, device_cfg: dict, attempts: int = 2):
    zk = ZK(
        ip,
        port=device_cfg.get("port", 4370),
        password=device_cfg.get("password", 0),
        timeout=5,
        ommit_ping=True,
    )
    for _ in range(attempts):
        try:
            conn = zk.connect()
        except (ZKError, OSError):
            continue
        try:
            return conn.get_serialnumber()
        except (ZKError, OSError):
            continue
        finally:
            try:
                conn.disconnect()
            except (ZKError, OSError):
                pass
    return None


def find_reader(config: dict) -> str:
    """ip del reloj cuya serie coincide con la del config, o vacio si no aparece"""
    device = config["device"]
    for ip in scan_port(local_ips(), device.get("port", 4370)):
        if serial_at(ip, device) == config["lector_serie"]:
            return ip
    return ""


def save_ip(config_path: str, new_ip: str) -> None:
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    data["device"]["ip"] = new_ip
    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, config_path)


def relocate_reader(config: dict, config_path: str) -> None:
    old_ip = config["device"]["ip"]
    log.info("Buscando el reloj %s en la red (no responde en %s)", config["lector_serie"], old_ip)
    new_ip = find_reader(config)
    if not new_ip:
        log.warning("El reloj %s no aparece en la red de esta PC", config["lector_serie"])
        return
    if new_ip != old_ip:
        config["device"]["ip"] = new_ip
        save_ip(config_path, new_ip)
        log.info("El reloj cambió de IP: %s -> %s (guardada en config.json)", old_ip, new_ip)


def recent_only(records: list, ignore_before: str) -> list:
    cutoff = datetime.fromisoformat(ignore_before) if ignore_before else None
    return [r for r in records if cutoff is None or datetime.fromisoformat(r[1]) >= cutoff]


def read_user_names(conn, wanted_ids: set) -> dict:
    cmd = pack("<bhii", 1, const.CMD_USERTEMP_RRQ, const.FCT_USER, 0)
    resp = conn._ZK__send_command(1503, cmd, 1024)
    if not resp.get("status"):
        return {}
    total = unpack("I", conn._ZK__data[1:5])[0]
    body = read_buffer_range(conn, 0, total)[4:]
    conn.free_data()

    names = {}
    for i in range(0, len(body) - 71, 72):
        fields = unpack("<HB8s24sIx7sx24s", body[i:i + 72])
        user_id = fields[6].split(b"\x00")[0].decode(errors="ignore")
        name = fields[3].split(b"\x00")[0].decode("latin-1").strip(" ,")
        if user_id in wanted_ids and name:
            names[user_id] = name
    return names


def fetch_from_device(
    device_cfg: dict, expected_serial: str, tz: timezone, state: dict, ignore_before: str = ""
) -> tuple:
    zk = ZK(
        device_cfg["ip"],
        port=device_cfg.get("port", 4370),
        password=device_cfg.get("password", 0),
        timeout=device_cfg.get("timeout", 15),
        force_udp=False,
        ommit_ping=True,
    )
    conn = zk.connect()
    try:
        conn.enable_device()
        serial = conn.get_serialnumber()
        if serial != expected_serial:
            raise ValueError(f"El reloj es {serial}, pero el config espera {expected_serial}")
        total = prepare_attendance(conn)
        known_total = state.get("total", 0)
        record_size = state.get("record_size", 0)
        full_due = time.time() - state.get("last_full", 0) > FULL_REREAD_SECONDS
        incremental = (
            known_total and record_size and not full_due
            and total >= known_total and (total - known_total) % record_size == 0
        )

        if incremental and total == known_total:
            conn.free_data()
            return [], {}, state

        if incremental:
            records, _ = parse_attendance(conn, read_buffer_range(conn, known_total, total), tz, record_size)
            new_state = {**state, "total": total}
        else:
            raw = read_buffer_range(conn, 0, total)
            records, record_size = parse_attendance(conn, raw[4:], tz)
            new_state = {"total": total, "record_size": record_size, "last_full": time.time()}
        conn.free_data()

        wanted = {r[0] for r in recent_only(records, ignore_before)}
        names = read_user_names(conn, wanted) if wanted else {}
        return records, names, new_state
    finally:
        conn.disconnect()


def store_new_records(queue: sqlite3.Connection, records: list, ignore_before: str) -> int:
    fresh = recent_only(records, ignore_before)
    before = queue.total_changes
    queue.executemany(
        "INSERT OR IGNORE INTO marcaciones (id_en_lector, fecha_hora, punch_code) VALUES (?, ?, ?)",
        fresh,
    )
    queue.commit()
    return queue.total_changes - before


def store_names(queue: sqlite3.Connection, names: dict) -> None:
    for user_id, name in names.items():
        queue.execute(
            """
            INSERT INTO nombres (id_en_lector, nombre, sent) VALUES (?, ?, 0)
            ON CONFLICT(id_en_lector) DO UPDATE SET
                sent = CASE WHEN nombres.nombre = excluded.nombre THEN nombres.sent ELSE 0 END,
                nombre = excluded.nombre
            """,
            (user_id, name),
        )
    queue.commit()


def send_pending(queue: sqlite3.Connection, api_cfg: dict, serial: str) -> tuple:
    pending = queue.execute(
        "SELECT id_en_lector, fecha_hora, punch_code FROM marcaciones WHERE sent = 0 ORDER BY fecha_hora"
    ).fetchall()

    names = queue.execute("SELECT id_en_lector, nombre FROM nombres WHERE sent = 0").fetchall()

    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    if not batches and names:
        batches = [[]]

    sent_count = 0
    for position, batch in enumerate(batches):
        payload = {
            "lector_serie": serial,
            "marcaciones": [
                {
                    "id_en_lector": uid,
                    "fecha_hora": ts,
                    "tipo": PUNCH_MAP.get(punch, "desconocido"),
                    "codigo_punch": punch,
                }
                for uid, ts, punch in batch
            ],
        }
        if position == 0 and names:
            payload["usuarios"] = [{"id_en_lector": uid, "nombre": nombre} for uid, nombre in names]
        try:
            resp = requests.post(
                api_cfg["url"],
                json=payload,
                headers={"X-API-Key": api_cfg["api_key"]},
                timeout=30,
            )
        except requests.RequestException as exc:
            log.warning("Sin conexión a la API, se reintentará después: %s", exc)
            break

        if resp.status_code != 200:
            log.warning("La API rechazó el lote (%s): %s", resp.status_code, resp.text[:200])
            break

        queue.executemany(
            "UPDATE marcaciones SET sent = 1 WHERE id_en_lector = ? AND fecha_hora = ?",
            [(uid, ts) for uid, ts, _ in batch],
        )
        if position == 0 and names:
            queue.executemany("UPDATE nombres SET sent = 1 WHERE id_en_lector = ?", [(uid,) for uid, _ in names])
        queue.commit()
        sent_count += len(batch)
        rejected = resp.json().get("rechazadas", 0)
        if rejected:
            log.warning("La API descartó %d marcaciones mal formadas de este lote", rejected)

    return sent_count, len(pending) - sent_count


def run_once(config: dict, config_path: str = "") -> None:
    tz = timezone(timedelta(hours=config.get("utc_offset_horas", -6)))
    queue = open_queue(str(base_dir() / config["queue_db"]))
    try:
        try:
            ignore_before = config.get("ignorar_antes_de", "")
            records, names, new_state = fetch_from_device(
                config["device"], config["lector_serie"], tz, load_state(queue), ignore_before
            )
            new_count = store_new_records(queue, records, ignore_before)
            store_names(queue, names)
            save_state(queue, new_state)
            estado_busqueda["fallos"] = 0
            log.info("Leídas %d marcaciones del checador (%d nuevas en la cola)", len(records), new_count)
        except (ZKError, OSError, ValueError) as exc:
            log.warning("No se pudo leer el checador: %s", exc)
            estado_busqueda["fallos"] += 1
            toca = time.time() - estado_busqueda["ultima"] > BUSQUEDA_CADA_SEGUNDOS
            if config_path and estado_busqueda["fallos"] >= FALLOS_PARA_BUSCAR and toca:
                estado_busqueda["ultima"] = time.time()
                relocate_reader(config, config_path)

        sent, still_pending = send_pending(queue, config["api"], config["lector_serie"])
        log.info("Enviadas %d marcaciones, %d pendientes en cola", sent, still_pending)
    finally:
        queue.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente Steren CLK-960 -> API de asistencia")
    parser.add_argument(
        "--config", default=str(base_dir() / "config.json"), help="Ruta al archivo de configuración"
    )
    parser.add_argument("--loop", action="store_true", help="Ejecutar continuamente")
    parser.add_argument("--serie", action="store_true", help="Mostrar el número de serie del reloj y salir")
    args = parser.parse_args()

    if not Path(args.config).exists():
        log.error("No existe %s. Copia config.example.json a config.json y ajusta los valores.", args.config)
        sys.exit(1)

    config = load_config(args.config)

    if args.serie:
        try:
            print("Número de serie del reloj:", read_serial(config["device"]))
        except (ZKErrorConnection, ZKNetworkError, OSError) as exc:
            log.error("No se pudo conectar al reloj en %s: %s", config["device"].get("ip"), exc)
            sys.exit(1)
        return

    if args.loop:
        interval = config.get("poll_interval_seconds", 300)
        while True:
            try:
                run_once(config, args.config)
            except Exception:
                log.exception("Error inesperado; se reintenta en el próximo ciclo")
            time.sleep(interval)
    else:
        run_once(config, args.config)


if __name__ == "__main__":
    main()
