"""Alternativa ao monitor YOLO: SSD MobileNet + mesmo tracker e envio HTTP."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import cv2

from RaspberryPi.camera.webcam_config import WebcamConfig
from RaspberryPi.communication.backend_client import BackendClient, BackendConfig
from RaspberryPi.detection.ssd_mobilenet_detector import SsdMobileNetDetector
from RaspberryPi.gps.gps_neo6m import Neo6mGps
from RaspberryPi.monitoring.monitor_residuos import (
    BASE_DIR,
    CONFIG_FILE,
    COUNTS_FILE,
    LINE_Y_RATIO,
    TRACKING_DIRECTION,
    draw_overlay,
    load_config,
    load_counts,
    save_counts,
)
from RaspberryPi.station.station_document import StationDocument
from RaspberryPi.tracking.line_tracker import LineTracker


def main() -> None:
    config = load_config(CONFIG_FILE)
    station_id = config["station_id"]
    backend_settings = config["backend"]
    client = BackendClient(BackendConfig(**{
        "base_url": backend_settings["base_url"],
        "detections_path": backend_settings["detections_path"],
        "timeout_seconds": backend_settings["timeout_seconds"],
    }))
    if backend_settings.get("require_connection_on_startup", True):
        client.ensure_station_is_available(station_id)

    station_settings = config["station_document"]
    station = StationDocument(BASE_DIR / station_settings["path"], station_id, station_settings)
    station.ensure_exists()
    gps = None
    gps_settings = config.get("gps", {})
    if gps_settings.get("enabled", False):
        gps = Neo6mGps(gps_settings["serial_port"], gps_settings["baudrate"], gps_settings["read_timeout_seconds"])
        gps.start()

    camera_config = WebcamConfig(**config["camera"])
    detector_settings = config["ssd_mobilenet"]
    detector = SsdMobileNetDetector(
        model_path=BASE_DIR / detector_settings["model_path"],
        config_path=BASE_DIR / detector_settings["config_path"],
        labels_path=BASE_DIR / detector_settings["labels_path"],
        confidence_threshold=detector_settings["confidence_threshold"],
        input_width=detector_settings["input_width"],
        input_height=detector_settings["input_height"],
        allowed_classes=detector_settings["detection_types"],
    )
    camera = camera_config.open_camera()
    counts = load_counts(COUNTS_FILE)
    tracker = LineTracker(line_y=int(camera_config.height * LINE_Y_RATIO), direction=TRACKING_DIRECTION)
    print("Monitor SSD MobileNet iniciado. Pressione Q ou ESC para encerrar.")
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
                fix = gps.latest_fix if gps is not None else None
                station.update(detections=sum(counts.values()), gps_fix=fix, status="online")
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
            cv2.imshow("Monitoramento de resíduos — SSD MobileNet", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        save_counts(COUNTS_FILE, station_id, counts)
        station.update(detections=sum(counts.values()), gps_fix=gps.latest_fix if gps else None, status="offline")
        if gps is not None:
            gps.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
