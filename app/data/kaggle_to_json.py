"""
kaggle_to_json.py (UPDATED WITH REVIEW SUPPORT)
------------------------------------------------
Adds support for a `reviews` column while keeping ALL previous logic unchanged.
"""

import csv
import json
import os
from typing import List, Dict, Any, Optional, Set

# ---------- Paths ---------- #

BASE_DIR = os.path.dirname(__file__)  # .../backend/app/data
CSV_PATH = os.path.join(BASE_DIR, "zomato_restaurants.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "restaurants_india.json")

# ---------- Cuisine → style tags mapping ---------- #

CUISINE_STYLE_MAP: Dict[str, List[str]] = {
    "south indian": ["soft", "light", "comfort"],
    "udupi": ["soft", "light"],
    "andhra": ["spicy"],
    "chettinad": ["spicy"],
    "kerala": ["soft", "comfort", "coastal"],
    "mangalorean": ["coastal", "spicy"],
    "north indian": ["spicy", "heavy"],
    "punjabi": ["spicy", "heavy"],
    "mughlai": ["rich", "heavy"],
    "indian": ["spicy", "comfort"],
    "chinese": ["spicy", "oily"],
    "indo-chinese": ["spicy", "oily"],
    "italian": ["cheesy"],
    "pizza": ["cheesy", "crunchy"],
    "pasta": ["cheesy", "creamy"],
    "fast food": ["crunchy", "heavy", "oily"],
    "burger": ["crunchy", "heavy"],
    "shawarma": ["spicy"],
    "dessert": ["sweet"],
    "bakery": ["sweet"],
    "ice cream": ["sweet", "cold"],
    "salad": ["light", "healthy"],
    "healthy": ["light", "healthy"],
}


def _infer_food_style_from_cuisines(cuisines_str: Optional[str]) -> List[str]:
    if not cuisines_str:
        return []
    styles: Set[str] = set()
    lower = cuisines_str.lower()
    parts = [p.strip() for p in lower.split(",") if p.strip()]

    for p in parts:
        for key, tags in CUISINE_STYLE_MAP.items():
            if key in p:
                for t in tags:
                    styles.add(t)

    return sorted(list(styles))


def _find_first_existing(fieldnames: List[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in fieldnames:
            return c
    return None


def _parse_review_list(value: str) -> List[str]:
    """
    Convert the string representation of a Python list into a real list.
    Example stored in CSV:
        "['Good food', 'Loved it', 'Amazing']"
    """
    if not value:
        return []
    try:
        cleaned = value.strip()
        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]  # remove brackets
        if not cleaned:
            return []
        raw_parts = cleaned.split("',")
        reviews = []
        for part in raw_parts:
            part = part.strip().strip("'").strip('"').strip()
            if part:
                reviews.append(part)
        return reviews
    except Exception:
        return []


def convert():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV not found at {CSV_PATH}")

    print(f"🔄 Loading CSV from: {CSV_PATH}")

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        # ------- Column Mapping (unchanged logic) -------
        name_col = _find_first_existing(fieldnames, ["Restaurant Name", "name", "Name", "restaurant_name"])
        cuisines_col = _find_first_existing(fieldnames, ["Cuisines", "cuisines", "Cuisine"])
        country_col = _find_first_existing(fieldnames, ["Country", "country", "Country Name"])
        country_code_col = _find_first_existing(fieldnames, ["Country Code", "country_code", "countryCode"])
        rating_col = _find_first_existing(fieldnames, ["Aggregate rating", "aggregate_rating", "Rating", "rating"])
        cost_col = _find_first_existing(fieldnames, ["Average Cost for two", "average_cost_for_two", "Price range", "price_range"])
        lat_col = _find_first_existing(fieldnames, ["Latitude", "latitude", "lat"])
        lng_col = _find_first_existing(fieldnames, ["Longitude", "longitude", "lng", "Longtitude"])
        address_col = _find_first_existing(fieldnames, ["Address", "address", "Locality Verbose", "Locality"])
        city_col = _find_first_existing(fieldnames, ["City", "city"])

        # 👉 NEW review column
        reviews_col = _find_first_existing(fieldnames, ["reviews", "Reviews", "review_list", "Review List"])

        print("📌 Using column mapping:")
        print(f"  name       -> {name_col}")
        print(f"  cuisines   -> {cuisines_col}")
        print(f"  country    -> {country_col or country_code_col}")
        print(f"  rating     -> {rating_col}")
        print(f"  cost       -> {cost_col}")
        print(f"  latitude   -> {lat_col}")
        print(f"  longitude  -> {lng_col}")
        print(f"  address    -> {address_col}")
        print(f"  city       -> {city_col}")
        print(f"  reviews    -> {reviews_col}")

        results: List[Dict[str, Any]] = []
        row_idx = 0

        for row in reader:
            row_idx += 1

            # -------- India filter -------- #
            in_india = False
            if country_col and row.get(country_col):
                if "india" in str(row[country_col]).lower():
                    in_india = True
            elif country_code_col and row.get(country_code_col):
                if str(row[country_code_col]).strip() == "1":
                    in_india = True

            if not in_india:
                continue

            # -------- Core fields -------- #
            name = (row.get(name_col) or "").strip()
            if not name:
                continue

            cuisines = (row.get(cuisines_col) or "").strip()
            cuisines_lower = cuisines.lower()
            primary_category = cuisines.split(",")[0].strip().lower() if cuisines else None

            # popularity / rating
            popularity = 0.0
            if rating_col and row.get(rating_col):
                try:
                    popularity = float(str(row[rating_col]).strip() or 0.0)
                except Exception:
                    popularity = 0.0

            # budget
            budget: Optional[int] = None
            if cost_col and row.get(cost_col):
                try:
                    budget = int(float(str(row[cost_col]).replace(",", "").strip()))
                except Exception:
                    budget = None

            # coordinates
            lat = None
            lng = None
            try:
                if lat_col and row.get(lat_col):
                    lat = float(str(row[lat_col]).strip())
                if lng_col and row.get(lng_col):
                    lng = float(str(row[lng_col]).strip())
            except Exception:
                lat = None
                lng = None

            address = (row.get(address_col) or "").strip() if address_col else None
            city = (row.get(city_col) or "").strip() if city_col else None

            # food styles
            food_style = _infer_food_style_from_cuisines(cuisines_lower)

            # 👉 NEW: parse reviews
            reviews = []
            if reviews_col and row.get(reviews_col):
                reviews = _parse_review_list(row[reviews_col])

            item = {
                "place_id": f"rest_{row_idx}",
                "name": name,
                "cuisine": cuisines,
                "category": primary_category,
                "popularity": popularity,
                "distance_m": None,
                "lat": lat,
                "lng": lng,
                "budget": budget,
                "food_style": food_style,
                "city": city,
                "address": address,
                "menu_link": None,
                "reviews": reviews,  # <-- NEW FIELD
            }

            results.append(item)

    print(f"✅ Filtered India rows: {len(results)}")
    print(f"💾 Writing JSON → {OUTPUT_JSON}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f_out:
        json.dump(results, f_out, ensure_ascii=False, indent=2)

    print("🎉 Done.")


if __name__ == "__main__":
    convert()