# backend/app/api/endpoints/recommendations.py

from flask import Blueprint, request, jsonify

from app.models.request_models import RecommendRequest
from app.models.response_models import RecommendResponse, Restaurant
from app.services.response_formatter import format_recommendation_list
from app.services.nlp_service import extract_attributes
from app.services.foursquare_service import search_places
from app.services.data_normalizer import normalize_foursquare_item
from app.services.geopy_service import distance_meters, geocode_text_location
from app.services.scoring_pipeline import rank_places
from app.services.response_formatter import format_recommendation_list
# from app.llm.gemini_client import generate_final_response_with_gemini
from app.core.mongo_client import save_query_log

from app.services.review_boost_service import re_rank_with_reviews

bp = Blueprint("recommendations", __name__)

DEFAULT_RADIUS_M = 10_000   # fallback 10 km


# ---------------------------------------------
# FILTER LOGIC (unchanged)
# ---------------------------------------------
def _filter_pre_constraints(attrs, places, max_radius_m=None, veg_only=False):
    avoid = attrs.get("avoid_cuisine") or []
    if isinstance(avoid, str):
        avoid = [avoid]
    avoid = [a.lower() for a in avoid]

    filtered = []

    for p in places:

        # distance filter
        dist = p.get("distance_m")
        if max_radius_m and dist is not None:
            try:
                if float(dist) > max_radius_m:
                    continue
            except Exception:
                pass

        # avoid cuisines
        cat = (p.get("category") or "").lower()
        if any(a in cat for a in avoid):
            continue

        # veg-only filter
        if veg_only:
            tags = (p.get("tags") or "").lower()
            if (
                "veg" not in cat
                and "vegetarian" not in cat
                and "pure veg" not in tags
            ):
                continue

        filtered.append(p)

    return filtered


# ---------------------------------------------
# MAIN ENDPOINT
# ---------------------------------------------
@bp.route("/recommend", methods=["POST"])
def recommend():

    # Parse request safely
    try:
        payload = request.get_json() or {}
        req = RecommendRequest(**payload)
    except Exception as e:
        return jsonify({"error": "Invalid request", "details": str(e)}), 400

    # ---------------------------------------------------
    # 1. Determine LAT/LNG based on Option A compatibility
    # ---------------------------------------------------
    lat = req.lat
    lng = req.lng

    # CASE 2 — if user is NOT using "my location" and text is provided → backend geocodes
    if not req.use_my_location:
        if req.location_text:
            glat, glng = geocode_text_location(req.location_text)
            if glat is None or glng is None:
                return jsonify(
                    {
                        "error": "Could not geocode location",
                        "details": req.location_text,
                    }
                ), 400
            lat, lng = glat, glng

    # If still missing → reject
    if lat is None or lng is None:
        return jsonify({"error": "Latitude and longitude required"}), 400

    # ---------------------------------------------------
    # 2. Extract attributes (unchanged)
    # ---------------------------------------------------
    attrs = extract_attributes(
        user_query=req.query,
        veg_only=req.veg_only,
        user_budget=req.budget,
        max_distance_km=req.max_distance_km,
        user_location=f"{lat},{lng}",
    )

    # ---------------------------------------------------
    # 3. Determine search query (unchanged)
    # ---------------------------------------------------
    dish = attrs.get("dish")
    food_style = attrs.get("food_style")

    if isinstance(dish, str):
        search_q = dish
    elif isinstance(dish, list) and dish:
        search_q = dish[0]
    elif attrs.get("cuisine"):
        search_q = attrs["cuisine"]
    elif food_style:
        search_q = food_style[0] if isinstance(food_style, list) else food_style
    else:
        search_q = req.query

    raw_limit = max((req.limit or 10) * 5, 30)

    # ---------------------------------------------------
    # 4. Load search places + compute distances
    # ---------------------------------------------------
    try:
        raw = search_places(search_q, lat, lng, limit=raw_limit)
        items = raw if isinstance(raw, list) else raw.get("results", [])
    except Exception as e:
        return jsonify({"error": "Data load failure", "details": str(e)}), 502

    places = []
    for it in items:
        p = normalize_foursquare_item(it)

        if p.get("lat") and p.get("lng"):
            if p.get("distance_m") is None:
                p["distance_m"] = distance_meters(lat, lng, p["lat"], p["lng"])
        places.append(p)

    if not places:
        return jsonify(
            {
                "query": req.query,
                "attributes": attrs,
                "recommendations": [],
                "message": format_recommendation_list(req.query, attrs, []),
            }
        ), 200

    # ---------------------------------------------------
    # 5. Hard filtering
    # ---------------------------------------------------
    max_radius_m = (
        (req.max_distance_km * 1000)
        if req.max_distance_km
        else (req.radius or DEFAULT_RADIUS_M)
    )

    filtered = _filter_pre_constraints(
        attrs=attrs,
        places=places,
        max_radius_m=max_radius_m,
        veg_only=req.veg_only,
    )

    if not filtered:
        return jsonify(
            {
                "query": req.query,
                "attributes": attrs,
                "recommendations": [],
                "message": f"No places found within {req.max_distance_km or req.radius or 10} km.",
            }
        ), 200

    # ---------------------------------------------------
    # 6. Ranking + Review Boosting
    # ---------------------------------------------------
    ranked = rank_places(attrs, filtered)
    ranked = re_rank_with_reviews(req.query, attrs, ranked)

    # ---------------------------------------------------
    # 7. Logging (non-critical)
    # ---------------------------------------------------
    try:
        save_query_log(
            {
                "query": req.query,
                "attrs": attrs,
                "count_results": len(ranked),
            }
        )
    except Exception:
        pass

    # ---------------------------------------------------
    # 8. Final Response Build
    # ---------------------------------------------------
    top = []
    limit = req.limit or 10

    for r in ranked[:limit]:
        top.append(
            Restaurant(
                place_id=r.get("place_id"),
                name=r.get("name"),
                category=r.get("category"),
                popularity=r.get("popularity"),
                distance_m=r.get("distance_m"),
                address=r.get("address"),
                opening_hours=None,
                rating=None,
                menu_link=r.get("menu_link"),
                reason=r.get("reason"),
                score=r.get("score_with_reviews", r.get("score")),
                lat = r.get("lat"),
                lng = r.get("lng"),
            ).dict()
        )

    msg = format_recommendation_list(req.query, attrs, top)

    return jsonify(
        RecommendResponse(
            query=req.query,
            attributes=attrs,
            recommendations=top,
            message=msg,
        ).dict()
    ), 200
