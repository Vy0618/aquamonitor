"""Regressões do monitor, sem precisar de câmera nem backend físico."""

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from backend.camera.webcam_config import LatestFrameCamera, WebcamConfig
from backend.detection.types import Detection
from backend.detection.yolo_detector import EXPECTED_CLASSES
from backend.monitoring import monitor_residuos as monitor
from backend.tracking.line_tracker import LineTracker


def detection(x, y, confidence=0.8, name="bottle"):
    return Detection(name, confidence, (x - 5, y - 5, x + 5, y + 5))


class TrackerTests(unittest.TestCase):
    def test_crossings_use_confidence_of_matching_object(self):
        tracker = LineTracker(100)
        tracker.update([detection(20, 90), detection(200, 90)])
        events = tracker.update([detection(200, 110, 0.9), detection(20, 110, 0.6)])
        self.assertEqual({e.track_id: e.confidence for e in events}, {1: 0.6, 2: 0.9})
        self.assertTrue(all(e.direction == "positive" for e in events))
        self.assertEqual(tracker.update([detection(20, 80), detection(200, 80)]), [])

    def test_direction_and_missing_tracks(self):
        tracker = LineTracker(100, direction="up", max_missing_frames=1)
        tracker.update([detection(20, 90)])
        self.assertEqual(tracker.update([detection(20, 110)]), [])
        events = tracker.update([detection(20, 90)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].direction, "negative")
        tracker.update([])
        tracker.update([])
        self.assertEqual(tracker.objects, {})

    def test_different_classes_do_not_match(self):
        tracker = LineTracker(100)
        tracker.update([detection(20, 90)])
        self.assertEqual(tracker.update([detection(20, 110, name="can")]), [])

    def test_actual_frame_height_and_visible_line_without_objects(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        tracker = monitor.tracker_for_frame(frame, {"line_y_ratio": 0.55})
        self.assertEqual(tracker.line_y, 132)
        monitor.draw_overlay(frame, [], tracker, dict.fromkeys(EXPECTED_CLASSES, 0))
        np.testing.assert_array_equal(frame[132, 200], [0, 255, 255])


class PersistenceTests(unittest.TestCase):
    def test_first_run_creates_directory_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data" / "counts.json"
            counts = monitor.load_counts(path)
            counts["bottle"] = 3
            monitor.save_counts(path, 1, counts)
            self.assertEqual(monitor.load_counts(path), counts)
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_invalid_counts_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "counts.json"
            for content in ('[]', 'null', '{"counts": []}', '{"bottle": -1}', '{"bottle": true}', 'invalid'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    monitor.load_counts(path)
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_config_rejects_invalid_interval_and_line(self):
        config = monitor.load_config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for interval in (0, -1, float("nan"), float("inf")):
                config["detection_interval_ms"] = interval
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(ValueError):
                    monitor.load_config(path)
            config["detection_interval_ms"] = 250
            config["tracking"]["line_y_ratio"] = 2
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                monitor.load_config(path)


class CameraTests(unittest.TestCase):
    def test_windows_and_linux_select_backend(self):
        for system, expected in (("Windows", cv2.CAP_DSHOW), ("Linux", cv2.CAP_V4L2)):
            with patch("backend.camera.webcam_config.platform.system", return_value=system), patch("backend.camera.webcam_config.cv2.VideoCapture") as factory:
                camera = WebcamConfig().open_camera()
                factory.assert_called_once_with(0, expected)
                camera.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 640)
                camera.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                camera.set.assert_any_call(cv2.CAP_PROP_FPS, 15)

    def test_failed_open_releases_capture(self):
        with patch("backend.camera.webcam_config.cv2.VideoCapture") as factory:
            factory.return_value.isOpened.return_value = False
            with self.assertRaises(RuntimeError):
                WebcamConfig().open_camera()
            factory.return_value.release.assert_called_once()

    def test_capture_failure_is_reported_and_closed(self):
        capture = MagicMock()
        capture.read.return_value = (False, None)
        camera = LatestFrameCamera(capture)
        try:
            with self.assertRaises(RuntimeError):
                camera.read()
        finally:
            camera.close()
        capture.release.assert_called_once()
        self.assertFalse(camera.thread.is_alive())


class MonitorTests(unittest.TestCase):
    def run_monitor(self, directory, network_error=False, display=False):
        config = copy.deepcopy(monitor.load_config())
        config["display"] = {"enabled": False}
        config["image_processing"]["enabled"] = False
        config["station_document"]["path"] = str(Path(directory) / "station.json")
        config["station_document"]["detections"] = 0
        counts_path = Path(directory) / "counts.json"
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(5)]
        camera = MagicMock()
        camera.read.side_effect = frames + [KeyboardInterrupt()]
        detector = MagicMock()
        detector.detect.side_effect = [[detection(100, 120)], [detection(100, 140, 0.73)], []]
        client = MagicMock()
        if network_error:
            client.send_detection.side_effect = RuntimeError("HTTP indisponível")
        clock = SimpleNamespace(monotonic=MagicMock(side_effect=[0, 0.05, 0.249, 0.25, 0.50]))
        write_document = monitor.StationDocument._write
        with patch.object(monitor.StationDocument, "_write", autospec=True, side_effect=write_document) as writes, patch.object(monitor, "COUNTS_FILE", counts_path), patch.object(monitor, "create_detector", return_value=detector), patch.object(monitor, "BackendClient", return_value=client), patch.object(monitor, "LatestFrameCamera", return_value=camera), patch.object(WebcamConfig, "open_camera"), patch.object(monitor, "time", clock), patch.object(cv2, "namedWindow"), patch.object(cv2, "imshow") as show, patch.object(cv2, "waitKey", return_value=-1), patch.object(cv2, "getWindowProperty", return_value=1), patch.object(cv2, "destroyAllWindows") as destroy:
            if network_error:
                with self.assertRaisesRegex(RuntimeError, "HTTP indisponível"):
                    monitor.run(config, "yolo", display=display)
            else:
                monitor.run(config, "yolo", display=display)
                self.assertEqual(detector.detect.call_count, 3)
                client.send_detection.assert_called_once()
                event = client.send_detection.call_args.args[0]
                self.assertEqual(event["confidence"], 0.73)
                self.assertEqual(event["detection_type"], "bottle")
                self.assertEqual(event["direction"], "positive")
                self.assertEqual(show.call_count, 5 if display else 0)
                camera.read.assert_called_with(copy=bool(display))
            self.assertEqual(writes.call_count, 2)
            self.assertEqual(writes.call_args_list[0].args[1]["status"], "online")
            self.assertEqual(writes.call_args_list[1].args[1]["status"], "offline")
            self.assertEqual(writes.call_args_list[1].args[1]["detections"], 1)
            camera.close.assert_called_once()
            client.close.assert_called_once()
            self.assertEqual(destroy.call_count, int(bool(display)))
        self.assertEqual(json.loads((Path(directory) / "station.json").read_text())["status"], "offline")
        self.assertEqual(monitor.load_counts(counts_path)["bottle"], 1)

    def test_interval_crossing_and_headless_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            self.run_monitor(directory)

    def test_json_disables_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            self.run_monitor(directory, display=None)

    def test_preview_on_every_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            self.run_monitor(directory, display=True)

    def test_http_failure_preserves_counts_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            self.run_monitor(directory, network_error=True)

    def test_ssd_model_loads_and_detects_blank_frame(self):
        detector = monitor.create_detector(monitor.load_config(), "ssd")
        self.assertEqual(detector.detect(np.zeros((240, 320, 3), dtype=np.uint8)), [])


if __name__ == "__main__":
    unittest.main()
