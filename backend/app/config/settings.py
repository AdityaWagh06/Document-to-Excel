import logging
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env files without overriding real environment variables.
# backend/.env (older layout) is read first, then the project-root .env.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _env_file in (_PROJECT_ROOT / "backend" / ".env", _PROJECT_ROOT / ".env"):
    if _env_file.is_file():
        load_dotenv(_env_file, override=False)

AI_PROVIDERS = ("openai", "gemini", "groq", "openrouter")


def _csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _clean_secret(value):
    """Treats empty strings and obvious template placeholders as unset."""
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower().startswith(("your_", "replace_with", "sk-your", "<")):
        return None
    return value


class Settings:
    def __init__(self):
        # ------------------------------------------------------------------
        # AI / LLM provider configuration (all calls happen server-side only)
        # ------------------------------------------------------------------
        # AI_PROVIDER: "openai" | "gemini" | "groq" | "openrouter" | "none" | "auto" (default).
        # "auto" picks the first provider with a key, in that order, else
        # rules-only extraction. Gemini and Groq have free tiers.
        self.ai_provider = (os.getenv("AI_PROVIDER", "auto") or "auto").strip().lower()

        self.openai_api_key = _clean_secret(os.getenv("OPENAI_API_KEY"))
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        self.openai_organization = (os.getenv("OPENAI_ORGANIZATION") or "").strip()
        self.openai_project = (os.getenv("OPENAI_PROJECT") or "").strip()

        # Google Gemini (free tier via Google AI Studio), OpenAI-compatible endpoint
        self.gemini_api_key = _clean_secret(os.getenv("GEMINI_API_KEY")) or _clean_secret(os.getenv("GOOGLE_API_KEY"))
        # Fallbacks are tried when a model is overloaded or retired; the "-latest"
        # aliases always point at Google's current Flash models.
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
        self.gemini_fallback_models = _csv(os.getenv("GEMINI_FALLBACK_MODELS", "gemini-flash-latest,gemini-flash-lite-latest"))
        self.gemini_base_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
        ).strip().rstrip("/")

        # Groq (free tier), OpenAI-compatible endpoint. Default model is text-only.
        self.groq_api_key = _clean_secret(os.getenv("GROQ_API_KEY"))
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        self.groq_base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/")

        self.openrouter_api_key = _clean_secret(os.getenv("OPENROUTER_API_KEY"))
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
        self.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.openrouter_fallback_models = _csv(os.getenv("OPENROUTER_FALLBACK_MODELS", ""))
        self.openrouter_site_url = os.getenv("OPENROUTER_SITE_URL", "").strip()
        self.openrouter_app_name = os.getenv("OPENROUTER_APP_NAME", "Invoice ERP Automation").strip()

        self.ai_timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "60"))
        self.ai_max_retries = int(os.getenv("AI_MAX_RETRIES", "2"))
        self.ai_max_input_chars = int(os.getenv("AI_MAX_INPUT_CHARS", "24000"))
        # Send page images to the LLM when OCR is unavailable or returns no text
        # (requires a vision-capable model such as gpt-4o-mini / gpt-4o).
        self.ai_vision_fallback = os.getenv("AI_VISION_FALLBACK", "true").strip().lower() == "true"
        self.ai_vision_max_pages = int(os.getenv("AI_VISION_MAX_PAGES", "3"))
        # Send page images together with the OCR text for photos and scanned pages,
        # so the model can correct OCR misreads (e.g. "$" read as "5"). Digital PDFs
        # with a text layer are always sent as text only.
        self.ai_send_images = os.getenv("AI_SEND_IMAGES", "true").strip().lower() == "true"

        # Minimum characters on a PDF page's embedded text layer before OCR is skipped
        self.pdf_text_layer_min_chars = int(os.getenv("PDF_TEXT_LAYER_MIN_CHARS", "40"))
        # Load OCR models eagerly on startup (slower boot, faster first request)
        self.ocr_preload = os.getenv("OCR_PRELOAD", "true").strip().lower() == "true"

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
        # Empty values and unedited template placeholders count as "not set".
        is_dev = self.flask_env != "production"
        raw_secret_key = _clean_secret(os.getenv("SECRET_KEY"))
        if raw_secret_key:
            self.secret_key = raw_secret_key
        elif not is_dev:
            self.secret_key = ""  # Handled by validate_production_config
        else:
            self.secret_key = secrets.token_hex(32)

        self.app_admin_username = (os.getenv("APP_ADMIN_USERNAME") or "").strip() or ("admin" if is_dev else "")
        self.app_admin_password = _clean_secret(os.getenv("APP_ADMIN_PASSWORD")) or (
            "dev-admin-pass-change-in-production" if is_dev else ""
        )
        self.api_secret_key = _clean_secret(os.getenv("API_SECRET_KEY")) or (
            "dev-api-secret-key-32chars-min-len" if is_dev else ""
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
        self.whatsapp_app_secret = _clean_secret(os.getenv("WHATSAPP_APP_SECRET")) or (
            "dev_whatsapp_app_secret_1234567890abcdef" if is_dev else ""
        )
        self.whatsapp_verify_token = _clean_secret(os.getenv("WHATSAPP_VERIFY_TOKEN")) or (
            "DOCUMENT_EXCEL_WHATSAPP_TOKEN" if is_dev else ""
        )

        # WhatsApp Cloud API (optional): needed to download real media and send replies
        self.whatsapp_access_token = _clean_secret(os.getenv("WHATSAPP_ACCESS_TOKEN"))
        self.whatsapp_phone_number_id = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
        self.whatsapp_graph_api_version = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0").strip()
        self.whatsapp_send_replies = os.getenv("WHATSAPP_SEND_REPLIES", "true").strip().lower() == "true"
        self.whatsapp_simulator_enabled = os.getenv("WHATSAPP_SIMULATOR_ENABLED", "true").strip().lower() == "true"

        # ERP integrations
        self.tally_company_name = (os.getenv("TALLY_COMPANY_NAME") or "").strip()
        self.tally_purchase_ledger = os.getenv("TALLY_PURCHASE_LEDGER", "Purchase Account").strip()
        self.custom_erp_endpoint = (os.getenv("CUSTOM_ERP_ENDPOINT") or "").strip()
        self.custom_erp_api_key = _clean_secret(os.getenv("CUSTOM_ERP_API_KEY"))

        # Rate Limiting & Reverse Proxy Configuration
        self.rate_limit_storage_uri = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
        self.login_rate_limit = os.getenv("LOGIN_RATE_LIMIT", "5 per 5 minutes")
        self.trusted_proxies_count = int(os.getenv("TRUSTED_PROXIES_COUNT", "0"))

        # Database Configuration
        default_db = str(Path(__file__).resolve().parent.parent.parent / "data" / "invoices.db")
        self.database_path = os.getenv("DATABASE_PATH", default_db)

    def ai_provider_settings(self, provider: str) -> dict:
        """Key, model, base URL and help text for one AI provider."""
        table = {
            "openai": (self.openai_api_key, self.openai_model, self.openai_base_url,
                       "OPENAI_API_KEY", "OPENAI_MODEL", "https://platform.openai.com/api-keys", "gpt-4o-mini"),
            "gemini": (self.gemini_api_key, self.gemini_model, self.gemini_base_url,
                       "GEMINI_API_KEY", "GEMINI_MODEL", "https://aistudio.google.com/apikey (free)", "gemini-3.5-flash"),
            "groq": (self.groq_api_key, self.groq_model, self.groq_base_url,
                     "GROQ_API_KEY", "GROQ_MODEL", "https://console.groq.com/keys (free)", "llama-3.3-70b-versatile"),
            "openrouter": (self.openrouter_api_key, self.openrouter_model, self.openrouter_base_url,
                           "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "https://openrouter.ai/keys", "openai/gpt-4o-mini"),
        }
        key, model, base_url, key_var, model_var, key_url, example = table[provider]
        fallbacks = {"gemini": self.gemini_fallback_models, "openrouter": self.openrouter_fallback_models}
        return {"api_key": key, "model": model, "base_url": base_url, "fallback_models": fallbacks.get(provider, []),
                "key_var": key_var,
                "model_var": model_var, "key_url": key_url, "example_model": example}

    @property
    def resolved_ai_provider(self) -> str:
        """Returns the effective provider name: one of AI_PROVIDERS or 'none'."""
        if self.ai_provider in AI_PROVIDERS or self.ai_provider == "none":
            return self.ai_provider
        for provider in AI_PROVIDERS:
            if self.ai_provider_settings(provider)["api_key"]:
                return provider
        return "none"

    @property
    def ai_model(self) -> str:
        provider = self.resolved_ai_provider
        return "" if provider == "none" else self.ai_provider_settings(provider)["model"]

    def ai_config_errors(self) -> list:
        """Returns actionable configuration problems for the selected AI provider."""
        errors = []
        if self.ai_provider not in AI_PROVIDERS + ("auto", "none"):
            errors.append(
                f"AI_PROVIDER='{self.ai_provider}' is not supported. Use one of: "
                + ", ".join(AI_PROVIDERS) + ", none or auto."
            )
            return errors
        provider = self.resolved_ai_provider
        if provider != "none":
            cfg = self.ai_provider_settings(provider)
            if not cfg["api_key"]:
                errors.append(
                    f"AI_PROVIDER={provider} but {cfg['key_var']} is not set. Create a key at {cfg['key_url']}."
                )
            if not cfg["model"]:
                errors.append(f"{cfg['model_var']} must not be empty (for example '{cfg['example_model']}').")
        if self.ai_timeout_seconds <= 0:
            errors.append("AI_TIMEOUT_SECONDS must be greater than 0.")
        if self.ai_max_retries < 0:
            errors.append("AI_MAX_RETRIES must be 0 or greater.")
        return errors

    def validate_ai_config(self):
        """
        Logs AI configuration problems. An explicitly selected provider that is
        misconfigured is fatal in production so the operator notices immediately.
        """
        errors = self.ai_config_errors()
        if not errors:
            provider = self.resolved_ai_provider
            if provider == "none":
                logger.warning(
                    "No AI provider configured (set OPENAI_API_KEY, or a free GEMINI_API_KEY / GROQ_API_KEY). "
                    "Invoices will be extracted with local rule-based parsing only, which is less accurate."
                )
            else:
                logger.info("AI extraction provider: %s (model: %s)", provider, self.ai_model)
            return
        for err in errors:
            logger.error("AI configuration error: %s", err)
        if self.flask_env == "production" and self.ai_provider != "auto":
            raise RuntimeError("AI configuration error: " + "; ".join(errors))

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

        if self.api_secret_key and len(self.api_secret_key) < 32:
            errors.append("API_SECRET_KEY must be at least 32 characters when set (leave empty to disable API-key access).")

        if any("*" in origin for origin in self.cors_allowed_origins):
            errors.append("CORS_ALLOWED_ORIGINS cannot contain wildcards (*) when credentialed auth is enabled.")

        if self.rate_limit_storage_uri.startswith("memory://"):
            logger.warning(
                "PRODUCTION WARNING: RATE_LIMIT_STORAGE_URI is set to '%s'. In-memory rate limiting "
                "only applies per individual process. In multi-worker deployments (e.g., Gunicorn), "
                "a shared storage backend like Redis (e.g. 'redis://host:port/0') must be configured "
                "for global rate limit enforcement.",
                self.rate_limit_storage_uri
            )

        if errors:
            joined = "; ".join(errors)
            logger.critical("Production configuration validation failed: %s", joined)
            raise RuntimeError(f"Critical security configuration error in production: {joined}")

settings = Settings()
