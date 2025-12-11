from pydantic import BaseModel
from typing import List, Optional

class Restaurant(BaseModel):
    place_id: str
    name: str
    category: Optional[str]
    popularity: Optional[float]
    distance_m: Optional[float]
    address: Optional[str]
    opening_hours: Optional[str]
    rating: Optional[float]
    menu_link: Optional[str]
    reason: Optional[str]
    score: Optional[float]
    lat: Optional[float]
    lng: Optional[float]

class RecommendResponse(BaseModel):
    query: str
    attributes: dict
    recommendations: List[Restaurant]
    message: str
