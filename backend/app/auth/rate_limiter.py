from flask import request
from flask_limiter import Limiter
from backend.app.config.settings import settings


def get_client_ip() -> str:
    """
    Returns client IP address using Flask's request.remote_addr.
    Does NOT trust client-supplied headers like X-Forwarded-For directly.
    Proxy headers are only respected if Werkzeug's ProxyFix middleware
    is configured via TRUSTED_PROXIES_COUNT setting.
    """
    return request.remote_addr or "127.0.0.1"


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[],
    headers_enabled=True,
    storage_uri=settings.rate_limit_storage_uri,
)
