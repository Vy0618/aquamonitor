"""Unit tests for idempotent bottle-event ingestion."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

import backend.app as application


class BottleEventEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        application.stations_collection = Mock()
        application.stations_collection.find_one.return_value = {"station_id": 1}
        application.bottle_events_collection = Mock()
        application.bottle_events_collection.insert_one.return_value = SimpleNamespace(
            inserted_id="event-document-id"
        )
        self.payload = application.BottleEventPayload(
            event_id="camera-1-track-42-2026-09-12T12:00:00Z",
            direction="positive",
            timestamp="2026-09-12T12:00:00Z",
        )

    def test_event_is_stored_for_an_existing_station(self) -> None:
        response = application.ingest_bottle_event(1, self.payload)

        self.assertEqual(response["event_id"], self.payload.event_id)
        self.assertEqual(response["station_id"], 1)
        document = application.bottle_events_collection.insert_one.call_args.args[0]
        self.assertEqual(document["direction"], "positive")

    def test_startup_creates_unique_event_id_index(self) -> None:
        application.create_bottle_event_indexes()

        application.bottle_events_collection.create_index.assert_called_once_with(
            [("event_id", 1)],
            name="unique_bottle_event_id",
            unique=True,
        )
  
    def test_duplicate_event_id_returns_conflict_without_second_insert(self) -> None:
        application.bottle_events_collection.insert_one.side_effect = [
            SimpleNamespace(inserted_id="event-document-id"),
            DuplicateKeyError("duplicate event_id"),
        ]


    
        application.ingest_bottle_event(1, self.payload)
        with self.assertRaises(HTTPException) as error:
            application.ingest_bottle_event(1, self.payload)

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(application.bottle_events_collection.insert_one.call_count, 2)

    def test_unknown_station_is_rejected_before_inserting_event(self) -> None:
        application.stations_collection.find_one.return_value = None

        with self.assertRaises(HTTPException) as error:
            application.ingest_bottle_event(999, self.payload)

        self.assertEqual(error.exception.status_code, 404)
        application.bottle_events_collection.insert_one.assert_not_called()

    def test_invalid_direction_and_naive_timestamp_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            application.BottleEventPayload(
                event_id="event-1",
                direction="sideways",
                timestamp="2026-09-12T12:00:00Z",
            )
        with self.assertRaises(ValidationError):
            application.BottleEventPayload(
                event_id="event-2",
                direction="negative",
                timestamp="2026-09-12T12:00:00",
            )


if __name__ == "__main__":
    unittest.main()