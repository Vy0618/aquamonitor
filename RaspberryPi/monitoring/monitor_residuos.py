"""Conta resíduos na câmera e envia cada cruzamento ao backend AquaDetector."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from RaspberryPi.camera.webcam_config import WebcamConfig
from RaspberryPi.communication.backend_client import BackendClient, BackendConfig
from RaspberryPi.detection.yolo_detector import EXPECTED_CLASSES, YoloDetector
from RaspberryPi.tracking.line_tracker import LineTracker

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_FILE = BASE_DIR / "config" / "raspberrypi_config.json"
COUNTS_FILE = BASE_DIR / "data" / "contagem_residuos.json"
LINE_Y_RATIO = 0.55
TRACKING_DIRECTION = "both"


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Configuração inválida em {path}: {error}") from error
    types = config.get("detection", {}).get("detection_types")
    if not isinstance(config.get("station_id"), int) or config["station_id"] <= 0:
        raise RuntimeError("station_id deve ser um inteiro positivo.")
    if not isinstance(types, list) or set(types) != set(EXPECTED_CLASSES):
        raise RuntimeError(f"detection.detection_types deve conter: {', '.join(EXPECTED_CLASSES)}")
    return config


def load_counts(path: Path) -> dict[str, int]:
    counts = {class_name: 0 for class_name in EXPECTED_CLASSES}
    if path.is_file():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            saved_counts = saved.get("counts", saved)  # Compatível com o formato local anterior.
            for class_name in counts:
                if isinstance(saved_counts.get(class_name), int):
                    counts[class_name] = saved_counts[class_name]
        except (json.JSONDecodeError, OSError):
            print("Aviso: JSON anterior inválido; iniciando uma nova contagem.")
    return counts


def save_counts(path: Path, station_id: int, counts: dict[str, int]) -> None:
    document = {
        "station_id": station_id,
        "counts": counts,
        "detection_types": list(EXPECTED_CLASSES),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def draw_overlay(frame, detections, tracker: LineTracker, counts: dict[str, int]) -> None:
    _, width = frame.shape[:2]
    cv2.line(frame, (0, tracker.line_y), (width, tracker.line_y), (0, 255, 255), 2)
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(frame, f"{detection.class_name} {detection.confidence:.0%}", (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2)
    for row, class_name in enumerate(EXPECTED_CLASSES, start=1):
        cv2.putText(frame, f"{class_name}: {counts[class_name]}", (12, row * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def main() -> None:
    config = load_config()
    station_id = config["station_id"]
    backend_settings = config["backend"]
    client = BackendClient(BackendConfig(**{
        "base_url": backend_settings["base_url"],
        "detections_path": backend_settings["detections_path"],
        "timeout_seconds": backend_settings["timeout_seconds"],
    }))
    if backend_settings.get("require_connection_on_startup", True):
        client.ensure_station_is_available(station_id)
        print(f"Backend conectado; estação {station_id} validada.")

    camera_config = WebcamConfig(**config["camera"])
    detection_config = config["detection"]
    detector = YoloDetector(
        model_path=BASE_DIR / detection_config["model_path"],
        confidence_threshold=detection_config["confidence_threshold"],
        image_size=detection_config["image_size"],
        allowed_classes=tuple(detection_config["detection_types"]),
    )
    camera = camera_config.open_camera()
    counts = load_counts(COUNTS_FILE)
    tracker = LineTracker(line_y=int(camera_config.height * LINE_Y_RATIO), direction=TRACKING_DIRECTION)
    print("Monitor iniciado. Pressione Q ou ESC para encerrar.")
    try:
        while True:
            success, frame = camera.read()
            if not success:
                raise RuntimeError("Não foi possível ler um frame da câmera.")
            detections = detector.detect(frame)
            detections_by_class = {d.class_name: d for d in detections}
            for crossing in tracker.update(detections):
                counts[crossing.class_name] += 1
                save_counts(COUNTS_FILE, station_id, counts)
                detection = detections_by_class.get(crossing.class_name)
                client.send_detection({
                    "event_id": str(uuid.uuid4()),
                    "station_id": station_id,
                    "detection_type": crossing.class_name,
                    "confidence": detection.confidence if detection else 0.0,
                    "track_id": crossing.track_id,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
                print(f"Enviado: {crossing.class_name} (track #{crossing.track_id})")
            draw_overlay(frame, detections, tracker, counts)
            cv2.imshow("Monitoramento de residuos", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        save_counts(COUNTS_FILE, station_id, counts)
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
