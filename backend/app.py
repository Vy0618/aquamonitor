"""API AquaMonitor com persistência relacional em PostgreSQL."""

from datetime import UTC, datetime
import os
from typing import Literal

import psycopg
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DATABASE_URL = os.getenv("AQUAMONITOR_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aquamonitor")


def connect_database():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


class DetectionPayload(BaseModel):
    """Formato enviado pelos monitores YOLO e SSD da Raspberry Pi."""

    event_id: str
    station_id: int = Field(gt=0)
    detection_type: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    track_id: int = Field(ge=0)
    detected_at: datetime
    direction: Literal["positive", "negative"] | None = None

    @field_validator("event_id", "detection_type")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("detected_at")
    @classmethod
    def detected_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("detected_at must include a timezone")
        return value


@app.on_event("startup")
def initialize_database() -> None:
    """Cria o esquema relacional necessário, preservando dados existentes."""
    with connect_database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_id BIGINT PRIMARY KEY CHECK (station_id > 0),
                longitude DOUBLE PRECISION,
                latitude DOUBLE PRECISION,
                country TEXT,
                state TEXT,
                city TEXT,
                district TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
        """)
        connection.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS detection_events (
                event_id TEXT PRIMARY KEY,
                station_id BIGINT NOT NULL REFERENCES stations(station_id),
                detection_type VARCHAR(100) NOT NULL,
                confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                track_id BIGINT NOT NULL CHECK (track_id >= 0),
                detected_at TIMESTAMPTZ NOT NULL,
                direction TEXT CHECK (direction IN ('positive', 'negative') OR direction IS NULL)
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS station_id_detected_at_desc ON detection_events (station_id, detected_at DESC)")


def empty_summary() -> dict:
    return {"total": 0, "by_type": {}, "by_direction": {"positive": 0, "negative": 0, "unknown": 0},
            "by_type_direction": {}, "timestamp": None}


def _station_values(station: dict) -> tuple:
    location = station.get("location") or {}
    coordinates = location.get("coordinates") if isinstance(location, dict) else None
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
        longitude = latitude = None
    else:
        longitude, latitude = coordinates
    administrative = station.get("administrative") or {}
    if not isinstance(administrative, dict):
        administrative = {}
    return (longitude, latitude, administrative.get("country"), administrative.get("state"),
            administrative.get("city"), administrative.get("district"))


def _location_response(station: dict) -> dict | None:
    if station["longitude"] is None or station["latitude"] is None:
        return None
    return {"type": "Point", "coordinates": [station["longitude"], station["latitude"]]}


def _administrative_response(station: dict) -> dict:
    return {field: station[field] for field in ("country", "state", "city", "district") if station[field] is not None}


def detection_summary_for_stations(station_id: int | None = None) -> dict[int, dict]:
    query = """SELECT station_id, detection_type, direction, COUNT(*) AS count, MAX(detected_at) AS last_detected_at
               FROM detection_events"""
    params: tuple = ()
    if station_id is not None:
        query += " WHERE station_id = %s"
        params = (station_id,)
    query += " GROUP BY station_id, detection_type, direction"
    summaries: dict[int, dict] = {}
    with connect_database() as connection:
        rows = connection.execute(query, params).fetchall()
    for row in rows:
        current = summaries.setdefault(row["station_id"], empty_summary())
        kind = row["detection_type"]
        direction = row["direction"] if row["direction"] in ("positive", "negative") else "unknown"
        count = row["count"]
        current["total"] += count
        current["by_type"][kind] = current["by_type"].get(kind, 0) + count
        current["by_direction"][direction] += count
        by_type = current["by_type_direction"].setdefault(kind, {"positive": 0, "negative": 0, "unknown": 0})
        by_type[direction] += count
        timestamp = row["last_detected_at"].astimezone(UTC).isoformat()
        if current["timestamp"] is None or timestamp > current["timestamp"]:
            current["timestamp"] = timestamp
    return summaries


@app.post("/api/stations")
def create_station(station: dict):
    station_id = station.get("station_id")
    if type(station_id) is not int or station_id <= 0:
        raise HTTPException(status_code=422, detail="station_id must be a positive integer")
    try:
        with connect_database() as connection:
            result = connection.execute(
                """INSERT INTO stations (station_id, longitude, latitude, country, state, city, district, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                   ON CONFLICT (station_id) DO UPDATE SET longitude = EXCLUDED.longitude,
                   latitude = EXCLUDED.latitude, country = EXCLUDED.country, state = EXCLUDED.state,
                   city = EXCLUDED.city, district = EXCLUDED.district, is_active = TRUE
                   WHERE stations.is_active = FALSE""",
                (station_id, *_station_values(station)),
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=409, detail="Station with this station_id already exists")
    except UniqueViolation as error:
        raise HTTPException(status_code=409, detail="Station with this station_id already exists") from error
    except HTTPException:
        raise
    return {"message": "Station created successfully", "id": str(station_id)}


@app.get("/api/stations")
def get_stations():
    summaries = detection_summary_for_stations()
    with connect_database() as connection:
        stations = connection.execute("SELECT * FROM stations WHERE is_active = TRUE ORDER BY station_id").fetchall()
    return [{"station_id": station["station_id"], "location": _location_response(station),
             "administrative": _administrative_response(station), "detections": summaries.get(station["station_id"], empty_summary())["total"],
             "detection_summary": summaries.get(station["station_id"], empty_summary())} for station in stations]


@app.delete("/api/stations/{station_id}")
def delete_station(station_id: int):
    with connect_database() as connection:
        result = connection.execute("UPDATE stations SET is_active = FALSE WHERE station_id = %s AND is_active = TRUE", (station_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Station not found")
    return {"message": "Station deleted successfully"}


@app.post("/api/detections", status_code=201)
def ingest_detection(payload: DetectionPayload):
    """Armazena um cruzamento detectado pela estação embarcada."""
    try:
        with connect_database() as connection:
            active_station = connection.execute(
                "SELECT 1 FROM stations WHERE station_id = %s AND is_active = TRUE", (payload.station_id,)
            ).fetchone()
            if active_station is None:
                raise HTTPException(status_code=404, detail="Station not found")
            connection.execute(
                """INSERT INTO detection_events
                   (event_id, station_id, detection_type, confidence, track_id, detected_at, direction)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (payload.event_id, payload.station_id, payload.detection_type, payload.confidence,
                 payload.track_id, payload.detected_at, payload.direction),
            )
    except UniqueViolation as error:
        raise HTTPException(status_code=409, detail="Detection event already exists") from error
    except HTTPException:
        raise
    except ForeignKeyViolation as error:
        raise HTTPException(status_code=404, detail="Station not found") from error
    return {"message": "Detection ingested successfully", "id": payload.event_id,
            "event_id": payload.event_id, "station_id": payload.station_id}


@app.get("/api/stations/{station_id}/detections")
def get_station_detections(station_id: int):
    with connect_database() as connection:
        exists = connection.execute("SELECT 1 FROM stations WHERE station_id = %s AND is_active = TRUE", (station_id,)).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Station not found")
    return {"station_id": station_id, **detection_summary_for_stations(station_id).get(station_id, empty_summary())}
