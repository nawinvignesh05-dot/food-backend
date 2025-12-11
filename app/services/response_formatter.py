# backend/app/services/response_formatter.py

"""
response_formatter.py
Converts backend recommendation JSON into a natural, conversational message.
Supports:
- Mood-aware tone
- Style adjectives (soft, crunchy, cheesy, etc.)
- Contextual explanations, including cuisine/dish fallbacks.
"""

from typing import List, Dict, Any

def _select_intro(attributes: Dict[str, Any]) -> str:
    mood = (attributes.get("mood") or "").lower()
    styles = attributes.get("food_style") or []

    if mood:
        MOOD_TEMPLATES = {
            "comfort food": "Sounds like you need something warm and comforting today. Here are some cozy picks:",
            "sad": "Rough day? Here are some comforting food options to lift your mood:",
            "tired": "You must be exhausted — here are some easy, soothing meals nearby:",
            "celebration": "Nice! Here are some places perfect for a celebration:",
            "hangout": "Looking for a chill hangout spot? Try these:",
            "spicy craving": "Craving something spicy? These places should hit the spot!",
        }
        for key, text in MOOD_TEMPLATES.items():
            if key in mood:
                return text

    if styles:
        s_text = ", ".join(str(s) for s in styles)
        return f"Here are some places that match your craving for something {s_text}:"

    return "Here are some great options I found for you!"

