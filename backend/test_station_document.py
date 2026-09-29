"""Testes de persistência e contrato CLI, sem serviços externos."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.station_document import create_document, read_document, update_document, validate


class StationDocumentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "nested" / "station.json"
        self.document = {
            "_id": {"$oid": "68c5d6c0a4e71b2f8d000001"},
            "station_id": 1, "detections": 37, "status": "online",
            "location": {"type": "Point", "coordinates": [-46.4526, -23.5015]},
            "administrative": {"country": "Brazil", "state": "São Paulo",
                               "city": "Santos", "district": "Baía de Santos"},
        }

    def test_create_read_and_refuse_overwrite(self):
        create_document(self.path, self.document)
        self.assertEqual(read_document(self.path), self.document)
        with self.assertRaises(FileExistsError):
            create_document(self.path, {**self.document, "detections": 0})
        self.assertEqual(read_document(self.path), self.document)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_update_preserves_identity_and_total(self):
        create_document(self.path, self.document)
        updated = update_document(self.path, {
            "detections": 5, "status": "offline",
            "location": {"type": "Point", "coordinates": [-47, -24]},
        })
        self.assertEqual(updated["detections"], 37)
        self.assertEqual(updated["station_id"], 1)
        self.assertEqual(updated["_id"], self.document["_id"])
        self.assertEqual(updated["status"], "offline")
        self.assertEqual(updated["location"]["coordinates"], [-47, -24])
        self.assertEqual(update_document(self.path, {"detections": 42})["detections"], 42)

    def test_invalid_updates_leave_file_unchanged(self):
        create_document(self.path, self.document)
        before = self.path.read_bytes()
        for changes in ({"station_id": 2}, {"_id": self.document["_id"]},
                        {"detections": -1}, {"detections": True}, {"status": "unknown"},
                        {"location": {"type": "Point", "coordinates": [181, 0]}},
                        {"administrative": {}}, {}, []):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    update_document(self.path, changes)
                self.assertEqual(self.path.read_bytes(), before)

    def test_rejects_invalid_coordinates_and_identifiers(self):
        for coordinates in ([True, 0], [float("nan"), 0], [0, float("inf")], [0, -91]):
            document = copy.deepcopy(self.document)
            document["location"]["coordinates"] = coordinates
            with self.subTest(coordinates=coordinates), self.assertRaises(ValueError):
                validate(document)
        for change in ({"station_id": True}, {"station_id": 0}, {"_id": {"$oid": "bad"}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**self.document, **change})

    def test_failed_replacement_preserves_original_and_cleans_temporary(self):
        create_document(self.path, self.document)
        with patch("backend.station_document.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                update_document(self.path, {"detections": 99})
        self.assertEqual(read_document(self.path), self.document)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_corrupt_file_is_not_reset(self):
        self.path.parent.mkdir()
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            update_document(self.path, {"status": "offline"})
        self.assertEqual(self.path.read_text(), "{broken")

    def test_cli_json_and_error_streams(self):
        def run(command, content=""):
            return subprocess.run(
                [sys.executable, "-m", "backend.station_document", command, str(self.path)],
                input=content, text=True, capture_output=True,
                cwd=Path(__file__).resolve().parents[1], check=False,
            )
        created = run("init", json.dumps(self.document))
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(json.loads(created.stdout), self.document)
        self.assertEqual(created.stderr, "")
        updated = run("update", '{"status":"offline"}')
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(json.loads(run("show").stdout)["status"], "offline")
        failed = run("update", "not json")
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(failed.stdout, "")
        self.assertIn("station_document:", failed.stderr)


if __name__ == "__main__":
    unittest.main()
