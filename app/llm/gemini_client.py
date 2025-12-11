import google.generativeai as genai
import json
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

PROMPT_BASE = open("app/llm/prompts/food_extraction_prompt.txt", encoding="utf-8").read()

DEFAULT_ATTRS = {
    "mood": None,
    "cuisine": None,
    "inferred_cuisine_from_dish": None,
    "dish": None,
    "food_style": [],
    "avoid_food_style": [],
    "avoid_cuisine": [],
    "budget": None,
    "location": None,
    "meal_type": None,
    "dietary_preference": None,
    "group_size": None,
    "distance_preference": None,
    "category_hint": None,
    "ranking_preferences": [],
}

def _to_list_lower(x):
    if x is None:
        return []
    if isinstance(x, str):
        return [x.lower()]
    if isinstance(x, list):
        return [str(v).lower() for v in x if isinstance(v, (str, int, float))]
    return []

def _normalize_attrs(raw: dict) -> dict:
    data = {**DEFAULT_ATTRS, **(raw or {})}

    for key in ["mood", "cuisine", "inferred_cuisine_from_dish",
                "location", "meal_type", "dietary_preference",
                "distance_preference", "category_hint"]:
        if isinstance(data.get(key), str):
            data[key] = data[key].strip().lower()

    data["food_style"] = _to_list_lower(data.get("food_style"))
    data["avoid_food_style"] = _to_list_lower(data.get("avoid_food_style"))
    data["avoid_cuisine"] = _to_list_lower(data.get("avoid_cuisine"))

    dish = data.get("dish")
    if isinstance(dish, list):
        data["dish"] = [str(d).lower() for d in dish]
    elif isinstance(dish, str):
        data["dish"] = dish.lower()
    else:
        data["dish"] = None

    try:
        if data.get("budget") is not None:
            data["budget"] = int(float(data["budget"]))
    except Exception:
        data["budget"] = None

    try:
        if data.get("group_size") is not None:
            data["group_size"] = int(float(data["group_size"]))
    except Exception:
        data["group_size"] = None

    prefs = raw.get("ranking_preferences", [])
    if isinstance(prefs, str):
        prefs = [prefs]
    prefs = [p.lower().strip() for p in prefs]

    raw_q = (raw.get("raw_query") or "").lower()

    def negated(term):
        return (
            f"{term} doesn’t matter" in raw_q
            or f"{term} doesn't matter" in raw_q
            or f"{term} does not matter" in raw_q
            or f"i don’t care about {term}" in raw_q
            or f"i don't care about {term}" in raw_q
        )

    cleaned = []
    for p in prefs:
        if p == "distance" and not negated("distance"):
            cleaned.append(p)
        elif p == "popularity" and not negated("popularity"):
            cleaned.append(p)
        elif p == "budget":
            cleaned.append(p)
        elif p == "rating" and not negated("rating"):
            cleaned.append("popularity")

    data["ranking_preferences"] = cleaned

    return data


def parse_query_with_gemini(user_query: str) -> dict:
    full_prompt = f"""
{PROMPT_BASE}

User Query:
\"\"\"{user_query}\"\"\"

Return ONLY a valid JSON object. No extra text.
"""

    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        response = model.generate_content(full_prompt)
        text = (response.text or "").strip()

        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != -1:
            text = text[start:end]

        raw = json.loads(text)
        raw["raw_query"] = user_query
        return _normalize_attrs(raw)

    except Exception as e:
        print("Gemini parsing error:", e)
        return DEFAULT_ATTRS.copy()