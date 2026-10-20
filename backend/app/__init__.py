from datetime import timedelta
import logging
from flask import Flask, jsonify, request, session, g
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded
from backend.app.api.v1.routes import api_bp
from backend.app.api.v1.whatsapp_routes import whatsapp_bp
from backend.app.auth import auth_bp, AuthService, limiter
from backend.app.app_logging.logger import configure_logger
from backend.app.ocr.ocr_engine import ocr_manager
from backend.app.config.settings import settings
from backend.app.db import init_db, close_flask_db

logger = logging.getLogger(__name__)

PUBLIC_EXACT_PATHS = {
    "/health",
    "/api/v1/health",
    "/",
    "/api/v1",
    "/favicon.ico",
    "/api/v1/auth/login",
    "/auth/login",
    "/api/v1/auth/session",
    "/auth/session",
    "/api/v1/whatsapp/webhook",
    "/whatsapp/webhook",
}

def create_app():
    # Setup structured logging
    configure_logger()

    # Fail safely in production if critical security secrets are absent
    settings.validate_production_config()

    # Eagerly initialize OCR models once on startup
    ocr_manager.initialize()

    app = Flask(__name__)

    # Session & Secret Key configuration
    app.secret_key = settings.secret_key
    app.config.update(
        MAX_CONTENT_LENGTH=settings.max_upload_size_bytes,
        SESSION_COOKIE_HTTPONLY=settings.session_cookie_httponly,
        SESSION_COOKIE_SAMESITE=settings.session_cookie_samesite,
        SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=settings.session_lifetime_hours),
    )

    # Reverse proxy support (if configured behind trusted proxies)
    if settings.trusted_proxies_count > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=settings.trusted_proxies_count,
            x_proto=settings.trusted_proxies_count
        )

    # Initialize rate limiting
    limiter.init_app(app)

    # Initialize SQLite database schema
    init_db()

    # Teardown database connection on request context end
    app.teardown_appcontext(close_flask_db)

    @app.errorhandler(413)
    def handle_large_upload(error):
        return jsonify({
            "error": "File size exceeds the 16 MiB maximum upload limit."
        }), 413

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_exceeded(error):
        response = jsonify({
            "error": "Too many failed login attempts. Please try again later.",
            "retry_after": error.description
        })
        response.status_code = 429
        return response

    # Restrict CORS to configured trusted origins with credentials support
    CORS(
        app,
        supports_credentials=True,
        resources={r"/*": {"origins": settings.cors_allowed_origins}}
    )

    # Global Authentication and CSRF Protection Middleware
    @app.before_request
    def enforce_auth_and_csrf():
        # Allow CORS preflight requests through without authentication
        if request.method == "OPTIONS":
            return None

        # Normalize path for comparison (strip trailing slashes except root)
        norm_path = request.path.rstrip("/") if request.path != "/" else "/"

        # Allow explicitly designated public endpoints
        if norm_path in PUBLIC_EXACT_PATHS or request.path in PUBLIC_EXACT_PATHS:
            return None

        # Strategy 1: Check programmatic API Key
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        if api_key and AuthService.authenticate_api_key(api_key):
            g.authenticated = True
            g.user = "api_client"
            g.auth_type = "api_key"
            return None

        # Strategy 2: Check server-managed browser session
        if session.get("authenticated") is True:
            # Check server-side session revocation in SQLite
            session_id = session.get("session_id")
            if session_id:
                from backend.app.db.session_repository import session_repo
                if session_repo.is_session_revoked(session_id):
                    session.clear()
                    logger.warning(
                        "Revoked session rejected on %s %s from IP %s",
                        request.method,
                        request.path,
                        request.remote_addr
                    )
                    return jsonify({"error": "Session has been revoked or logged out. Please log in again."}), 401

            # Enforce CSRF protection on state-changing requests authenticated via cookies
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                csrf_header = request.headers.get("X-CSRF-Token")
                expected_csrf = session.get("csrf_token")

                if not AuthService.validate_csrf_token(csrf_header, expected_csrf):
                    logger.warning(
                        "CSRF validation failure on %s %s from IP %s",
                        request.method,
                        request.path,
                        request.remote_addr
                    )
                    return jsonify({"error": "CSRF validation failed. Missing or invalid CSRF token."}), 403

            g.authenticated = True
            g.user = session.get("user")
            g.auth_type = "session"
            return None

        # Unauthenticated request to sensitive endpoint
        logger.warning(
            "Unauthenticated access rejected: %s %s from IP %s",
            request.method,
            request.path,
            request.remote_addr
        )
        return jsonify({"error": "Authentication required. Please log in."}), 401

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="")
    app.register_blueprint(api_bp, url_prefix="/api/v1", name="api_v1_prefixed")
    app.register_blueprint(whatsapp_bp, url_prefix="/api/v1/whatsapp")
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(auth_bp, url_prefix="/auth", name="auth_root")

    return app
