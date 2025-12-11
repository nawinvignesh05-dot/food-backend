# backend/app/services/scoring_service.py

import math
from typing import Dict, Any, List

# ---------------- Weights ---------------- #

WEIGHTS = {
    "cuisine_match": 0.35,   # strong impact
    "style_match": 0.15,
    "popularity": 0.20,
    "distance": 0.15,
    "budget": 0.10,
    # dish_boost and mood/style boosts are added separately
}

# Dish → cuisine/category hints (helps dish_boost)
DISH_HINTS = {
    "dosa": {"cuisine": "south indian"},
    "idli": {"cuisine": "south indian"},
    "vada": {"cuisine": "south indian"},
    "pongal": {"cuisine": "south indian"},
    "biryani": {"cuisine": "indian"},
    "naan": {"cuisine": "north indian"},
    "butter naan": {"cuisine": "north indian"},
    "butter chicken": {"cuisine": "north indian"},
    "fried rice": {"cuisine": "chinese"},
    "manchurian": {"cuisine": "chinese"},
    "noodles": {"cuisine": "chinese"},
    "pizza": {"cuisine": "italian"},
    "pasta": {"cuisine": "italian"},
    "burger": {"category": "fast food"},
    "ice cream": {"category": "dessert"},
    "brownie": {"category": "dessert"},
    "litti": {"cuisine": "bihari"},
    "litti chokha": {"cuisine": "bihari"},
    "dal bati": {"cuisine": "rajasthani"},
    "misal pav": {"cuisine": "maharashtrian"},
}

# Simple cuisine families for regional mapping
CUISINE_FAMILIES = {
    "south indian": ["south indian", "andhra", "telangana", "tamil", "kerala", "karnataka", "udupi", "chettinad"],
    "north indian": ["north indian", "punjabi", "mughlai", "awadhi", "bihari"],
    "east indian": ["bengali", "odia", "oriya", "assamese"],
    "west indian": ["rajasthani", "gujarati", "maharashtrian", "goan"],
    "coastal": ["mangalorean", "konkan", "seafood"],
    "generic_indian": ["indian"],
}

STATE_FAMILY = {
    "andhra": "south indian",
    "telangana": "south indian",
    "tamil nadu": "south indian",
    "kerala": "south indian",
    "karnataka": "south indian",
    "punjab": "north indian",
    "uttar pradesh": "north indian",
    "bihar": "north indian",
    "delhi": "north indian",
    "haryana": "north indian",
    "rajasthan": "west indian",
    "gujarat": "west indian",
    "maharashtra": "west indian",
    "goa": "west indian",
    "west bengal": "east indian",
    "odisha": "east indian",
    "orissa": "east indian",
    "assam": "east indian",
}

# Style → implied cuisines/categories
STYLE_HINTS = {
    "soft": {"cuisines": ["south indian"], "categories": []},
    "light": {"cuisines": ["south indian", "healthy"], "categories": []},
    "comfort": {"cuisines": ["south indian", "indian"], "categories": []},
    "crunchy": {"cuisines": [], "categories": ["fast food"]},
    "crispy": {"cuisines": [], "categories": ["fast food", "chinese"]},
    "cheesy": {"cuisines": ["italian"], "categories": ["fast food"]},
    "spicy": {"cuisines": ["andhra", "chettinad", "indo-chinese", "north indian"], "categories": []},
    "sweet": {"cuisines": [], "categories": ["dessert", "bakery"]},
    "healthy": {"cuisines": [], "categories": ["salad", "healthy food"]},
}


