"""
Production server without Docker (Windows, macOS and Linux), used by the
start scripts. Serves the API and, with SERVE_FRONTEND=true, the web app.

    python -m backend.serve        (run from the project root)

HOST defaults to 127.0.0.1 (this computer only). Set HOST=0.0.0.0 in .env to
let other computers on the network open the app.
"""
import os

# PaddleOCR compatibility (must be set before Paddle is imported)
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_mkldnn", "0")
os.environ.setdefault("PADDLE_DISABLE_FAST_MATH", "1")

from waitress import serve

from backend.app import create_app
from backend.app.config.settings import settings


def main():
    app = create_app()
    host = os.getenv("HOST", "127.0.0.1")
    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    print(f"\n  DocExtract Pro is running:  http://{shown}:{settings.port}\n  Press Ctrl+C to stop.\n", flush=True)
    serve(
        app,
        host=host,
        port=settings.port,
        threads=int(os.getenv("SERVER_THREADS", "8")),
        max_request_body_size=settings.max_upload_size_bytes + 1024 * 1024,
        channel_timeout=300,
    )


if __name__ == "__main__":
    main()
