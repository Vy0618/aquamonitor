"""Cria cinco estações sintéticas na Baía de Santos pela API local.

Uso: python scripts/populate_santos.py
Cada execução cria novos IDs e grava entre 1 e 200 eventos por estação.
"""

import json
import random
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
# Pontos aproximados na água, de oeste para leste; não são instalações reais.
POINTS = [
    (-46.385, -23.995),
    (-46.370, -24.005),
    (-46.350, -24.008),
    (-46.330, -24.005),
    (-46.315, -23.998),
]


def request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(BASE_URL + path, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def main():
    existing_ids = {station["station_id"] for station in request("GET", "/api/stations")}
    results = []
    for index, coordinates in enumerate(POINTS, start=1):
        # IDs grandes aleatórios evitam reutilizar IDs sequenciais antigos/inativos.
        station_id = random.SystemRandom().randint(1_000_000_000, 2_000_000_000)
        while station_id in existing_ids:
            station_id = random.SystemRandom().randint(1_000_000_000, 2_000_000_000)
        existing_ids.add(station_id)
        count = random.randint(1, 200)
        request("POST", "/api/stations", {
            "station_id": station_id,
            "location": {"type": "Point", "coordinates": list(coordinates)},
            "administrative": {
                "country": "Brazil", "state": "São Paulo", "city": "Santos",
                "district": f"Baía de Santos - teste {index}",
            },
        })
        print(f"Estação {station_id} criada; enviando {count} eventos.", flush=True)
        for track_id in range(1, count + 1):
            request("POST", "/api/detections", {
                "event_id": f"santos-demo-{uuid.uuid4()}",
                "station_id": station_id,
                "detection_type": "bottle",
                "confidence": round(random.uniform(0.75, 0.99), 4),
                "track_id": track_id,
                "direction": random.choice(["positive", "negative"]),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })
        summary = request("GET", f"/api/stations/{station_id}/detections")
        if summary["total"] != count:
            raise RuntimeError(f"Total inesperado na estação {station_id}: {summary}")
        results.append({"station_id": station_id, "coordinates": coordinates,
                        "detections": count})
        print(f"Confirmado: {station_id} com {count} detecções.", flush=True)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Total: {sum(item['detections'] for item in results)} detecções em 5 estações.")


if __name__ == "__main__":
    main()
