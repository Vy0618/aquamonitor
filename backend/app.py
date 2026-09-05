from fastapi import FastAPI, HTTPException
from  pymongo import MongoClient
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

    stations = stations_collection.find()

    result = []

    for station in stations:
        result.append({
            "station_id": station["station_id"],
            "location": station["location"],
            "detections": station["detections"]
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
# Update(não existem motivos por enquanto)
# ============================