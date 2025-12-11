import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "food_reco_db")
    SECRET_KEY = os.getenv("SECRET_KEY", "secret")
    DEFAULT_RADIUS_METERS = int(os.getenv("DEFAULT_RADIUS_METERS", 3000))

settings = Settings()