def _build_global_explanation(attributes: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
    """
    One global explanation paragraph that:
    - Mentions veg-only if applied.
    - Explains cuisine fallback (e.g., no Kerala → show South Indian).
    - Explains dish + cuisine link (e.g., dosa → South Indian).
    - Explains dish fallback if nothing explicitly mentions the dish.
    """
    if not recommendations:
        return ""

    parts: List[str] = []

    veg_only = attributes.get("veg_only")
    raw_query = attributes.get("raw_query") or ""
    requested_cuisine = attributes.get("cuisine") or attributes.get("inferred_cuisine_from_dish")
    requested_dish = attributes.get("dish")
    inferred_cuisine = attributes.get("inferred_cuisine_from_dish")
    fallback_type = attributes.get("_fallback_type")
    dish_fallback = attributes.get("_dish_fallback")

    # Normalise dish text
    dish_text = None
    if requested_dish:
        if isinstance(requested_dish, list):
            dish_text = ", ".join(str(d) for d in requested_dish)
        else:
            dish_text = str(requested_dish)

    # Veg-only explanation
    if veg_only:
        parts.append(
            "You asked for pure vegetarian options, so I'm only showing places that look vegetarian / pure-veg."
        )

    # ---------- CASE 1 & CASE 3: Cuisine family fallback ----------
    # Example:
    #   - User asked for Kerala or Arabian
    #   - No place clearly tagged with that cuisine
    #   - We fall back to related/closest cuisine (e.g. South Indian).
    if fallback_type == "cuisine_family_fallback" and requested_cuisine:
        top_cat = (recommendations[0].get("category") or "").strip()
        if dish_text:
            # Tie cuisine fallback with the dish user asked
            if top_cat:
                parts.append(
                    f"I couldn't find restaurants clearly labelled as {requested_cuisine} "
                    f"for {dish_text}, so I'm recommending the closest matches like "
                    f"{top_cat} that should feel similar."
                )
            else:
                parts.append(
                    f"I couldn't find restaurants clearly labelled as {requested_cuisine} "
                    f"for {dish_text}, so I'm recommending the closest cuisine matches instead."
                )
        else:
            # Original cuisine fallback behaviour
            if top_cat:
                parts.append(
                    f"I couldn't find restaurants clearly labelled as {requested_cuisine} nearby, "
                    f"so I'm recommending the closest matches like {top_cat} that should feel similar."
                )
            else:
                parts.append(
                    f"I couldn't find restaurants clearly labelled as {requested_cuisine} nearby, "
                    "so I'm recommending the closest cuisine matches instead."
                )

    # ---------- CASE 2: Dish → inferred cuisine (e.g. dosa → South Indian) ----------
    # Only when we are NOT already in a cuisine-family fallback.
    elif dish_text and inferred_cuisine:
        parts.append(
            f"Since {dish_text} is usually a {inferred_cuisine} dish, "
            f"I'm prioritising strong {inferred_cuisine} restaurants that are likely to serve it."
        )

    # ---------- Dish fallback explanation ----------
    # If we still couldn't find places that explicitly mention the dish by name.
    if dish_fallback and not (fallback_type == "cuisine_family_fallback" and dish_text and inferred_cuisine):
        # If we already know an inferred cuisine for the dish, mention that too.
        if dish_text and inferred_cuisine:
            parts.append(
                f"I couldn't find places that explicitly mention {dish_text}, "
                f"so I'm showing well-rated {inferred_cuisine} options where you're likely to get it."
            )
        else:
            # Generic dish fallback (no inferred cuisine info)
            dish_label = dish_text or raw_query
            parts.append(
                f"I also couldn't find places that explicitly mention {dish_label}, "
                "so these are the best matches based on cuisine, style and reviews."
            )

    if not parts:
        return ""

    return " ".join(parts)

def _build_reason_phrase(attrs: Dict[str, Any], place: Dict[str, Any]) -> str:
    """
    Convert backend's technical 'reason' into human-style sentences.
    Backend reason is already helpful, but we wrap it with context templates.
    """
    reason = place.get("reason") or ""
    name = place["name"]

    cuisine = attrs.get("cuisine") or attrs.get("inferred_cuisine_from_dish")
    dish = attrs.get("dish")
    styles = attrs.get("food_style") or []
    avoid = attrs.get("avoid_food_style") or []
    budget = attrs.get("budget")

    phrases: List[str] = []

    # Dish context
    if dish:
        if isinstance(dish, list):
            dish_text = ", ".join(str(d) for d in dish)
        else:
            dish_text = str(dish)
        phrases.append(f"{name} is a good pick if you're craving {dish_text}.")

    # Cuisine context
    if cuisine:
        phrases.append(f"Fits your preference for {cuisine} food.")

    # Style context
    if styles:
        st = ", ".join(styles)
        phrases.append(f"Matches your taste for something {st}.")

    # Avoid styles
    if avoid:
        av = ", ".join(avoid)
        phrases.append(f"Avoids foods that are {av}, just like you wanted.")

    # Budget context
    if budget:
        phrases.append(f"Works well within your budget (around ₹{budget}).")

    # Distance context
    dist = place.get("distance_m")
    if dist is not None:
        km = dist / 1000
        if km <= 0.7:
            phrases.append(f"Super close — only {km:.1f} km away.")
        else:
            phrases.append(f"Not too far at about {km:.1f} km away.")

    # Popularity context
    if place.get("popularity"):
        phrases.append(f"People love this place — rated {place['popularity']}/5.")

    # Always include backend reason as supporting detail
    if reason:
        phrases.append(f"({reason})")

    return " ".join(phrases)

def generate_user_message(query: str, attributes: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
    if not recommendations:
        return (
            f"Sorry, I couldn't find anything matching \"{query}\".\n"
            "Want to try changing cuisine, dish, style (soft / spicy / cheesy), or budget?"
        )

    intro = _select_intro(attributes)
    message = f"🍽️ {intro}\n\n"

    # Global explanation at the top (veg, fallbacks, dish→cuisine, etc.)
    global_explanation = _build_global_explanation(attributes, recommendations)
    if global_explanation:
        message += global_explanation + "\n\n"

    for i, r in enumerate(recommendations, start=1):
        dist_km = (r.get("distance_m") or 0) / 1000
        reason_text = _build_reason_phrase(attributes, r)

        message += (
            f"⭐ {i}. {r['name']}\n"
            f"- 🥗 Category: {r.get('category', 'N/A')}\n"
            f"- 📍 {dist_km:.1f} km away\n"
            f"- ⭐ {r.get('popularity', 'N/A')}/5 rating\n"
            f"- 💡 Why this place? {reason_text}\n\n"
        )

    message += (
        "---\n"
        "Want something spicier, lighter, cheaper, only-veg, or more like street food? "
        "Tell me and I’ll refine the list! 😊"
    )

    return message

def format_recommendation_list(query: str, attributes: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
    return generate_user_message(query, attributes, recommendations)