from flask import Blueprint, jsonify
from app.llm.gemini_client import parse_query_with_gemini

test_llm_bp = Blueprint("test_llm", __name__)

@test_llm_bp.route("/test-llm", methods=["GET"])
def test_llm():
    try:
        prompt = "give me spicy cheesy biriyani under 200 near tambaram"
        result = parse_query_with_gemini(prompt)

        return jsonify({
            "status": "success",
            "gemini_output": result
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
