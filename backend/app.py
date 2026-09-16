from datetime import UTC, datetime
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import ASCENDING, DESCENDING, MongoClient
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError
from typing import Literal

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


client = MongoClient(
    "mongodb://localhost:27017/"
)

db = client["aquamonitor"]

stations_collection = db["stations"]
bottle_metrics_collection = db["bottle_metrics"]
bottle_events_collection = db["bottle_events"]

# ============================
# Pydantic models
# ============================

class BottleCountPayload(BaseModel):
    count: int
    count_by_direction: dict[str, int]

class BottleEventPayload(BaseModel):
    """An individual bottle crossing reported by the detection pipeline."""

    event_id: str
    direction: Literal["positive", "negative"]
    timestamp: datetime

    @field_validator("event_id")
    @classmethod
    def event_id_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("event_id must not be blank")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


@app.on_event("startup")
def create_bottle_event_indexes() -> None:
    """Enforce idempotency even when two requests arrive concurrently."""
    bottle_events_collection.create_index(
        [("event_id", ASCENDING)],
        name="unique_bottle_event_id",
        unique=True,
    )


def create_bottle_metrics_indexes() -> None:
    """Create the index used to retrieve the newest metric for each station."""
    # Drop any pre-existing conflicting index with the same key pattern
    # but a different auto-generated name (e.g. from a prior run).
    existing = bottle_metrics_collection.index_information()
    for idx_name, idx_info in existing.items():
        if idx_info["key"] == [("station_id", 1), ("timestamp", -1)] and idx_name != "station_id_timestamp_desc":
            bottle_metrics_collection.drop_index(idx_name)
    bottle_metrics_collection.create_index(
        [("station_id", ASCENDING), ("timestamp", DESCENDING)],
        name="station_id_timestamp_desc",
    )


@app.on_event("startup")
def initialize_indexes() -> None:
    create_bottle_metrics_indexes()


def serialize_bottle_count(metric: dict | None) -> dict:
    """Return the dashboard's stable bottle-count representation."""
    if metric is None:
        return {
            "count": 0,
            "positive": 0,
            "negative": 0,
            "timestamp": None,
        }

    directions = metric.get("count_by_direction", {})
    timestamp = metric.get("timestamp")
    return {
        "count": metric.get("count", 0),
        "positive": directions.get("positive", 0),
        "negative": directions.get("negative", 0),
        "timestamp": timestamp.isoformat() if timestamp else None,
    }


# ============================
# POST
# ============================

@app.post("/api/stations")
def create_station(station: dict):

    print("Database:", db.name)
    print("Collection:", stations_collection.name)
    print("Document:", station)

    existing = stations_collection.find_one({"station_id": station.get("station_id")})
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Station with this station_id already exists"
        )

    result = stations_collection.insert_one(station)

    print("Inserted ID:", result.inserted_id)

    return {
        "message": "Station created successfully",
        "id": str(result.inserted_id)
    }

# ============================
# GET
# ============================
@app.get("/api/stations")
def get_stations():
    """List stations with their latest bottle metric in one batch query."""
    latest_metrics = bottle_metrics_collection.aggregate([
        {"$sort": {"station_id": 1, "timestamp": -1}},
        {
            "$group": {
                "_id": "$station_id",
                "count": {"$first": "$count"},
                "count_by_direction": {"$first": "$count_by_direction"},
                "timestamp": {"$first": "$timestamp"},
            }
        },
    ])
    metrics_by_station = {
        metric["_id"]: metric
        for metric in latest_metrics
    }

    result = []
    for station in stations_collection.find():
        bottle_count = serialize_bottle_count(
            metrics_by_station.get(station["station_id"])
        )
        result.append({
            "station_id": station["station_id"],
            "location": station.get("location"),
            "administrative": station.get("administrative"),
            # Compatibility field; bottle_count is the dashboard's source of truth.
            "detections": bottle_count["count"],
            "bottle_count": bottle_count,
        })

    return result

# ============================
# DELETE: permitir deletar a estação por enquanto
# ============================
@app.delete("/api/stations/{station_id}")
def delete_station(station_id: str):

    try:
        station_id = int(station_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Station ID must be a number"
        )

    result = stations_collection.delete_one({
        "station_id": station_id
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Station not found"
        )

    return {
        "message": "Station deleted successfully"
    }


# ============================
# BOTTLE COUNT — Phase 3
# ============================

@app.post("/api/stations/{station_id}/bottle-count")
def ingest_bottle_count(station_id: int, payload: BottleCountPayload):
    """Ingest the aggregate bottle count from a detection pipeline."""
    if stations_collection.find_one({"station_id": station_id}) is None:
        raise HTTPException(
            status_code=404,
            detail="Station not found",
        )

    document = {
        "station_id": station_id,
        "count": payload.count,
        "count_by_direction": payload.count_by_direction,
        "timestamp": datetime.now(UTC),
    }

    result = bottle_metrics_collection.insert_one(document)

    print(
        "Bottle count ingested for station %d: %d (inserted_id=%s)",
        station_id,
        payload.count,
        result.inserted_id,
    )

    return {
        "message": "Bottle count ingested successfully",
        "id": str(result.inserted_id),
        "station_id": station_id,
        "count": payload.count,
    }


@app.get("/api/stations/{station_id}/bottle-count")
def get_bottle_count(station_id: int):
    """Retrieve the latest bottle count for a station."""
    if stations_collection.find_one({"station_id": station_id}) is None:
        raise HTTPException(
            status_code=404,
            detail="Station not found",
        )

    document = bottle_metrics_collection.find_one(
        {"station_id": station_id},
        sort=[("timestamp", -1)],
    )

    if document is None:
        return {
            "station_id": station_id,
            "count": 0,
            "count_by_direction": {"positive": 0, "negative": 0},
            "timestamp": None,
        }

    return {
        "station_id": document["station_id"],
        "count": document["count"],
        "count_by_direction": document["count_by_direction"],
        "timestamp": document["timestamp"].isoformat(),
    }




@app.post("/api/stations/{station_id}/bottle-events", status_code=201)
def ingest_bottle_event(station_id: int, payload: BottleEventPayload):
    """Store one crossing event, rejecting duplicate event IDs."""
    if stations_collection.find_one({"station_id": station_id}) is None:
        raise HTTPException(status_code=404, detail="Station not found")

    document = {
        "event_id": payload.event_id,
        "station_id": station_id,
        "direction": payload.direction,
        "timestamp": payload.timestamp,
    }
    try:
        result = bottle_events_collection.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=409,
            detail="Bottle event already exists",
        ) from exc

    return {
        "message": "Bottle event ingested successfully",
        "id": str(result.inserted_id),
        "event_id": payload.event_id,
        "station_id": station_id,
    }


# ============================
# ============================
# Update(não existem motivos por enquanto)
# ============================
