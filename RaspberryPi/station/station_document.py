"""Persistência local do documento da estação no formato solicitado."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

class StationDocument:
    def __init__(self, path: Path, station_id: int, settings: dict[str, Any]) -> None:
        self.path = path
        self.station_id = station_id
        self.settings = settings

    def ensure_exists(self) -> dict[str, Any]:
        if self.path.is_file():
            return self._read()
        document = self._base_document()
        self._write(document)
        return document

    def update(self, detections: Optional[int] = None, status: Optional[str] = None) -> dict[str, Any]:
        document = self.ensure_exists()
        if detections is not None:
            # O contador inicial configurado nunca é reduzido por um arquivo local antigo.
            document["detections"] = max(int(document.get("detections", 0)), detections)
        if status is not None:
            document["status"] = status
        self._validate(document)
        self._write(document)
        return document

    def _base_document(self) -> dict[str, Any]:
        document = {
            "_id": self.settings["_id"],
            "station_id": self.station_id,
            "detections": self.settings["detections"],
            "status": self.settings["status"],
            "location": self.settings["location"],
            "administrative": self.settings["administrative"],
        }
        self._validate(document)
        return document

    def _read(self) -> dict[str, Any]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Documento da estação inválido em {self.path}: {error}") from error
        self._validate(document)
        return document

    def _write(self, document: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _validate(document: dict[str, Any]) -> None:
        required = {"_id", "station_id", "detections", "status", "location", "administrative"}
        if not isinstance(document, dict) or set(document) != required:
            raise RuntimeError("station.json deve conter exatamente os campos do documento da estação.")
        location = document["location"]
        coordinates = location.get("coordinates") if isinstance(location, dict) else None
        if not isinstance(location, dict) or location.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) != 2:
            raise RuntimeError("location deve ser um GeoJSON Point com [longitude, latitude].")
        if not all(isinstance(value, (int, float)) for value in coordinates):
            raise RuntimeError("As coordenadas devem ser numéricas.")
