from flask import Flask, jsonify
from flask_cors import CORS
from backend.app.api.v1.routes import api_bp
from backend.app.api.v1.whatsapp_routes import whatsapp_bp
from backend.app.app_logging.logger import configure_logger
from backend.app.ocr.ocr_engine import ocr_manager
from backend.app.config.settings import settings

def create_app():
    # Setup structured logging
    configure_logger()
    
    # Eagerly initialize OCR models once on startup
    ocr_manager.initialize()
    
    app = Flask(__name__)

    # Enforce maximum upload size limit (Default: 16 MiB)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_size_bytes

    @app.errorhandler(413)
    def handle_large_upload(error):
        return jsonify({
            "error": "File size exceeds the 16 MiB maximum upload limit."
        }), 413

    # Restrict CORS to configured trusted origins
    CORS(app, resources={r"/*": {"origins": settings.cors_allowed_origins}})
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="")
    app.register_blueprint(api_bp, url_prefix="/api/v1", name="api_v1_prefixed")
    app.register_blueprint(whatsapp_bp, url_prefix="/api/v1/whatsapp")
    
    return app
