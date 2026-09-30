import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from backend.camera.image_processing import prepare_frame, restore_coordinates
from backend.detection.types import Detection
from backend.monitoring import monitor_residuos as monitor
from backend.settings import load_config
from backend.tracking.line_tracker import LineTracker


class ImageProcessingTests(unittest.TestCase):
    def test_resize_preserves_aspect_and_never_enlarges(self):
        settings = dict(enabled=True, max_width=320, max_height=240)
        wide = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertEqual(prepare_frame(wide, settings).shape, (180, 320, 3))
        small = np.zeros((120, 160, 3), dtype=np.uint8)
        self.assertIs(prepare_frame(small, settings), small)
        self.assertIs(prepare_frame(wide, {'enabled': False}), wide)

    def test_restored_boxes_preserve_crossing_and_confidence(self):
        tracker = LineTracker(line_y=240, max_distance=90)
        for y, expected in ((100, 0), (140, 1)):
            boxes = restore_coordinates([Detection('bottle', .85, (45, y-5, 55, y+5))],
                                        (240, 320, 3), (480, 640, 3))
            crossings = tracker.update(boxes)
            self.assertEqual(len(crossings), expected)
        self.assertEqual(crossings[0].confidence, .85)

    def test_invalid_configuration_rejected(self):
        config = load_config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for section, value in [('display', {'enabled': 'false'}),
                                   ('image_processing', {'enabled': True, 'max_width': 0, 'max_height': 240}),
                                   ('image_processing', {'enabled': True, 'max_width': True, 'max_height': 240})]:
                with self.subTest(value=value):
                    path.write_text(json.dumps({**config, section: value}))
                    with self.assertRaises(ValueError):
                        load_config(path)

    def test_cli_override_and_json_default(self):
        for flags, expected in [([], None), (['--display'], True), (['--no-display'], False)]:
            with patch('sys.argv', ['monitor', *flags]), patch.object(monitor, 'run') as run:
                monitor.main()
                self.assertIs(run.call_args.kwargs['display'], expected)


if __name__ == '__main__':
    unittest.main()
