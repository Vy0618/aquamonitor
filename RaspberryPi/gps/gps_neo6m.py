"""Leitura assíncrona de posição de um GPS u-blox NEO-6M via UART."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class GpsFix:
    latitude: float
    longitude: float
    received_at: str

    @property
    def geojson_coordinates(self) -> list[float]:
        """GeoJSON sempre usa a ordem longitude, latitude."""
        return [self.longitude, self.latitude]


class Neo6mGps:
    """Mantém a última posição válida emitida em sentenças NMEA RMC/GGA."""

    def __init__(self, port: str = "/dev/serial0", baudrate: int = 9600, timeout: float = 1.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._latest_fix: Optional[GpsFix] = None
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._serial = None

    @property
    def latest_fix(self) -> Optional[GpsFix]:
        with self._lock:
            return self._latest_fix

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def start(self) -> None:
        """Abre a UART e inicia a leitura sem bloquear o loop da câmera."""
        if self._thread is not None:
            return
        try:
            import serial
        except ImportError as error:
            raise RuntimeError("Instale pyserial: pip install -r requirements.txt") from error
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except serial.SerialException as error:
            raise RuntimeError(f"Não foi possível abrir o GPS em {self.port}: {error}") from error
        self._thread = threading.Thread(target=self._read_loop, name="neo6m-gps", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.timeout + 1)
        if self._serial is not None:
            self._serial.close()
        self._thread = None
        self._serial = None

    def _read_loop(self) -> None:
        while not self._stop_event.is_set() and self._serial is not None:
            try:
                raw = self._serial.readline().decode("ascii", errors="ignore").strip()
                fix = parse_nmea_sentence(raw)
                if fix is not None:
                    with self._lock:
                        self._latest_fix = fix
                        self._last_error = None
            except Exception as error:  # Erro transitório de UART não deve parar a câmera.
                with self._lock:
                    self._last_error = str(error)


def parse_nmea_sentence(sentence: str) -> Optional[GpsFix]:
    """Extrai uma posição de GPRMC/GNRMC ou GPGGA/GNGGA com fix válido."""
    fields = sentence.split("*")[0].split(",")
    if not fields or not fields[0].startswith("$"):
        return None
    message = fields[0][-3:]
    try:
        if message == "RMC":
            # $GPRMC,hhmmss.ss,A,llll.ll,a,yyyyy.yy,a,...
            if len(fields) < 7 or fields[2] != "A":
                return None
            latitude = _nmea_coordinate_to_decimal(fields[3], fields[4])
            longitude = _nmea_coordinate_to_decimal(fields[5], fields[6])
        elif message == "GGA":
            # $GPGGA,hhmmss.ss,llll.ll,a,yyyyy.yy,a,quality,...
            if len(fields) < 7 or fields[6] in {"", "0"}:
                return None
            latitude = _nmea_coordinate_to_decimal(fields[2], fields[3])
            longitude = _nmea_coordinate_to_decimal(fields[4], fields[5])
        else:
            return None
    except (ValueError, IndexError):
        return None
    return GpsFix(latitude, longitude, datetime.now(timezone.utc).isoformat())


def _nmea_coordinate_to_decimal(value: str, hemisphere: str) -> float:
    if not value or hemisphere not in {"N", "S", "E", "W"}:
        raise ValueError("coordenada NMEA inválida")
    degrees_length = 2 if hemisphere in {"N", "S"} else 3
    degrees = float(value[:degrees_length])
    minutes = float(value[degrees_length:])
    decimal = degrees + minutes / 60
    return -decimal if hemisphere in {"S", "W"} else decimal
