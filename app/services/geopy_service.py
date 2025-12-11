from geopy.geocoders import Nominatim
from math import radians, sin, cos, asin, sqrt

geolocator = Nominatim(user_agent="foodfinder")


def geocode_text_location(text: str):
    """
    Convert typed location name → (lat, lng).
    Returns (None, None) if not found.
    """
    try:
        result = geolocator.geocode(text)
        if not result:
            return None, None
        return float(result.latitude), float(result.longitude)
    except Exception:
        return None, None


def distance_meters(lat1, lon1, lat2, lon2):
    """Haversine formula → distance in meters."""
    if None in (lat1, lon1, lat2, lon2):
        return None

    R = 6371000.0  # meters

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(
        dlon / 2
    ) ** 2
    c = 2 * asin(sqrt(a))

    return R * c
