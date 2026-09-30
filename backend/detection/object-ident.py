"""Live camera runner for detector -> ByteTrack -> bottle line counter.

Run from the repository root with:
``.venv/bin/python backend/detection/object-ident.py``.
Press ``q`` to quit.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

# Keep direct execution working even though this historical filename contains a
# hyphen and therefore cannot be run with ``python -m``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from backend.detection.config import API, COUNTING_LINE, ApiConfig, line_config
    from backend.detection.detection_pipeline import DetectionPipeline, PipelineResult
    from backend.detection.tracker import Detection
else:
    from .config import API, COUNTING_LINE, ApiConfig, line_config
    from .detection_pipeline import DetectionPipeline, PipelineResult
    from .tracker import Detection


from backend.settings import CONFIG_FILE, load_config
from backend.detection.config import ByteTrackConfig
from backend.detection.tracker import ByteTrackTracker


class OpenCVDnnDetector:
    """Adapt OpenCV DNN SSD MobileNet output to the project's Detection type."""

    def __init__(self, settings=None) -> None:
        settings = settings or load_config()["ssd_mobilenet"]
        class_file = Path(settings["labels_path"])
        self.class_names = class_file.read_text(encoding="utf-8").splitlines()
        self.net = cv2.dnn_DetectionModel(
            settings["model_path"],
            settings["config_path"],
        )
        self.net.setInputSize(settings["input_width"], settings["input_height"])
        self.net.setInputScale(1.0 / 127.5)
        self.net.setInputMean((127.5, 127.5, 127.5))
        self.net.setInputSwapRB(True)

    def detect(
        self,
        image,
        *,
        confidence_threshold: float,
        nms_threshold: float,
        classes: frozenset[str] | None = None,
    ) -> list[Detection]:
        class_ids, confidences, boxes = self.net.detect(
            image,
            confThreshold=confidence_threshold,
            nmsThreshold=nms_threshold,
        )
        detections: list[Detection] = []
        for class_id, confidence, (x, y, width, height) in zip(
            class_ids.flatten(), confidences.flatten(), boxes
        ):
            class_name = self.class_names[int(class_id) - 1]
            if classes is not None and class_name not in classes:
                continue
            detections.append(
                Detection(
                    xyxy=(float(x), float(y), float(x + width), float(y + height)),
                    confidence=float(confidence),
                    class_id=int(class_id),
                    class_name=class_name,
                )
            )
        return detections


def draw_overlay(image, result: PipelineResult) -> None:
    """Draw tracks, the configured line, and the current aggregate on a frame."""
    start = tuple(map(int, COUNTING_LINE.start))
    end = tuple(map(int, COUNTING_LINE.end))
    cv2.line(image, start, end, (0, 165, 255), 2)
    for track in result.tracks:
        x1, y1, x2, y2 = map(int, track.xyxy)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            image,
            f"{track.class_name or 'object'} #{track.track_id}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
    cv2.putText(
        image,
        f"Garrafas: {result.total_count}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 165, 255),
        3,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count bottles crossing a camera line")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    known, _ = config_parser.parse_known_args()
    settings = load_config(known.config)
    parser.add_argument("--camera", type=int, default=settings["camera"]["device_index"], help="OpenCV camera index (default: 0)")
    parser.add_argument("--width", type=int, default=settings["camera"]["width"])
    parser.add_argument("--height", type=int, default=settings["camera"]["height"])
    parser.add_argument("--detection-interval", type=float, default=settings["detection_interval_ms"] / 1000)
    parser.add_argument("--confidence", type=float, default=settings["ssd_mobilenet"]["confidence_threshold"])
    parser.add_argument("--nms", type=float, default=settings["ssd_mobilenet"]["nms_threshold"])
    parser.add_argument("--publish", action="store_true", help="Publish crossing events to the detection API")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_config(args.config)
    global COUNTING_LINE
    COUNTING_LINE = line_config(settings, args.width, args.height)
    api_config = ApiConfig(**{key: settings['backend'][key] for key in
        ('base_url', 'publish_interval_seconds', 'detections_path', 'timeout_seconds')},
        station_id=settings['station_id'], enabled=args.publish or settings['backend']['enabled'])
    detector = OpenCVDnnDetector(settings['ssd_mobilenet'])
    pipeline = DetectionPipeline(api_config=api_config, line_config=COUNTING_LINE,
        tracker=ByteTrackTracker(ByteTrackConfig(**settings['bytetrack'])))
    camera = cv2.VideoCapture(args.camera)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    camera.set(cv2.CAP_PROP_FPS, settings["camera"]["fps"])
    if not camera.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera}")

    latest_result = PipelineResult([], [], 0)
    last_detection_at = 0.0
    try:
        while True:
            success, image = camera.read()
            if not success:
                raise RuntimeError("Could not read a frame from the camera")
            now = time.monotonic()
            if now - last_detection_at >= args.detection_interval:
                detections = detector.detect(
                    image,
                    confidence_threshold=args.confidence,
                    nms_threshold=args.nms,
                    classes=COUNTING_LINE.classes_to_count,
                )
                latest_result = pipeline.process(detections)
                last_detection_at = now
            else:
                pipeline.publish_if_due()

            draw_overlay(image, latest_result)
            cv2.imshow("AquaMonitor Bottle Counter", image)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        pipeline.publish_if_due(force=True)
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
