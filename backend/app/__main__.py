"""
Development server entry point:  python -m backend.app   (run from the project root)
Production uses Gunicorn instead:  gunicorn -c backend/gunicorn.conf.py "backend.app:create_app()"
"""
import os

# Disable OneDNN for PaddleOCR compatibility (must be set before Paddle is imported)
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_mkldnn", "0")
os.environ.setdefault("PADDLE_DISABLE_FAST_MATH", "1")

from backend.app import create_app
from backend.app.config.settings import settings


def main():
    app = create_app()
    if settings.flask_env == "production":
        print("NOTE: FLASK_ENV=production - use Gunicorn (see README) instead of the development server.")
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=settings.port,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
