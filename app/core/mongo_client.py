from pymongo import MongoClient
from app.core.config import settings

client = MongoClient(settings.MONGODB_URI)
db = client[settings.MONGO_DB_NAME]

def save_query_log(log: dict):
    try:
        db.query_logs.insert_one(log)
    except Exception as e:
        # production: use structured logging
        print("Mongo save failed:", e)
