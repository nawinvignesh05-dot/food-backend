# backend/app/services/scoring_pipeline.py
from typing import Dict, Any, List
from app.services.scoring_service import (
    compute_score,
    cuisine_match_score,
    style_score_fn,
    normalize_popularity,
    distance_score,
    budget_similarity,
    avoid_penalty,
    dish_boost,
    mood_boost,
    classify_cuisine_relation,
    WEIGHTS,
    adjust_dynamic_weights,
)

# -------------------------------------------------------------------
# STRICT VEG CHECK – based ONLY on CSV cuisine/category (your request)
# -------------------------------------------------------------------
def _is_veg_place(place: dict) -> bool:
    cuisine_text = (place.get("cuisine") or "").lower()
    category_text = (place.get("category") or "").lower()
    combined = f"{cuisine_text} {category_text}"
    return "vegetarian" in combined

# -------------------------------------------------------------------
# NORMAL EXPLANATION ENGINE (unchanged)
# -------------------------------------------------------------------
def _describe_top_factors(attrs, place, contributions):
    parts: List[str] = []
    c_cuisine = contributions.get("cuisine", 0.0)
    c_style = contributions.get("style", 0.0)
    c_pop = contributions.get("popularity", 0.0)
    c_dist = contributions.get("distance", 0.0)
    c_budget = contributions.get("budget", 0.0)
    c_dish = contributions.get("dish", 0.0)
    c_mood = contributions.get("mood", 0.0)

    user_budget = attrs.get("budget")
    price_level = place.get("price_level")

    if c_budget >= 0.05:
        if user_budget is not None and price_level is not None:
            try:
                b = float(user_budget)
                p = float(price_level)
                if p <= b:
                    parts.append(f"Works well within your budget (around ₹{int(b)}).")
                elif p <= 1.3 * b:
                    parts.append("Slightly above your budget but still fairly affordable.")
                else:
                    parts.append("Costs more than you planned, but recommended for other reasons.")
            except Exception:
                parts.append("A good fit for what you want to spend.")
        else:
            parts.append("A good fit for your budget preference.")

    dist = place.get("distance_m")
    if dist is not None and c_dist >= 0.05:
        km = dist / 1000
        if km <= 0.5:
            parts.append("Super close — just a short walk away")
        elif km <= 1.5:
            parts.append(f"Very close at about {km:.1f} km")
        elif km <= 3:
            parts.append(f"Nearby at around {km:.1f} km")
        else:
            parts.append(f"About {km:.1f} km away")

    pop = place.get("popularity")
    if pop and c_pop >= 0.05:
        if pop >= 4.5:
            parts.append("Extremely popular — highly rated by customers")
        elif pop >= 4.0:
            parts.append("Well-loved place with great reviews")
        elif pop >= 3.5:
            parts.append("Generally well-rated by visitors")

    cuisine = attrs.get("cuisine") or attrs.get("inferred_cuisine_from_dish")
    if cuisine and c_cuisine >= 0.05:
        relation = contributions.get("cuisine_relation")
        if relation == "strong":
            parts.append(f"Perfect match for your **{cuisine}** preference")
        elif relation == "weak":
            parts.append(f"Close match to your preferred **{cuisine}** cuisine family")

    styles = attrs.get("food_style")
    if styles:
        if isinstance(styles, str):
            styles = [styles]
        style_str = ", ".join(styles)
        if c_style >= 0.05:
            parts.append(f"Matches your request for something **{style_str}**")

    if attrs.get("dish") and c_dish > 0.0:
        parts.append(f"Good choice if you're craving **{attrs['dish']}**")

    mood = attrs.get("mood")
    if mood and c_mood > 0.0:
        parts.append(f"Fits your mood for **{mood}** food")

    if not parts:
        parts.append("Good overall match based on your preferences")
    return ". ".join(parts)