def adjust_dynamic_weights(attrs: Dict[str, Any], base: Dict[str, float]) -> Dict[str, float]:
    """
    Dynamically modify scoring weights based on:
    - ranking_preferences (primary)
    - distance_preference / raw_query / budget / cuisine / food_style (fallback)
    """

    # Start from base
    w = base.copy()

    # ---- 1) Use ranking_preferences if present ----
    prefs = attrs.get("ranking_preferences") or []
    if isinstance(prefs, str):
        prefs = [prefs]
    prefs = [str(p).lower() for p in prefs]
    prefs = [p for p in prefs if p]  # drop empty strings

    if prefs:
        keys = ["cuisine_match", "style_match", "popularity", "distance", "budget"]
        # very small baseline so things we don't care about almost vanish
        w = {k: 0.02 for k in keys}

        # Single-primary-factor case: e.g. ["budget"]
        if len(prefs) == 1:
            p0 = prefs[0]
            if p0 == "budget":
                w["budget"] = 0.9
            elif p0 == "distance":
                w["distance"] = 0.9
            elif p0 in ("popularity", "rating"):
                w["popularity"] = 0.9
            elif p0 == "cuisine":
                w["cuisine_match"] = 0.9
            elif p0 == "style":
                w["style_match"] = 0.9
        else:
            # Multi-factor: give each requested factor a big bump
            for p in prefs:
                if p == "budget":
                    w["budget"] += 0.4
                elif p == "distance":
                    w["distance"] += 0.4
                elif p in ("popularity", "rating"):
                    w["popularity"] += 0.4
                elif p == "cuisine":
                    w["cuisine_match"] += 0.4
                elif p == "style":
                    w["style_match"] += 0.4

        # Normalize so they sum to 1.0
        total = sum(w.values()) or 1.0
        for k in w:
            w[k] /= total

        return w

    # ---- 2) Fallback to old behaviour (no ranking_preferences) ----

    # Distance emphasis
    dist_pref = attrs.get("distance_preference")
    if dist_pref and ("near" in dist_pref or "nearby" in dist_pref):
        w["distance"] = 0.60
        w["popularity"] = 0.15
        w["cuisine_match"] = 0.10
        w["style_match"] = 0.05
        w["budget"] = 0.10
        return w

    # Popularity emphasis (from raw_query)
    query_text = str(attrs.get("raw_query", "")).lower()
    if "popular" in query_text or "high rating" in query_text or "top rated" in query_text:
        w["popularity"] = 0.50
        w["distance"] = 0.20
        w["cuisine_match"] = 0.15
        w["style_match"] = 0.05
        w["budget"] = 0.10
        return w

    # Budget emphasis
    budget = attrs.get("budget")
    if budget:
        w["budget"] = 0.50
        w["distance"] = 0.20
        w["cuisine_match"] = 0.15
        w["style_match"] = 0.05
        w["popularity"] = 0.10
        return w

    # Cuisine emphasis
    if attrs.get("cuisine") or attrs.get("inferred_cuisine_from_dish"):
        w["cuisine_match"] = 0.50
        w["distance"] = 0.20
        w["popularity"] = 0.15
        w["style_match"] = 0.10
        w["budget"] = 0.05
        return w

    # Style emphasis
    if attrs.get("food_style"):
        w["style_match"] = 0.40
        w["cuisine_match"] = 0.25
        w["distance"] = 0.15
        w["popularity"] = 0.10
        w["budget"] = 0.10
        return w

    # No special preference → base weights
    return w


def normalize_popularity(raw):
    """Assume rating scale 0–5 or 0–10, normalize to 0–1."""
    if raw is None:
        return 0.0
    try:
        val = float(raw)
    except Exception:
        return 0.0

    if val <= 5:
        return max(0.0, min(val / 5.0, 1.0))
    return max(0.0, min(val / 10.0, 1.0))


def distance_score(dist_m):
    """Closer is better; 0m → 1.0, 5km → ~0.0."""
    if dist_m is None:
        return 0.5  # neutral if unknown
    try:
        d = float(dist_m)
    except Exception:
        return 0.5
    if d <= 0:
        return 1.0
    # Exponential decay to avoid going negative
    return math.exp(-d / 4000.0)  # 4km characteristic length


def budget_similarity(user_budget, place_price):
    """1.0 if within budget, taper off if more expensive."""
    if user_budget is None or place_price is None:
        return 0.5
    try:
        b = float(user_budget)
        p = float(place_price)
    except Exception:
        return 0.5

    if p <= b:
        return 1.0
    if p <= 1.3 * b:
        return 0.7
    if p <= 1.6 * b:
        return 0.4
    return 0.1


