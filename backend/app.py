from datetime import UTC, datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import ASCENDING, DESCENDING, MongoClient
from fastapi.middleware.cors import CORSMiddleware

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


# ============================
# Pydantic models
# ============================

class BottleCountPayload(BaseModel):
    count: int
    count_by_direction: dict[str, int]


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
            "location": station["location"],
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


# ============================
# Update(não existem motivos por enquanto)
# ============================
