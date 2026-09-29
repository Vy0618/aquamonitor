"""Network stalls must not stall frame processing or event producers."""

import threading
import unittest
from unittest.mock import Mock, patch

from backend.detection.api_client import BottleCountApiClient
from backend.detection.config import ApiConfig, CountingLineConfig
from backend.detection.detection_pipeline import DetectionPipeline
from backend.detection.line_counter import CrossingEvent, TrackedObject
from backend.detection.publisher import BackgroundPublisher


class BackgroundPublisherTests(unittest.TestCase):
    def test_pipeline_continues_while_http_is_blocked(self):
        entered, release, processed = threading.Event(), threading.Event(), threading.Event()

        def slow_post(*args, **kwargs):
            entered.set()
            release.wait(3)
            return Mock(status_code=201)

        tracker = Mock()
        tracker.update.side_effect = [
            [TrackedObject(7, (1, 0, 3, 2), 'bottle', 0.9)],
            [TrackedObject(7, (1, 8, 3, 10), 'bottle', 0.85)],
            [],
        ]
        with patch('backend.detection.api_client.requests.post', side_effect=slow_post) as post:
            pipeline = DetectionPipeline(
                tracker=tracker,
                line_config=CountingLineConfig(start=(0, 5), end=(10, 5)),
                api_config=ApiConfig(enabled=True, publish_interval_seconds=0),
            )
            def frames():
                pipeline.process([])
                pipeline.process([])
                entered.wait(1)
                pipeline.process([])
                pipeline.api_client.enqueue(CrossingEvent(8, (2, 5), 'positive', 'bottle'), 0.8)
                processed.set()
            producer = threading.Thread(target=frames)
            try:
                producer.start()
                self.assertTrue(entered.wait(1))
                self.assertTrue(processed.wait(1), 'Frame processing blocked on HTTP')
                self.assertEqual(pipeline.api_client.pending_count, 2)
                self.assertFalse(pipeline.close(timeout=0.01))
            finally:
                release.set()
                producer.join(3)
                pipeline.close()
            # A shutdown during an active batch may leave newer events pending;
            # their UUIDs and payloads remain available in the in-memory queue.
            self.assertGreaterEqual(post.call_count, 1)

    def test_close_flushes_idle_worker_and_disabled_mode_does_not_send(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled), patch('backend.detection.api_client.requests.post') as post:
                post.return_value = Mock(status_code=201)
                client = BottleCountApiClient(ApiConfig(enabled=enabled))
                worker = BackgroundPublisher(client)
                client.enqueue(CrossingEvent(1, (0, 0), 'positive', 'bottle'), 0.9)
                self.assertTrue(worker.close())
                self.assertEqual(post.call_count, int(enabled))
                self.assertFalse(worker.request())


if __name__ == '__main__':
    unittest.main()
