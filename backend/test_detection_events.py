"""Unit tests for generic detection ingestion and station summaries."""

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

import backend.app as application


class DetectionEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        application.stations_collection = Mock()
        application.stations_collection.find_one.return_value = {"station_id": 1}
        application.detection_events_collection = Mock()
        application.detection_events_collection.insert_one.return_value = SimpleNamespace(inserted_id="event-id")
        self.payload = application.DetectionPayload(
            event_id="event-1", station_id=1, detection_type="can", confidence=0.92,
            track_id=7, detected_at="2026-09-17T12:00:00Z",
        )

    def test_stores_any_detection_type_for_registered_station(self) -> None:
        response = application.ingest_detection(self.payload)
        self.assertEqual(response["station_id"], 1)
        document = application.detection_events_collection.insert_one.call_args.args[0]
        self.assertEqual(document["detection_type"], "can")
        self.assertEqual(document["track_id"], 7)
        self.assertIsInstance(document["detected_at"], datetime)

    def test_rejects_unknown_station(self) -> None:
        application.stations_collection.find_one.return_value = None
        with self.assertRaises(HTTPException) as error:
            application.ingest_detection(self.payload)
        self.assertEqual(error.exception.status_code, 404)

    def test_duplicate_event_is_rejected(self) -> None:
        application.detection_events_collection.insert_one.side_effect = DuplicateKeyError("duplicate")
        with self.assertRaises(HTTPException) as error:
            application.ingest_detection(self.payload)
        self.assertEqual(error.exception.status_code, 409)

    def test_station_summary_contains_total_and_types(self) -> None:
        application.stations_collection.find.return_value = [{
            "station_id": 1, "location": {"type": "Point", "coordinates": [-46.45, -23.50]},
        }]
        application.detection_events_collection.aggregate.return_value = [
            {"_id": {"station_id": 1, "detection_type": "bottle"}, "count": 3,
             "last_detected_at": datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)},
            {"_id": {"station_id": 1, "detection_type": "can"}, "count": 2,
             "last_detected_at": datetime(2026, 9, 17, 12, 5, tzinfo=timezone.utc)},
        ]
        station = application.get_stations()[0]
        self.assertEqual(station["detections"], 5)
        self.assertEqual(station["detection_summary"]["by_type"], {"bottle": 3, "can": 2})
        self.assertEqual(station["detection_summary"]["timestamp"], "2026-09-17T12:05:00+00:00")

    def test_summary_normalizes_mixed_and_invalid_timestamps(self) -> None:
        summary = application.serialize_detection_summary([{
            "_id": {"station_id": 1, "detection_type": "can"},
            "count": 4,
            "detected_at_values": [
                "not-a-date",
                "2026-09-17T11:00:00Z",
                datetime(2026, 9, 17, 12, 30, tzinfo=timezone.utc),
                "2026-09-17T14:30:00+02:00",
                None,
            ],
        }])
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["timestamp"], "2026-09-17T12:30:00+00:00")

    def test_get_stations_returns_locations_with_mixed_timestamps(self) -> None:
        application.stations_collection.find.return_value = [{
            "station_id": 1,
            "location": {"type": "Point", "coordinates": [-46.45, -23.50]},
            "administrative": {"city": "Santos"},
        }]
        application.detection_events_collection.aggregate.return_value = [{
            "_id": {"station_id": 1, "detection_type": "bottle"},
            "count": 2,
            "detected_at_values": [datetime(2026, 9, 17, 9, tzinfo=timezone.utc), "invalid"],
        }]
        station = application.get_stations()[0]
        self.assertEqual(station["location"]["coordinates"], [-46.45, -23.50])
        self.assertEqual(station["detection_summary"]["timestamp"], "2026-09-17T09:00:00+00:00")

    def test_startup_creates_detection_indexes(self) -> None:
        application.initialize_indexes()
        self.assertEqual(application.detection_events_collection.create_index.call_count, 2)


if __name__ == "__main__":
    unittest.main()
