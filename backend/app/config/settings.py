import os
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class Settings:
    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat:free")
        self.flask_env = os.getenv("FLASK_ENV", "development")
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

settings = Settings()
