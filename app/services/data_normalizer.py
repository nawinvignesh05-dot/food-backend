# backend/app/services/data_normalizer.py

def normalize_foursquare_item(item):
    """
    Convert raw item (Kaggle-backed or Foursquare) to our canonical dict.

    Canonical fields:
    - place_id, name, category, cuisine, popularity, distance_m, lat, lng,
      address, price_level, tags, menu_link, city, reviews_list
    """

    # If it's *not* a real Foursquare item, treat it as our Kaggle/canonical shape
    if "fsq_id" not in item:
        cuisine = item.get("cuisine")
        category = item.get("category") or cuisine

        return {
            "place_id": item.get("place_id") or item.get("name"),
            "name": item.get("name"),
            # keep both category and original cuisine from CSV
            "category": category,
            "cuisine": cuisine,
            "popularity": item.get("popularity", 0.0),
            "distance_m": item.get("distance_m"),
            "lat": item.get("lat") or item.get("Latitude"),
            "lng": item.get("lng") or item.get("Longitude"),
            "address": item.get("address"),
            "price_level": item.get("budget") or item.get("price_level"),
            # tags: cuisine + style tags to help style_score_fn
            "tags": " ".join(
                (cuisine or "").lower().split(",")
            ) + " " + " ".join(item.get("food_style", [])),
            "menu_link": item.get("menu_link"),
            "city": item.get("city"),
            # NEW: carry reviews from Kaggle JSON
            "reviews_list": item.get("reviews_list") or item.get("reviews"),
        }

    # ---- Foursquare style (kept for future use if needed) ---- #
    canonical = {}
    canonical["place_id"] = item.get("fsq_id") or item.get("id")
    canonical["name"] = item.get("name")

    # category pick
    cats = item.get("categories") or []
    canonical["category"] = cats[0]["name"] if cats else None
    canonical["cuisine"] = item.get("cuisine")  # may or may not exist
    canonical["popularity"] = item.get("popularity") or item.get("rating") or 0

    # geocode
    geo = item.get("geocodes", {}).get("main", {})
    canonical["lat"] = geo.get("latitude")
    canonical["lng"] = geo.get("longitude")
    canonical["distance_m"] = item.get("distance") or None

    location = item.get("location", {})
    canonical["address"] = ", ".join(
        filter(
            None,
            [
                location.get("address"),
                location.get("locality"),
                location.get("region"),
            ],
        )
    )

    # price handling: Foursquare price often as 1-4
    canonical["price_level"] = item.get("price") or None

    # tags from categories/description
    canonical["tags"] = " ".join([c.get("name", "") for c in cats])
    canonical["menu_link"] = None

    # For real Foursquare items we (likely) don't have review text yet
    canonical["reviews_list"] = item.get("reviews_list") or item.get("reviews")

    return canonical