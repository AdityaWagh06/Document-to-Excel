import logging
import os
import re
from logging.handlers import RotatingFileHandler

_CONFIGURED_ATTR = "_invoice_platform_configured"

# Defense in depth: mask anything that looks like a credential before it is written
_SECRET_PATTERNS = (
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-[REDACTED]"),
    (re.compile(r"((?:api[_-]?key|access_token|password|secret)\s*[=:]\s*)[^\s,;&]+", re.IGNORECASE), r"\1[REDACTED]"),
)


class SecretRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = message
        for pattern, replacement in _SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logger():
    """
    Configures root logging once per process (safe to call repeatedly).
    LOG_LEVEL sets verbosity; LOG_TO_FILE=false keeps logs on stdout only
    (recommended in Docker); LOG_DIR overrides the log directory.
    """
    root = logging.getLogger()
    if getattr(root, _CONFIGURED_ATTR, False):
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    redactor = SecretRedactingFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redactor)
    root.addHandler(console_handler)

    if os.getenv("LOG_TO_FILE", "true").strip().lower() == "true":
        default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        log_dir = os.getenv("LOG_DIR", default_dir)
        os.makedirs(log_dir, exist_ok=True)

        app_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'), maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)
        app_handler.addFilter(redactor)
        root.addHandler(app_handler)

        error_handler = RotatingFileHandler(
            os.path.join(log_dir, 'error.log'), maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.WARNING)
        error_handler.addFilter(redactor)
        root.addHandler(error_handler)

    setattr(root, _CONFIGURED_ATTR, True)
