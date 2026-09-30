"""Captura, detecção periódica, contagem por linha e publicação HTTP."""

from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

import cv2

from backend.camera.webcam_config import LatestFrameCamera, WebcamConfig
from backend.communication.backend_client import BackendClient, BackendConfig
from backend.detection.yolo_detector import EXPECTED_CLASSES, YoloDetector
from backend.station.station_document import StationDocument
from backend.tracking.line_tracker import LineTracker

BASE_DIR = Path(__file__).resolve().parents[1]
from backend.settings import CONFIG_FILE, load_config
COUNTS_FILE = BASE_DIR / "data" / "contagem_residuos.json"



def load_counts(path: Path) -> dict[str, int]:
    counts = dict.fromkeys(EXPECTED_CLASSES, 0)
    if not path.exists():
        return counts
    try:
        saved = json.loads(path.read_text(encoding="utf-8-sig"))
        saved_counts = saved.get("counts", saved)
        for name in counts:
            value = saved_counts.get(name, 0)
            if type(value) is not int or value < 0:
                raise ValueError(f"Contagem inválida para {name}.")
            counts[name] = value
    except (OSError, ValueError, AttributeError) as error:
        # Não sobrescreve silenciosamente dados que precisam ser recuperados.
        raise RuntimeError(f"Contagens inválidas em {path}: {error}") from error
    return counts


def save_counts(path: Path, station_id: int, counts: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "station_id": station_id,
        "counts": counts,
        "detection_types": list(EXPECTED_CLASSES),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def tracker_for_frame(frame, settings: dict) -> LineTracker:
    height = frame.shape[0]
    return LineTracker(
        line_y=min(height - 1, max(0, int(height * settings.get("line_y_ratio", 0.55)))),
        direction=settings.get("direction", "both"),
        max_distance=settings.get("max_distance", 90),
        max_missing_frames=settings.get("max_missing_frames", 4),
    )


def draw_overlay(frame, detections, tracker: LineTracker, counts: dict[str, int]) -> None:
    height, width = frame.shape[:2]
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 1)
        cv2.putText(frame, f"{detection.class_name} {detection.confidence:.0%}",
                    (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 0), 1)
    # Desenha por último, com contorno, para ser visível mesmo sobre objetos.
    line_y = min(height - 1, max(0, tracker.line_y))
    for color, thickness in (((0, 0, 0), 5), ((0, 255, 255), 2)):
        cv2.line(frame, (0, line_y), (width - 1, line_y), color, thickness)
    for row, name in enumerate(EXPECTED_CLASSES, start=1):
        cv2.putText(frame, f"{name}: {counts[name]}", (8, row * 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def create_detector(config: dict, name: str):
    if name == "yolo":
        settings = config["detection"]
        return YoloDetector(
            model_path=BASE_DIR / settings["model_path"],
            confidence_threshold=settings["confidence_threshold"],
            image_size=settings["image_size"],
            device="cpu",
            allowed_classes=tuple(settings["detection_types"]),
        )
    from backend.detection.ssd_mobilenet_detector import SsdMobileNetDetector
    settings = config["ssd_mobilenet"]
    return SsdMobileNetDetector(
        model_path=BASE_DIR / settings["model_path"],
        config_path=BASE_DIR / settings["config_path"],
        labels_path=BASE_DIR / settings["labels_path"],
        confidence_threshold=settings["confidence_threshold"],
        input_width=settings["input_width"], input_height=settings["input_height"],
        allowed_classes=settings["detection_types"],
    )


def run(config: dict, detector_name: str, display: bool = True) -> None:
    station_id = config["station_id"]
    counts = load_counts(COUNTS_FILE)
    detector = create_detector(config, detector_name)
    settings = config["backend"]
    interval = config.get("detection_interval_ms", 250) / 1000
    tracking_settings = config.get("tracking", {})
    station_settings = config["station_document"]
    station = StationDocument(BASE_DIR / station_settings["path"], station_id, station_settings)
    window = "AquaMonitor - " + detector_name.upper()
    with ExitStack() as resources:
        client = BackendClient(BackendConfig(settings["base_url"], settings["detections_path"], settings["timeout_seconds"]))
        resources.callback(client.close)
        if settings.get("require_connection_on_startup", True):
            client.ensure_station_is_available(station_id)
        camera = LatestFrameCamera(WebcamConfig(**config["camera"]).open_camera())
        resources.callback(camera.close)
        if display:
            resources.callback(cv2.destroyAllWindows)
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        station.update(detections=sum(counts.values()), status="online")
        resources.callback(lambda: station.update(detections=sum(counts.values()), status="offline"))
        resources.callback(lambda: save_counts(COUNTS_FILE, station_id, counts))
        sender = resources.enter_context(ThreadPoolExecutor(max_workers=1, thread_name_prefix="http"))
        pending = deque()
        tracker = None
        frame_shape = None
        next_detection = 0.0
        detections = []
        print(f"Monitor {detector_name.upper()} iniciado; intervalo mínimo {interval * 1000:g} ms. Q/ESC ou Ctrl+C para sair.")
        try:
            while True:
                while pending and pending[0].done():
                    pending.popleft().result()
                frame = camera.read()
                if frame.shape[:2] != frame_shape:
                    frame_shape = frame.shape[:2]
                    tracker = tracker_for_frame(frame, tracking_settings)
                    detections = []
                    next_detection = 0.0
                    print(f"Frame recebido: {frame.shape[1]}x{frame.shape[0]}; linha em y={tracker.line_y}.")
                now = time.monotonic()
                if now >= next_detection:
                    next_detection = now + interval
                    detections = detector.detect(frame)
                    crossings = tracker.update(detections)
                    for crossing in crossings:
                        counts[crossing.class_name] += 1
                    if crossings:
                        save_counts(COUNTS_FILE, station_id, counts)
                        station.update(detections=sum(counts.values()))
                    for crossing in crossings:
                        if len(pending) >= 32:
                            raise RuntimeError("Backend lento: limite de 32 envios pendentes atingido. Verifique a conexão.")
                        event = {
                            "event_id": str(uuid.uuid4()), "station_id": station_id,
                            "detection_type": crossing.class_name, "confidence": crossing.confidence,
                            "track_id": crossing.track_id,
                            "detected_at": datetime.now(timezone.utc).isoformat(),
                        }
                        pending.append(sender.submit(client.send_detection, event))
                        print(f"Contado: {crossing.class_name} (track #{crossing.track_id})")
                if display:
                    draw_overlay(frame, detections, tracker, counts)
                    cv2.imshow(window, frame)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                    if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                        break
        except KeyboardInterrupt:
            pass
        finally:
            # Aguarda os envios autorizados e torna falhas visíveis ao encerrar.
            for future in pending:
                future.result()


def main(default_detector: str = "yolo") -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--detector", choices=("yolo", "ssd"), default=default_detector)
    parser.add_argument("--no-display", action="store_true", help="Executa sem janela; encerre com Ctrl+C.")
    args = parser.parse_args()
    run(load_config(args.config), args.detector, display=not args.no_display)


if __name__ == "__main__":
    main()
