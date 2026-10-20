import logging
import secrets
from flask import Blueprint, jsonify, request, session
from backend.app.auth.auth_service import AuthService
from backend.app.auth.rate_limiter import limiter
from backend.app.config.settings import settings

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
@limiter.shared_limit(
    lambda: settings.login_rate_limit,
    scope="admin_login",
    deduct_when=lambda res: res.status_code in (400, 401)
)
def login():
    """
    Authenticates user credentials and establishes a server-side session.
    Sets HttpOnly, SameSite cookie and returns CSRF token.
    Protected by shared rate limiting across all login aliases.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request payload. Expected JSON object."}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    safe_user = AuthService.sanitize_log_input(username)
    client_ip = request.remote_addr or "unknown"

    if not AuthService.authenticate_credentials(username, password):
        # Do not log password; log sanitized identifier
        logger.warning("Failed login attempt for user: %s from IP: %s", safe_user, client_ip)
        return jsonify({"error": "Invalid username or password."}), 401

    # Invalidate existing session data before creating new session
    session.clear()
    session["authenticated"] = True
    session["user"] = username
    session_id = secrets.token_hex(16)
    session["session_id"] = session_id
    csrf_token = AuthService.generate_csrf_token()
    session["csrf_token"] = csrf_token
    session.permanent = True

    logger.info("User '%s' authenticated successfully from IP: %s", safe_user, client_ip)
    return jsonify({
        "status": "authenticated",
        "user": username,
        "csrf_token": csrf_token
    }), 200


@auth_bp.post("/logout")
def logout():
    """
    Clears current session and invalidates the session cookie.
    Persists session revocation to SQLite to prevent token replay.
    """
    session_id = session.get("session_id")
    user = session.get("user")
    if session_id:
        try:
            from backend.app.db.session_repository import session_repo
            session_repo.revoke_session(session_id, user=user)
        except Exception as exc:
            logger.warning("Could not persist session revocation to database: %s", exc)

    safe_user = AuthService.sanitize_log_input(user) if user else "anonymous"
    session.clear()
    logger.info("User '%s' logged out and session revoked.", safe_user)
    return jsonify({
        "status": "logged_out",
        "message": "Successfully logged out."
    }), 200


@auth_bp.get("/session")
def get_session():
    """
    Returns the current session authentication status and active CSRF token.
    Safe read-only endpoint for browser client session bootstrap.
    """
    is_authenticated = bool(session.get("authenticated", False))
    user = session.get("user") if is_authenticated else None
    csrf_token = session.get("csrf_token") if is_authenticated else None

    return jsonify({
        "authenticated": is_authenticated,
        "user": user,
        "csrf_token": csrf_token
    }), 200
