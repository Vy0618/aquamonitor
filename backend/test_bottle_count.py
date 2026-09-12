"""Unit tests for associating bottle metrics with registered stations."""

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

import backend.app as application


class BottleCountStationAssociationTests(unittest.TestCase):
    def setUp(self) -> None:
        application.stations_collection = Mock()
        application.stations_collection.find_one.return_value = {"station_id": 1}
        application.bottle_metrics_collection = Mock()
        application.bottle_metrics_collection.insert_one.return_value = SimpleNamespace(
            inserted_id="metric-id"
        )

    def test_post_stores_metric_for_registered_station(self) -> None:
        payload = application.BottleCountPayload(
            count=4,
            count_by_direction={"positive": 3, "negative": 1},
        )

        response = application.ingest_bottle_count(1, payload)

        self.assertEqual(response["station_id"], 1)
        document = application.bottle_metrics_collection.insert_one.call_args.args[0]
        self.assertEqual(document["station_id"], 1)

    def test_post_rejects_metric_for_unknown_station(self) -> None:
        application.stations_collection.find_one.return_value = None

        with self.assertRaises(HTTPException) as error:
            application.ingest_bottle_count(
                999,
                application.BottleCountPayload(
                    count=1,
                    count_by_direction={"positive": 1, "negative": 0},
                ),
            )

        self.assertEqual(error.exception.status_code, 404)
        application.bottle_metrics_collection.insert_one.assert_not_called()

    def test_registered_station_without_metric_returns_zero_count(self) -> None:
        application.bottle_metrics_collection.find_one.return_value = None

        response = application.get_bottle_count(1)

        self.assertEqual(response["station_id"], 1)
        self.assertEqual(response["count"], 0)
        self.assertEqual(response["count_by_direction"], {"positive": 0, "negative": 0})

    def test_latest_metric_remains_scoped_to_requested_station(self) -> None:
        application.bottle_metrics_collection.find_one.return_value = {
            "station_id": 1,
            "count": 5,
            "count_by_direction": {"positive": 3, "negative": 2},
            "timestamp": datetime(2026, 9, 12, 12, 0, 0),
        }

        response = application.get_bottle_count(1)

        self.assertEqual(response["station_id"], 1)
        self.assertEqual(response["count"], 5)


if __name__ == "__main__":
    unittest.main()
