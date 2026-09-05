from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017/")

db = client["aquamonitor"]

stations = db["stations"]


for station in stations.find():
    print(station)