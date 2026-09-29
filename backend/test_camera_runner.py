"""Regression tests for OpenCV empty output and operation without Qt."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np

spec = importlib.util.spec_from_file_location('camera_runner', Path(__file__).parent / 'detection/object-ident.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CameraRunnerTests(unittest.TestCase):
    def test_detector_accepts_empty_and_nonempty_outputs(self):
        detector = runner.OpenCVDnnDetector.__new__(runner.OpenCVDnnDetector)
        detector.class_names = ['bottle']
        detector.net = Mock()
        for output in (((), (), ()), (np.array([]), np.array([]), ()), (None, None, None)):
            detector.net.detect.return_value = output
            self.assertEqual(detector.detect(None, confidence_threshold=.45, nms_threshold=.2), [])
        for ids, scores in (((1,), (.9,)), (np.array([[1]]), np.array([[.9]]))):
            detector.net.detect.return_value = (ids, scores, [(10, 20, 30, 40)])
            result = detector.detect(None, confidence_threshold=.45, nms_threshold=.2)
            self.assertEqual(result[0].xyxy, (10, 20, 40, 60))
            self.assertEqual(result[0].class_name, 'bottle')

    def test_no_display_processes_frame_and_cleans_up_on_interrupt(self):
        with patch.object(runner.sys, 'argv', ['object-ident.py', '--no-display', '--publish']), \
             patch.object(runner, 'OpenCVDnnDetector') as detector, \
             patch.object(runner, 'DetectionPipeline') as pipeline, \
             patch.object(runner, 'cv2') as cv:
            camera = cv.VideoCapture.return_value
            camera.read.side_effect = [(True, object()), KeyboardInterrupt()]
            detector.return_value.detect.return_value = []
            runner.main()
            pipeline.return_value.process.assert_called_once_with([])
            camera.release.assert_called_once()
            pipeline.return_value.close.assert_called_once()
            cv.imshow.assert_not_called()
            cv.waitKey.assert_not_called()
            cv.destroyAllWindows.assert_not_called()


if __name__ == '__main__':
    unittest.main()
