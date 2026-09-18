"""Atualiza station.json com a primeira posição válida recebida do NEO-6M."""

from __future__ import annotations

import time

from RaspberryPi.gps.gps_neo6m import Neo6mGps
from RaspberryPi.monitoring.monitor_residuos import BASE_DIR, CONFIG_FILE, load_config
from RaspberryPi.station.station_document import StationDocument


def main() -> None:
    config = load_config(CONFIG_FILE)
    gps_settings = config["gps"]
    if not gps_settings.get("enabled", False):
        raise RuntimeError("Ative gps.enabled em raspberrypi_config.json.")
    document_settings = config["station_document"]
    station = StationDocument(BASE_DIR / document_settings["path"], config["station_id"], document_settings)
    station.ensure_exists()
    gps = Neo6mGps(gps_settings["serial_port"], gps_settings["baudrate"], gps_settings["read_timeout_seconds"])
    gps.start()
    print("Aguardando um fix válido do NEO-6M. Pressione Ctrl+C para cancelar.")
    try:
        while gps.latest_fix is None:
            time.sleep(0.2)
        saved = station.update(gps_fix=gps.latest_fix, status="online")
        print(f"Posição atualizada: {saved['location']['coordinates']}")
    finally:
        gps.close()


if __name__ == "__main__":
    main()