# -------------------------------------------------------------------
# RANKING + FALLBACK LOGIC (FULLY RESTORED)
# -------------------------------------------------------------------
def rank_places(attrs: Dict[str, Any], places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    strong_matches: List[Dict[str, Any]] = []
    weak_matches: List[Dict[str, Any]] = []
    neutral: List[Dict[str, Any]] = []

    user_has_specific_preference = bool(
        attrs.get("cuisine")
        or attrs.get("inferred_cuisine_from_dish")
        or attrs.get("dish")
    )

    avoid_cuisines = attrs.get("avoid_cuisine") or []
    if isinstance(avoid_cuisines, str):
        avoid_cuisines = [avoid_cuisines]

    veg_only = attrs.get("veg_only", False)
    max_dist = attrs.get("max_distance_m")

    # ----------------------------
    # STRICT VEG + DIST FILTERING
    # ----------------------------
    filtered_places = []
    for p in places:
        if veg_only and not _is_veg_place(p):
            continue
        if max_dist is not None:
            dist = p.get("distance_m")
            if dist is not None and dist > max_dist:
                continue
        filtered_places.append(p)
    places = filtered_places

    # ----------------------------
    # GROUPING
    # ----------------------------
    for p in places:
        category = (p.get("category") or "").lower()
        if any(ac.lower() in category for ac in avoid_cuisines):
            continue

        if user_has_specific_preference:
            rel = classify_cuisine_relation(attrs, p)
            if rel == "strong":
                strong_matches.append(p)
            elif rel == "weak":
                weak_matches.append(p)
            else:
                neutral.append(p)
        else:
            neutral.append(p)

    # ----------------------------
    # SELECT CANDIDATES
    # ----------------------------
    if user_has_specific_preference:
        if strong_matches:
            candidates = strong_matches
        elif weak_matches:
            candidates = weak_matches
        else:
            candidates = neutral
    else:
        candidates = neutral

    # ----------------------------
    # RESTORE FALLBACK LOGIC
    # ----------------------------
    requested_cuisine = attrs.get("cuisine") or attrs.get("inferred_cuisine_from_dish")
    requested_dish = attrs.get("dish")
    fallback_type = None
    dish_fallback = False

    # CUSINE FALLBACK
    if requested_cuisine and candidates:
        token = str(requested_cuisine).lower()
        found = False
        for p in candidates:
            if token in (p.get("category") or "").lower() or token in (p.get("cuisine") or "").lower():
                found = True
                break
        if not found:
            fallback_type = "cuisine_family_fallback"

    # DISH FALLBACK
    if requested_dish and candidates:
        dish_tokens = (
            [str(d).lower() for d in requested_dish]
            if isinstance(requested_dish, list)
            else [requested_dish.lower()]
        )
        found = False
        for p in candidates:
            text = " ".join([
                p.get("name") or "",
                p.get("category") or "",
                p.get("tags") or "",
            ]).lower()
            if any(d in text for d in dish_tokens):
                found = True
                break
        if not found:
            dish_fallback = True

    attrs["_fallback_type"] = fallback_type
    attrs["_dish_fallback"] = dish_fallback

    # ----------------------------
    # SCORING
    # ----------------------------
    ranked = []
    w = adjust_dynamic_weights(attrs, WEIGHTS)
    for p in candidates:
        c = cuisine_match_score(attrs, p)
        s = style_score_fn(attrs, p)
        pop = normalize_popularity(p.get("popularity"))
        dist = distance_score(p.get("distance_m"))
        bud = budget_similarity(attrs.get("budget"), p.get("price_level"))
        penalty = avoid_penalty(attrs, p)
        dish_extra = dish_boost(attrs, p)
        mood_extra = mood_boost(attrs, p)

        contributions = {
            "cuisine": w["cuisine_match"] * c,
            "style": w["style_match"] * s,
            "popularity": w["popularity"] * pop,
            "distance": w["distance"] * dist,
            "budget": w["budget"] * bud,
            "dish": dish_extra,
            "mood": mood_extra,
            "penalty": penalty,
            "cuisine_relation": classify_cuisine_relation(attrs, p),
        }

        score = compute_score(attrs, p)
        reason = _describe_top_factors(attrs, p, contributions)
        p["score"] = score
        p["reason"] = reason
        ranked.append(p)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked