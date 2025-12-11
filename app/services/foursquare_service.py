# backend/app/services/foursquare_service.py
"""
Kaggle-based search service.

We keep the module name `foursquare_service` only to avoid changing imports,
but there is NO Foursquare API here anymore.
"""

import os
import json
from math import radians, sin, cos, asin, sqrt

# Path to your preprocessed Kaggle JSON (India-only, cleaned)
# Adjust this if your output file has a different name.
KAGGLE_JSON_PATH = os.path.join("app", "data", "restaurants_india.json")


def _haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lng points."""
    if None in (lat1, lon1, lat2, lon2):
        return None

    R = 6371000.0  # meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def _load_dataset():
    with open(KAGGLE_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def search_places(query: str, lat: float, lng: float, limit: int = 50):
    """
    Simple Kaggle-based search:
    - loads all India restaurants
    - computes distance from (lat, lng)
    - optional keyword filter on name/cuisines
    - returns top `limit` nearest matches
    """
    data = _load_dataset()
    q = (query or "").strip().lower()

    candidates = []
    for row in data:
        rlat = row.get("lat") or row.get("latitude")
        rlng = row.get("lng") or row.get("longitude")

        try:
            rlat = float(rlat)
            rlng = float(rlng)
        except Exception:
            continue

        dist_m = _haversine_m(lat, lng, rlat, rlng)
        row["distance_m"] = dist_m

        if q:
            name = str(row.get("name") or row.get("restaurant_name") or "").lower()
            cuisines = str(row.get("cuisines") or row.get("category") or "").lower()
            if (q not in name) and (q not in cuisines):
                # we still keep it, scoring will decide — or uncomment next line to make it strict
                # continue
                pass

        candidates.append(row)

    # sort by distance
    candidates = [r for r in candidates if r.get("distance_m") is not None]
    candidates.sort(key=lambda r: r["distance_m"])

    return candidates[:limit]


def get_place_details(place_id: str):
    """
    Stub kept only for compatibility. You can extend this to
    look up details from the Kaggle JSON by place_id if needed.
    """
    data = _load_dataset()
    for row in data:
        if str(row.get("place_id") or row.get("restaurant_id")) == str(place_id):
            return row
    return None
