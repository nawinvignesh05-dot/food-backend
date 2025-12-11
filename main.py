from flask import Flask, jsonify
from flask_cors import CORS

from app.core.config import settings
from app.api.endpoints.recommendations import bp as rec_bp
from app.api.endpoints.geocode import geo_bp
from app.api.test_llm import test_llm_bp

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = settings.SECRET_KEY

    # <-- FIX CORS -->
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=False,
    )

    # register all blueprints
    app.register_blueprint(rec_bp, url_prefix="/api")
    app.register_blueprint(geo_bp, url_prefix="/api")
    app.register_blueprint(test_llm_bp, url_prefix="/api")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)




