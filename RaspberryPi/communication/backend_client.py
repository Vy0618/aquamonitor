"""Cliente do contrato HTTP entre a estação Raspberry Pi e o backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class BackendConfig:
    base_url: str
    detections_path: str
    timeout_seconds: float

    @property
    def detections_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.detections_path}"


class BackendClient:
    def __init__(self, config: BackendConfig) -> None:
        base_url = os.getenv("AQUADETECTOR_API_URL", config.base_url).rstrip("/")
        if "SEU_IP_DO_BACKEND" in base_url:
            raise RuntimeError("Defina AQUADETECTOR_API_URL com o IP do backend.")
        self.config = BackendConfig(base_url, config.detections_path, config.timeout_seconds)
        self.session = requests.Session()

    def ensure_station_is_available(self, station_id: int) -> None:
        try:
            response = self.session.get(f"{self.config.base_url}/api/stations", timeout=self.config.timeout_seconds)
            response.raise_for_status()
            stations = response.json()
        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(f"Não foi possível conectar ao backend em {self.config.base_url}: {error}") from error
        if not isinstance(stations, list) or not any(s.get("station_id") == station_id for s in stations):
            raise RuntimeError(f"A estação station_id={station_id} não existe no backend.")

    def send_detection(self, event: dict[str, Any]) -> None:
        try:
            response = self.session.post(self.config.detections_url, json=event, timeout=self.config.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as error:
            raise RuntimeError(f"Falha ao enviar detecção ao backend: {error}") from error
