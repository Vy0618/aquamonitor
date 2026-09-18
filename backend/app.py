"""API do Aqua Monitor: estações e eventos gerais de detecção."""

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
db = client["aquamonitor"]
stations_collection = db["stations"]
detection_events_collection = db["detection_events"]


class DetectionPayload(BaseModel):
    """Formato enviado pelos monitores YOLO e SSD da Raspberry Pi."""

    event_id: str
    station_id: int = Field(gt=0)
    detection_type: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    track_id: int = Field(ge=0)
    detected_at: datetime

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
def initialize_indexes() -> None:
    """Mantém a ingestão idempotente e as consultas do painel rápidas."""
    detection_events_collection.create_index([("event_id", ASCENDING)], name="unique_detection_event_id", unique=True)
    detection_events_collection.create_index(
        [("station_id", ASCENDING), ("detected_at", DESCENDING)], name="station_id_detected_at_desc"
    )


def serialize_detection_summary(rows: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    last_detected_at: datetime | None = None
    for row in rows:
        by_type[row["_id"]["detection_type"]] = row["count"]
        # Older documents may have stored an ISO string, while current
        # documents store a BSON datetime. Normalize every value before
        # ordering so BSON type precedence cannot choose the wrong timestamp.
        values = row.get("detected_at_values", [row.get("last_detected_at")])
        for value in values:
            detected_at = normalize_detected_at(value)
            if detected_at is not None and (
                last_detected_at is None or detected_at > last_detected_at
            ):
                last_detected_at = detected_at
    return {
        "total": sum(by_type.values()),
        "by_type": by_type,
        "timestamp": last_detected_at.isoformat() if last_detected_at else None,
    }


def normalize_detected_at(value: object) -> datetime | None:
    """Return an aware UTC datetime from legacy or current MongoDB values."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    # Legacy naive datetimes have no timezone metadata. Treat them as UTC,
    # matching MongoDB's UTC datetime storage convention.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def detection_summary_for_stations(station_id: int | None = None) -> dict[int, dict]:
    pipeline = []
    if station_id is not None:
        pipeline.append({"$match": {"station_id": station_id}})
    pipeline.append({"$group": {
        "_id": {"station_id": "$station_id", "detection_type": "$detection_type"},
        "count": {"$sum": 1},
        "detected_at_values": {"$push": "$detected_at"},
    }})
    grouped: dict[int, list[dict]] = {}
    for row in detection_events_collection.aggregate(pipeline):
        grouped.setdefault(row["_id"]["station_id"], []).append(row)
    return {key: serialize_detection_summary(value) for key, value in grouped.items()}


@app.post("/api/stations")
def create_station(station: dict):
    station_id = station.get("station_id")
    if not isinstance(station_id, int) or station_id <= 0:
        raise HTTPException(status_code=422, detail="station_id must be a positive integer")
    if stations_collection.find_one({"station_id": station_id}) is not None:
        raise HTTPException(status_code=409, detail="Station with this station_id already exists")
    result = stations_collection.insert_one(station)
    return {"message": "Station created successfully", "id": str(result.inserted_id)}


@app.get("/api/stations")
def get_stations():
    summaries = detection_summary_for_stations()
    result = []
    for station in stations_collection.find():
        summary = summaries.get(station["station_id"], {"total": 0, "by_type": {}, "timestamp": None})
        result.append({
            "station_id": station["station_id"],
            "location": station.get("location"),
            "administrative": station.get("administrative"),
            "detections": summary["total"],
            "detection_summary": summary,
        })
    return result


@app.delete("/api/stations/{station_id}")
def delete_station(station_id: int):
    result = stations_collection.delete_one({"station_id": station_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Station not found")
    return {"message": "Station deleted successfully"}


@app.post("/api/detections", status_code=201)
def ingest_detection(payload: DetectionPayload):
    """Armazena um cruzamento detectado pela estação embarcada."""
    if stations_collection.find_one({"station_id": payload.station_id}) is None:
        raise HTTPException(status_code=404, detail="Station not found")
    try:
        result = detection_events_collection.insert_one(payload.model_dump())
    except DuplicateKeyError as error:
        raise HTTPException(status_code=409, detail="Detection event already exists") from error
    return {
        "message": "Detection ingested successfully", "id": str(result.inserted_id),
        "event_id": payload.event_id, "station_id": payload.station_id,
    }


@app.get("/api/stations/{station_id}/detections")
def get_station_detections(station_id: int):
    if stations_collection.find_one({"station_id": station_id}) is None:
        raise HTTPException(status_code=404, detail="Station not found")
    summary = detection_summary_for_stations(station_id).get(
        station_id, {"total": 0, "by_type": {}, "timestamp": None}
    )
    return {"station_id": station_id, **summary}
