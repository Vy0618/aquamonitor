"""Regression coverage for the camera pipeline's detection API contract."""

import unittest
from unittest.mock import Mock, patch

import requests
from fastapi.testclient import TestClient

import backend.app as application
from backend.detection.api_client import BottleCountApiClient
from backend.detection.config import ApiConfig, CountingLineConfig
from backend.detection.detection_pipeline import DetectionPipeline
from backend.detection.line_counter import CrossingEvent, TrackedObject


class PublishingTests(unittest.TestCase):
    def test_crossing_reaches_current_api_once(self):
        tracker = Mock()
        tracker.update.side_effect = [
            [TrackedObject(7, (1, 0, 3, 2), 'bottle', 0.9)],
            [TrackedObject(7, (1, 8, 3, 10), 'bottle', 0.85)],
        ]
        pipeline = DetectionPipeline(
            tracker=tracker,
            line_config=CountingLineConfig(start=(0, 5), end=(10, 5)),
            api_config=ApiConfig(enabled=True, publish_interval_seconds=0),
        )
        client = TestClient(application.app)
        with patch.object(application, 'stations_collection') as stations, \
             patch.object(application, 'detection_events_collection') as events, \
             patch('backend.detection.api_client.requests.post', side_effect=client.post) as post:
            stations.find_one.return_value = {'station_id': 1}
            events.insert_one.return_value = Mock(inserted_id='id')
            pipeline.process([])
            self.assertEqual(post.call_count, 0)
            pipeline.process([])
            pipeline.publish_if_due(force=True)
            self.assertTrue(pipeline.close())
            self.assertEqual(post.call_count, 1)
            document = events.insert_one.call_args.args[0]
            self.assertEqual(document['confidence'], 0.85)
            self.assertEqual(document['track_id'], 7)
            self.assertEqual(document['detection_type'], 'bottle')

    def test_retry_preserves_id_and_accepts_duplicate(self):
        client = BottleCountApiClient(ApiConfig(enabled=True))
        client.enqueue(CrossingEvent(7, (2, 5), 'positive', 'bottle'), 0.9)
        with patch('backend.detection.api_client.requests.post') as post:
            post.side_effect = [requests.Timeout('lost response'), Mock(status_code=409)]
            self.assertFalse(client.publish())
            self.assertTrue(client.publish())
            self.assertFalse(client.publish())
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args_list[0].kwargs['json'], post.call_args_list[1].kwargs['json'])

    def test_disabled_publisher_does_not_queue(self):
        client = BottleCountApiClient(ApiConfig(enabled=False))
        client.enqueue(CrossingEvent(7, (2, 5), 'positive', 'bottle'), 0.9)
        with patch('backend.detection.api_client.requests.post') as post:
            self.assertFalse(client.publish())
            post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