def _get_family(label: str) -> str:
    """Map a cuisine/region string to a coarse family name."""
    if not label:
        return ""
    txt = label.lower()
    # Check state mapping
    if txt in STATE_FAMILY:
        return STATE_FAMILY[txt]

    # Check family groups
    for fam, vals in CUISINE_FAMILIES.items():
        for v in vals:
            if v in txt:
                return fam

    # generic indian fallback
    if "indian" in txt:
        return "generic_indian"

    return ""


def classify_cuisine_relation(attrs: Dict[str, Any], place: Dict[str, Any]) -> str:
    """
    Return one of: "strong", "weak", "none"
    Used for semi-strict filtering + explanation.
    """
    user_cuisine = attrs.get("cuisine") or attrs.get("inferred_cuisine_from_dish")
    if not user_cuisine:
        return "none"

    uc = str(user_cuisine).lower()
    cat = (place.get("category") or "").lower()
    cuisine_text = (place.get("category") or place.get("cuisine") or "").lower()

    if not cuisine_text and not cat:
        return "none"

    # Direct match: exact token
    if uc in cuisine_text:
        return "strong"

    # Family-based mapping
    user_family = _get_family(uc)
    place_family = _get_family(cuisine_text)
    if user_family and place_family:
        if user_family == place_family:
            return "strong"
        # e.g. south-indian vs generic-indian
        if (user_family == "south indian" and place_family == "generic_indian") or \
           (user_family == "generic_indian" and place_family in ("south indian", "north indian")):
            return "weak"

    return "none"


