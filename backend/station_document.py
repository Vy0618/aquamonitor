"""Documento local da estação, sem dependências de API, GPS ou detecção.

Uso: python -m backend.station_document {init,show,update} CAMINHO
init recebe um documento JSON por stdin; update recebe os campos alterados.
Cada arquivo deve ter um único escritor. A gravação atômica protege os leitores,
mas não coordena atualizações concorrentes.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


FIELDS = {"_id", "station_id", "detections", "status", "location", "administrative"}
MUTABLE_FIELDS = FIELDS - {"_id", "station_id"}


def validate(document: Any) -> None:
    """Valida o formato local compatível com os documentos existentes."""
    if not isinstance(document, dict) or set(document) != FIELDS:
        raise ValueError("O documento deve conter exatamente: " + ", ".join(sorted(FIELDS)))
    identifier = document["_id"]
    if (
        not isinstance(identifier, dict)
        or set(identifier) != {"$oid"}
        or not isinstance(identifier["$oid"], str)
        or re.fullmatch(r"[0-9a-fA-F]{24}", identifier["$oid"]) is None
    ):
        raise ValueError("_id deve conter $oid com 24 dígitos hexadecimais.")
    if type(document["station_id"]) is not int or document["station_id"] <= 0:
        raise ValueError("station_id deve ser um inteiro positivo.")
    if type(document["detections"]) is not int or document["detections"] < 0:
        raise ValueError("detections deve ser um inteiro não negativo.")
    if document["status"] not in ("online", "offline"):
        raise ValueError("status deve ser online ou offline.")
    location = document["location"]
    if not isinstance(location, dict) or location.get("type") != "Point":
        raise ValueError("location deve ser um GeoJSON Point.")
    coordinates = location.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError("coordinates deve conter [longitude, latitude].")
    for value, limit in zip(coordinates, (180, 90)):
        if type(value) not in (int, float) or not -limit <= value <= limit or not math.isfinite(value):
            raise ValueError("Coordenadas inválidas: longitude entre -180 e 180, latitude entre -90 e 90.")
    administrative = document["administrative"]
    if not isinstance(administrative, dict) or set(administrative) != {"country", "state", "city", "district"}:
        raise ValueError("administrative deve conter country, state, city e district.")
    if any(not isinstance(value, str) or not value.strip() for value in administrative.values()):
        raise ValueError("Os campos administrativos devem ser textos não vazios.")


def read_document(path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(document)
    return document


def _write_document(path: Path, document: dict[str, Any], *, create: bool = False) -> None:
    validate(document)
    content = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if create:
            # Publica o arquivo completo sem sobrescrever um documento existente.
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_document(path: str | Path, document: dict[str, Any]) -> dict[str, Any]:
    """Cria o documento; nunca substitui um arquivo existente."""
    _write_document(Path(path), document, create=True)
    return document


def update_document(path: str | Path, changes: dict[str, Any]) -> dict[str, Any]:
    """Atualiza campos completos; preserva identidade e o maior total acumulado."""
    if not isinstance(changes, dict) or not changes or not set(changes) <= MUTABLE_FIELDS:
        raise ValueError("Informe um ou mais campos: " + ", ".join(sorted(MUTABLE_FIELDS)))
    document = read_document(path)
    updated = {**document, **changes}
    validate(updated)
    updated["detections"] = max(document["detections"], updated["detections"])
    _write_document(Path(path), updated)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "show", "update"))
    parser.add_argument("path", type=Path, help="Caminho do documento JSON local")
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            document = read_document(args.path)
        elif args.command == "init":
            document = create_document(args.path, json.load(sys.stdin))
        else:
            document = update_document(args.path, json.load(sys.stdin))
        print(json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(f"station_document: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
