import hmac
import logging
import secrets
from typing import Optional

from backend.app.config.settings import settings

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    def authenticate_credentials(username: Optional[str], password: Optional[str]) -> bool:
        """
        Validates username and password using constant-time string comparison.
        Prevents timing attacks and avoids leaking whether username or password was incorrect.
        """
        if not username or not password:
            return False

        expected_user = settings.app_admin_username
        expected_pass = settings.app_admin_password

        if not expected_user or not expected_pass:
            logger.warning("Authentication failed: Server credentials are not configured.")
            return False

        # Constant-time comparison
        user_matches = hmac.compare_digest(username.strip(), expected_user.strip())
        pass_matches = hmac.compare_digest(password, expected_pass)

        return user_matches and pass_matches

    @staticmethod
    def authenticate_api_key(key: Optional[str]) -> bool:
        """
        Validates a programmatic API key header using constant-time comparison.
        """
        if not key or not settings.api_secret_key:
            return False

        # Support "Bearer <token>" format as well
        clean_key = key.strip()
        if clean_key.lower().startswith("bearer "):
            clean_key = clean_key[7:].strip()

        return hmac.compare_digest(clean_key, settings.api_secret_key.strip())

    @staticmethod
    def generate_csrf_token() -> str:
        """
        Generates a 32-byte cryptographically secure hexadecimal CSRF token.
        """
        return secrets.token_hex(32)

    @staticmethod
    def validate_csrf_token(provided_token: Optional[str], expected_token: Optional[str]) -> bool:
        """
        Validates CSRF token using constant-time comparison.
        """
        if not provided_token or not expected_token:
            return False
        return hmac.compare_digest(provided_token.strip(), expected_token.strip())