def cuisine_match_score(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """
    Numeric cuisine match score using the relation classification.
    strong → 1.0, weak → 0.6, none → 0.0
    If user didn't specify any cuisine/dish → neutral 0.5
    """
    user_cuisine = attrs.get("cuisine") or attrs.get("inferred_cuisine_from_dish")
    if not user_cuisine:
        return 0.5  # neutral

    relation = classify_cuisine_relation(attrs, place)
    if relation == "strong":
        return 1.0
    if relation == "weak":
        return 0.6
    return 0.0


def style_score_fn(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """
    Match of food_style adjectives (spicy, cheesy, sweet, soft...).
    Uses tags from place["tags"].
    """
    desired = attrs.get("food_style") or []
    if isinstance(desired, str):
        desired = [desired]

    tags = (place.get("tags") or "").lower()
    if not desired or not tags:
        return 0.0

    matches = 0
    for s in desired:
        s_low = str(s).lower()
        if s_low in tags:
            matches += 1
    if not desired:
        return 0.0
    return matches / len(desired)


def avoid_penalty(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """Negative score for cuisines/styles the user wants to avoid."""
    score = 0.0
    avoid_styles = attrs.get("avoid_food_style") or []
    avoid_cuisines = attrs.get("avoid_cuisine") or []

    if isinstance(avoid_styles, str):
        avoid_styles = [avoid_styles]
    if isinstance(avoid_cuisines, str):
        avoid_cuisines = [avoid_cuisines]

    tags = (place.get("tags") or "").lower()
    cat = (place.get("category") or "").lower()

    for s in avoid_styles:
        if str(s).lower() in tags:
            score -= 0.4

    for c in avoid_cuisines:
        if str(c).lower() in cat:
            score -= 0.4

    return score


def dish_boost(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """
    Extra boost for restaurants that match the requested dish's cuisine/category.
    Handles dish as string or list.
    For semi-strict behavior:
    - strong cuisine relation → full boost
    - weak relation → smaller boost
    - none → no boost
    """
    dish = attrs.get("dish")
    if not dish:
        return 0.0

    # Normalize dish into a list of lower-case strings
    if isinstance(dish, str):
        dishes = [dish.lower()]
    elif isinstance(dish, list):
        dishes = [str(d).lower() for d in dish if isinstance(d, (str, int, float))]
    else:
        return 0.0

    place_cat = (place.get("category") or "").lower()
    boost = 0.0

    relation = classify_cuisine_relation(attrs, place)

    for d in dishes:
        hint = DISH_HINTS.get(d)
        if not hint:
            continue

        if "cuisine" in hint:
            if hint["cuisine"] in place_cat:
                if relation == "strong":
                    boost = max(boost, 0.25)
                elif relation == "weak":
                    boost = max(boost, 0.15)

        if "category" in hint and hint["category"] in place_cat:
            if relation == "strong":
                boost = max(boost, 0.25)
            elif relation == "weak":
                boost = max(boost, 0.15)

    if relation == "none":
        return 0.0

    return boost


def _style_inference_boost(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """
    Boost based directly on style adjectives when user only says things like:
    - soft, light → favor south indian veg / healthy
    - crunchy, crispy → favor fast food / fried
    - cheesy → italian / fast food
    """
    desired = attrs.get("food_style") or []
    if isinstance(desired, str):
        desired = [desired]

    if not desired:
        return 0.0

    cat = (place.get("category") or "").lower()
    tags = (place.get("tags") or "").lower()

    boost = 0.0

    for s in desired:
        s_low = str(s).lower()
        hint = STYLE_HINTS.get(s_low)
        if not hint:
            continue

        # cuisines
        for c in hint.get("cuisines", []):
            if c in cat or c in tags:
                boost += 0.08

        # categories
        for c in hint.get("categories", []):
            if c in cat or c in tags:
                boost += 0.08

    # clamp
    boost = max(-0.25, min(boost, 0.25))
    return boost


def mood_boost(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """
    Soft, non-strict mood effect.
    Example: comfort food → slight preference for veg / south Indian,
    slight penalty for very heavy/oily categories.
    """
    mood = attrs.get("mood")
    if not mood:
        return 0.0

    mood_text = str(mood).lower()
    cat = (place.get("category") or "").lower()
    tags = (place.get("tags") or "").lower()

    boost = 0.0

    # Comfort / rough day
    if "comfort" in mood_text or "rough" in mood_text or "bad day" in mood_text or "sad" in mood_text or "tired" in mood_text:
        # Prefer veg / south Indian style places
        if "vegetarian" in cat or "veg" in cat:
            boost += 0.18
        elif "south indian" in cat:
            boost += 0.15
        elif "indian" in cat:
            boost += 0.08

        # Light/healthy tags
        if "light" in tags or "home-style" in tags or "healthy" in tags or "soft" in tags:
            boost += 0.10

        # Slight penalty for obviously heavy/oily/fast food
        if "fast food" in cat or "chinese" in cat:
            boost -= 0.08
        if "fried" in tags or "biryani" in tags or "tandoori" in tags or "oily" in tags:
            boost -= 0.10

    # Celebration
    if "celebration" in mood_text or "party" in mood_text or "birthday" in mood_text:
        # Prefer rich/spicy/dessert
        if "mughlai" in cat or "north indian" in cat or "biryani" in tags:
            boost += 0.12
        if "dessert" in cat or "bakery" in cat or "sweet" in tags:
            boost += 0.08

    # clamp so mood doesn't dominate everything
    boost = max(-0.25, min(boost, 0.25))
    return boost


def compute_score(attrs: Dict[str, Any], place: Dict[str, Any]) -> float:
    """
    Compute final score [0, 1] combining:
    - cuisine match
    - style match
    - popularity
    - distance
    - budget match
    - dish boost (extra)
    - mood boost (extra)
    - style inference boost (extra)
    - negative penalties
    """
    c = cuisine_match_score(attrs, place)
    s = style_score_fn(attrs, place)
    p = normalize_popularity(place.get("popularity"))
    d = distance_score(place.get("distance_m"))
    b = budget_similarity(attrs.get("budget"), place.get("price_level"))
    penalty = avoid_penalty(attrs, place)
    dish_extra = dish_boost(attrs, place)
    mood_extra = mood_boost(attrs, place)
    style_inferred_extra = _style_inference_boost(attrs, place)

    w = adjust_dynamic_weights(attrs, WEIGHTS)
    base = (
        w["cuisine_match"] * c
        + w["style_match"] * s
        + w["popularity"] * p
        + w["distance"] * d
        + w["budget"] * b
    )

    final = base + dish_extra + mood_extra + style_inferred_extra + penalty
    final = max(0.0, min(final, 1.0))
    return final