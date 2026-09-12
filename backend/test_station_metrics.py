"""Tests for stations enriched with their latest bottle metrics."""

from datetime import datetime
import unittest
from unittest.mock import Mock

import backend.app as application


class StationMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        application.stations_collection = Mock()
        application.bottle_metrics_collection = Mock()

    def test_station_with_metric_uses_latest_count_everywhere(self) -> None:
        location = {"type": "Point", "coordinates": [-46.4526, -23.5015]}
        application.stations_collection.find.return_value = [{
            "station_id": 1,
            "location": location,
            "detections": 6,
            "administrative": {"city": "Santos"},
        }]
        application.bottle_metrics_collection.aggregate.return_value = [{
            "_id": 1,
            "count": 37,
            "count_by_direction": {"positive": 20, "negative": 17},
            "timestamp": datetime(2026, 9, 12, 14, 20),
        }]

        station = application.get_stations()[0]

        self.assertEqual(station["location"], location)
        self.assertEqual(station["administrative"], {"city": "Santos"})
        self.assertEqual(station["detections"], 37)
        self.assertEqual(station["bottle_count"]["count"], 37)
        self.assertEqual(station["bottle_count"]["positive"], 20)
        self.assertEqual(station["bottle_count"]["negative"], 17)
        self.assertEqual(station["bottle_count"]["timestamp"], "2026-09-12T14:20:00")
        application.bottle_metrics_collection.aggregate.assert_called_once()

    def test_station_without_metric_has_zero_count(self) -> None:
        application.stations_collection.find.return_value = [{
            "station_id": 2,
            "location": {"type": "Point", "coordinates": [-46.0, -23.0]},
            "detections": 99,
        }]
        application.bottle_metrics_collection.aggregate.return_value = []

        station = application.get_stations()[0]

        self.assertEqual(station["detections"], 0)
        self.assertEqual(
            station["bottle_count"],
            {"count": 0, "positive": 0, "negative": 0, "timestamp": None},
        )

    def test_multiple_stations_receive_their_own_metrics(self) -> None:
        application.stations_collection.find.return_value = [
            {"station_id": 1, "location": {"coordinates": [1, 1]}},
            {"station_id": 2, "location": {"coordinates": [2, 2]}},
        ]
        application.bottle_metrics_collection.aggregate.return_value = [
            {"_id": 1, "count": 10, "count_by_direction": {}, "timestamp": None},
            {"_id": 2, "count": 25, "count_by_direction": {}, "timestamp": None},
        ]

        stations = application.get_stations()

        self.assertEqual([station["detections"] for station in stations], [10, 25])

    def test_index_is_created_for_latest_metric_lookup(self) -> None:
        application.create_bottle_metrics_indexes()

        application.bottle_metrics_collection.create_index.assert_called_once_with(
            [("station_id", 1), ("timestamp", -1)],
            name="station_id_timestamp_desc",
        )


if __name__ == "__main__":
    unittest.main()
