from flask import Blueprint, request, jsonify
from app.services.geopy_service import geocode_text_location

geo_bp = Blueprint("geocode", __name__)


@geo_bp.route("/geocode", methods=["POST"])
def geocode():
    data = request.get_json() or {}
    text = data.get("location_text")

    if not text:
        return jsonify({"error": "Missing location_text"}), 400

    lat, lng = geocode_text_location(text)

    if lat is None or lng is None:
        return jsonify({"error": "Location not found"}), 404

    return jsonify({"lat": lat, "lng": lng}), 200
