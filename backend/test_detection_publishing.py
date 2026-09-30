"""Verify crossings use the API schema and retries do not duplicate identity."""
import unittest
from unittest.mock import Mock, patch

import requests
from backend.app import DetectionPayload
from backend.detection.api_client import BottleCountApiClient
from backend.detection.config import ApiConfig, CountingLineConfig
from backend.detection.detection_pipeline import DetectionPipeline
from backend.detection.line_counter import CrossingEvent, TrackedObject


class PublishingTests(unittest.TestCase):
    def test_crossing_produces_valid_payload_once(self):
        tracker = Mock()
        tracker.update.side_effect = [
            [TrackedObject(7, (1, 0, 3, 2), 'bottle', .9)],
            [TrackedObject(7, (1, 8, 3, 10), 'bottle', .85)],
            [TrackedObject(7, (1, 0, 3, 2), 'bottle', .8)],
        ]
        pipeline = DetectionPipeline(tracker=tracker,
            line_config=CountingLineConfig((0, 5), (10, 5)),
            api_config=ApiConfig(enabled=True, base_url='http://server:8000/', station_id=12,
                                 detections_path='/api/detections', timeout_seconds=7,
                                 publish_interval_seconds=0))
        with patch('backend.detection.api_client.requests.post') as post:
            post.return_value = Mock(status_code=201)
            pipeline.process([])
            post.assert_not_called()
            pipeline.process([])
            pipeline.process([])
            pipeline.publish_if_due(force=True)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.args[0], 'http://server:8000/api/detections')
            self.assertEqual(post.call_args.kwargs['timeout'], 7)
            payload = DetectionPayload.model_validate(post.call_args.kwargs['json'])
            self.assertEqual((payload.station_id, payload.track_id, payload.confidence), (12, 7, .85))
            self.assertEqual(payload.detection_type, 'bottle')
            self.assertEqual(payload.direction, 'positive')

    def test_retry_and_duplicate_confirmation(self):
        client = BottleCountApiClient(ApiConfig(enabled=True))
        client.enqueue(CrossingEvent(7, (2, 5), 'positive', 'bottle'), .9)
        with patch('backend.detection.api_client.requests.post') as post:
            post.side_effect = [requests.Timeout('lost response'), Mock(status_code=409)]
            self.assertFalse(client.publish())
            self.assertTrue(client.publish())
            self.assertFalse(client.publish())
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args_list[0].kwargs['json'], post.call_args_list[1].kwargs['json'])

    def test_disabled_does_not_send(self):
        client = BottleCountApiClient(ApiConfig(enabled=False))
        client.enqueue(CrossingEvent(7, (2, 5), 'positive', 'bottle'), .9)
        with patch('backend.detection.api_client.requests.post') as post:
            self.assertFalse(client.publish())
            post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
