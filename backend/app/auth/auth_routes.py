import logging
from flask import Blueprint, jsonify, request, session
from backend.app.auth.auth_service import AuthService

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    """
    Authenticates user credentials and establishes a server-side session.
    Sets HttpOnly, SameSite cookie and returns CSRF token.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request payload. Expected JSON object."}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    if not AuthService.authenticate_credentials(username, password):
        # Do not log password; log safe identifier
        logger.warning("Failed login attempt for user: %s from IP: %s", username, request.remote_addr)
        return jsonify({"error": "Invalid username or password."}), 401

    # Invalidate existing session data before creating new session
    session.clear()
    session["authenticated"] = True
    session["user"] = username
    csrf_token = AuthService.generate_csrf_token()
    session["csrf_token"] = csrf_token
    session.permanent = True

    logger.info("User '%s' authenticated successfully from IP: %s", username, request.remote_addr)
    return jsonify({
        "status": "authenticated",
        "user": username,
        "csrf_token": csrf_token
    }), 200


@auth_bp.post("/logout")
def logout():
    """
    Clears current session and invalidates the session cookie.
    """
    user = session.get("user")
    session.clear()
    logger.info("User '%s' logged out.", user or "anonymous")
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
