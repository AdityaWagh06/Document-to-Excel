import logging
import os
import secrets
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
load_dotenv()

class Settings:
    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat:free")
        self.flask_env = os.getenv("FLASK_ENV", "development").lower()
        self.port = int(os.getenv("PORT", "5000"))

        # CORS Allowed Origins (comma-separated string or list)
        origins_env = os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000,http://127.0.0.1:5000"
        )
        self.cors_allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

        # Permitted Local Tally endpoint (strictly bounded loopback endpoint)
        self.permitted_tally_url = os.getenv("PERMITTED_TALLY_URL", "http://localhost:9000")

        # Upload limits (Default: 16 MiB)
        self.max_upload_size_bytes = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(16 * 1024 * 1024)))

        # PDF Processing Limits
        self.max_pdf_pages = int(os.getenv("MAX_PDF_PAGES", "20"))
        self.pdf_render_dpi = int(os.getenv("PDF_RENDER_DPI", "150"))

        # Authentication & Session Security
        raw_secret_key = os.getenv("SECRET_KEY")
        if raw_secret_key:
            self.secret_key = raw_secret_key
        elif self.flask_env == "production":
            self.secret_key = ""  # Handled by validate_production_config
        else:
            self.secret_key = secrets.token_hex(32)

        self.app_admin_username = os.getenv("APP_ADMIN_USERNAME", "admin" if self.flask_env != "production" else "")
        self.app_admin_password = os.getenv(
            "APP_ADMIN_PASSWORD",
            "dev-admin-pass-change-in-production" if self.flask_env != "production" else ""
        )
        self.api_secret_key = os.getenv(
            "API_SECRET_KEY",
            "dev-api-secret-key-32chars-min-len" if self.flask_env != "production" else ""
        )

        # Cookie Settings
        self.session_cookie_secure = os.getenv(
            "SESSION_COOKIE_SECURE",
            "true" if self.flask_env == "production" else "false"
        ).lower() == "true"
        self.session_cookie_httponly = True
        self.session_cookie_samesite = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
        self.session_lifetime_hours = int(os.getenv("SESSION_LIFETIME_HOURS", "24"))

        # WhatsApp Webhook Secrets
        self.whatsapp_app_secret = os.getenv(
            "WHATSAPP_APP_SECRET",
            "dev_whatsapp_app_secret_1234567890abcdef" if self.flask_env != "production" else ""
        )
        self.whatsapp_verify_token = os.getenv(
            "WHATSAPP_VERIFY_TOKEN",
            "DOCUMENT_EXCEL_WHATSAPP_TOKEN" if self.flask_env != "production" else ""
        )

    def validate_production_config(self):
        """
        Validates that critical security secrets are properly configured in production mode.
        Fails safely by raising RuntimeError if mandatory secrets are absent or weak.
        """
        if self.flask_env != "production":
            return

        errors = []

        if not self.secret_key or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be set with at least 32 characters in production.")

        if not self.app_admin_username:
            errors.append("APP_ADMIN_USERNAME must be explicitly set in production.")

        if not self.app_admin_password or len(self.app_admin_password) < 12:
            errors.append("APP_ADMIN_PASSWORD must be at least 12 characters in production.")
        elif self.app_admin_password == "dev-admin-pass-change-in-production":
            errors.append("APP_ADMIN_PASSWORD cannot use default development credentials in production.")

        if not self.whatsapp_app_secret:
            errors.append("WHATSAPP_APP_SECRET must be explicitly set in production.")
        elif self.whatsapp_app_secret == "dev_whatsapp_app_secret_1234567890abcdef":
            errors.append("WHATSAPP_APP_SECRET cannot use default development credentials in production.")

        if not self.whatsapp_verify_token:
            errors.append("WHATSAPP_VERIFY_TOKEN must be explicitly set in production.")
        elif self.whatsapp_verify_token == "DOCUMENT_EXCEL_WHATSAPP_TOKEN":
            errors.append("WHATSAPP_VERIFY_TOKEN cannot use default development credentials in production.")

        if any("*" in origin for origin in self.cors_allowed_origins):
            errors.append("CORS_ALLOWED_ORIGINS cannot contain wildcards (*) when credentialed auth is enabled.")

        if errors:
            joined = "; ".join(errors)
            logger.critical("Production configuration validation failed: %s", joined)
            raise RuntimeError(f"Critical security configuration error in production: {joined}")

settings = Settings()
