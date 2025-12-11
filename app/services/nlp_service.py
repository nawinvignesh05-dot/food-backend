# backend/app/services/nlp_service.py

from app.llm.gemini_client import parse_query_with_gemini


def _auto_detect_veg_only(user_query: str) -> bool:
    """
    Very lightweight veg-only detector from raw query text.

    Examples that should trigger:
    - "veg only"
    - "only veg"
    - "pure veg"
    - "pure-veg"
    - "vegetarian"
    - "strictly veg"
    """
    q = (user_query or "").lower()

    patterns = [
        "veg only",
        "only veg",
        "pure veg",
        "pure-veg",
        "pure vegetarian",
        "vegetarian only",
        "only vegetarian",
        "strictly veg",
        "strict veg",
        "veg restaurant",
        "veg hotel",
        "veg hotels",
        "veg food",
        "vegetarian",
    ]

    if any(pat in q for pat in patterns):
        return True

    return False


def extract_attributes(
    user_query: str,
    veg_only=None,
    user_budget=None,
    max_distance_km=None,
    user_location=None,
):
    attrs = parse_query_with_gemini(user_query) or {}
    attrs["raw_query"] = user_query

    # Ranking preferences → already extracted by Gemini prompt
    attrs["ranking_preferences"] = attrs.get("ranking_preferences", []) or []

    # --- veg_only handling (UI + query auto-detection) ---
    auto_veg = _auto_detect_veg_only(user_query)

    # Start from whatever Gemini might have (usually False/absent)
    current_flag = bool(attrs.get("veg_only", False))

    # If UI explicitly passes veg_only, that participates in OR logic
    if veg_only is not None:
        current_flag = current_flag or bool(veg_only)

    # Auto-detection from query
    if auto_veg:
        current_flag = True

    attrs["veg_only"] = current_flag

    # Explicit overrides from UI (budget / distance)
    if user_budget is not None:
        attrs["budget"] = float(user_budget)

    if max_distance_km is not None:
        attrs["max_distance_m"] = float(max_distance_km) * 1000

    if user_location:
        attrs["explicit_location_text"] = user_location

    return attrs