"""Gunicorn settings for the production container. All values can be overridden with env vars."""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# OCR models use ~1 GB RAM per worker process, so default to one process with
# threads. With more than one worker, configure RATE_LIMIT_STORAGE_URI=redis://...
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"

# OCR + AI extraction of multi-page scans can take a while
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
graceful_timeout = 30
keepalive = 5

# Upload bodies are bounded by MAX_UPLOAD_SIZE_BYTES in Flask and nginx
limit_request_line = 8190

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
# Don't log query strings (they may contain WhatsApp verify tokens)
access_log_format = '%(h)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)ss'
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
