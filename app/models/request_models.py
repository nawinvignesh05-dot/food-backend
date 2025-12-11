# backend/app/models/request_models.py
from pydantic import BaseModel
from typing import Optional

class RecommendRequest(BaseModel):
    query: str

    # Required for recommendation
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius: Optional[int] = None 
    # NEW — user‑provided inputs
    veg_only: Optional[bool] = None
    budget: Optional[float] = None
    max_distance_km: Optional[float] = None  # replaces radius
    location_text: Optional[str] = None      # geocoded when use_my_location=False
    use_my_location: Optional[bool] = None

    # Response control
    limit: Optional[int] = 10
