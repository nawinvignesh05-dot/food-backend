# backend/app/services/review_boost_service.py

from typing import List, Dict, Any
import re


def _flatten_reviews(place: Dict[str, Any]) -> str:
    """
    Take whatever review field exists and flatten to a single string.
    Expected:
      - place["reviews_list"] is a list of strings
      - or place["reviews"] / place["reviews_text"] as fallback
    """
    reviews = (
        place.get("reviews_list")
        or place.get("reviews")
        or place.get("reviews_text")
    )

    if isinstance(reviews, list):
        return " ".join(str(r) for r in reviews if r)
    if isinstance(reviews, str):
        return reviews
    return ""


_STOPWORDS = {
    "i", "me", "my", "we", "you", "he", "she", "they",
    "want", "need", "some", "something", "food", "place", "restaurant",
    "near", "nearby", "around", "very", "really", "just",
    "give", "get", "for", "to", "a", "an", "the", "in", "at", "of",
    "on", "with", "and", "or", "but", "too", "also", "like"
}


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    # split on non-letters/numbers
    tokens = re.split(r"[^a-z0-9]+", text)
    return [t for t in tokens if t and t not in _STOPWORDS]


def _build_query_terms(user_query: str, attrs: Dict[str, Any]) -> List[str]:
    terms = set(_tokenize(user_query))

    # enrich with structured attrs
    for key in ["cuisine", "inferred_cuisine_from_dish", "mood", "category_hint"]:
        val = attrs.get(key)
        if isinstance(val, str):
            terms.update(_tokenize(val))

    # dish can be str or list
    dish = attrs.get("dish")
    if isinstance(dish, str):
        terms.update(_tokenize(dish))
    elif isinstance(dish, list):
        for d in dish:
            terms.update(_tokenize(str(d)))

    # food_style list
    fs = attrs.get("food_style") or []
    if isinstance(fs, str):
        fs = [fs]
    for s in fs:
        terms.update(_tokenize(str(s)))

    return list(terms)


def _review_match_score(user_query: str, attrs: Dict[str, Any], reviews_text: str) -> float:
    """
    Simple local similarity: overlap between user/query terms and review tokens.
    Returns value in [0, 1].
    """
    if not reviews_text:
        return 0.5  # neutral if no reviews

    query_terms = set(_build_query_terms(user_query, attrs))
    if not query_terms:
        return 0.5

    review_tokens = set(_tokenize(reviews_text))
    if not review_tokens:
        return 0.5

    common = query_terms.intersection(review_tokens)
    overlap = len(common) / max(len(query_terms), 1)

    # map overlap [0,1] -> [0.3, 1.0] so it's never completely killing a place
    return 0.3 + 0.7 * max(0.0, min(overlap, 1.0))


def _short_review_summary(reviews_text: str, max_len: int = 140) -> str:
    """
    Very simple 'summary': take the first sentence or first N chars.
    No LLM here to keep it free.
    """
    text = reviews_text.strip()
    if not text:
        return ""

    # Try to cut at first sentence end
    for sep in [". ", "!", "? "]:
        idx = text.find(sep)
        if 0 < idx < max_len:
            return text[: idx + 1].strip()

    # fallback: crop hard
    if len(text) > max_len:
        return text[: max_len].rstrip() + "..."
    return text


def re_rank_with_reviews(
    user_query: str,
    attrs: Dict[str, Any],
    ranked_places: List[Dict[str, Any]],
    top_k_for_reviews: int = 15,
    blend_weight: float = 0.25,
) -> List[Dict[str, Any]]:
    """
    Hybrid re-ranking WITHOUT any LLM calls.

    - Takes the already ranked list from `rank_places`.
    - For top_k_for_reviews items:
        - Compute local review_match_score based on review text.
        - Blend with existing `score`.
    - Attach a small "Reviews highlight: ..." snippet to reason.
    - Returns new sorted list.

    If:
      - there are no reviews on any place, or
      - something fails
    → returns the original list unchanged.
    """

    if not ranked_places:
        return ranked_places

    # Quick check for presence of any review text
    has_any_reviews = any(
        _flatten_reviews(p).strip() for p in ranked_places
    )
    if not has_any_reviews:
        # No reviews in dataset -> keep old behaviour
        return ranked_places

    # We'll only compute for top K for speed; the rest keep base score
    candidates = ranked_places[:top_k_for_reviews]

    # Compute review-based score locally
    review_scores: Dict[str, Dict[str, Any]] = {}
    for p in candidates:
        pid = str(p.get("place_id"))
        reviews_text = _flatten_reviews(p)
        if not reviews_text.strip():
            continue

        r_score = _review_match_score(user_query, attrs, reviews_text)
        summary = _short_review_summary(reviews_text)
        review_scores[pid] = {
            "review_match_score": float(r_score),
            "review_summary": summary,
        }

    if not review_scores:
        return ranked_places

    re_scored: List[Dict[str, Any]] = []

    for p in ranked_places:
        pid = str(p.get("place_id"))
        base_score = float(p.get("score") or 0.0)

        if pid in review_scores:
            r = review_scores[pid]["review_match_score"]
            new_score = (1.0 - blend_weight) * base_score + blend_weight * r

            # Attach extra explanation from reviews (if any)
            review_summary = review_scores[pid]["review_summary"]
            if review_summary:
                existing_reason = p.get("reason") or ""
                if existing_reason:
                    p["reason"] = f"{existing_reason}. Reviews highlight: {review_summary}"
                else:
                    p["reason"] = f"Reviews highlight: {review_summary}"

            p["score_with_reviews"] = new_score
        else:
            # No review boost -> keep same score
            p["score_with_reviews"] = base_score

        re_scored.append(p)

    # Sort by new combined score (fallback to `score` if something is missing)
    re_scored.sort(
        key=lambda x: x.get("score_with_reviews", x.get("score", 0.0)),
        reverse=True,
    )
    return re_scored