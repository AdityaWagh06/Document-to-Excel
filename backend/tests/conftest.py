"""
Test isolation. Runs before any backend module is imported so that tests:
- never read or modify the real database (backend/data/invoices.db),
- never call a real AI provider even if backend/.env contains an API key,
- never load the heavy OCR models or write to backend/logs.
Values set here take precedence over backend/.env (python-dotenv does not
override variables that already exist in the environment).
"""
import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="invoice-tests-")

os.environ.update({
    "FLASK_ENV": "testing",
    "DATABASE_PATH": os.path.join(_TEST_DIR, "test_invoices.db"),
    "AI_PROVIDER": "none",
    "OPENAI_API_KEY": "",
    "OPENROUTER_API_KEY": "",
    "OCR_PRELOAD": "false",
    "LOG_TO_FILE": "false",
    "LOG_LEVEL": "WARNING",
    "SECRET_KEY": "test-secret-key-" + "x" * 32,
    "APP_ADMIN_USERNAME": "admin",
    "APP_ADMIN_PASSWORD": "test-admin-password-123",
    "API_SECRET_KEY": "test-api-secret-key-0123456789abcdef",
    "WHATSAPP_APP_SECRET": "test_whatsapp_app_secret_1234567890",
    "WHATSAPP_VERIFY_TOKEN": "TEST_VERIFY_TOKEN",
    "WHATSAPP_ACCESS_TOKEN": "",
    "WHATSAPP_PHONE_NUMBER_ID": "",
    "RATE_LIMIT_STORAGE_URI": "memory://",
    "TRUSTED_PROXIES_COUNT": "0",
    "SESSION_COOKIE_SECURE": "false",
    "CUSTOM_ERP_ENDPOINT": "",
    "CUSTOM_ERP_API_KEY": "",
    "PERMITTED_TALLY_URL": "http://localhost:9000",
    "CORS_ALLOWED_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
})
