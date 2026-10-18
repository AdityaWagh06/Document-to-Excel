import os
import sys
from pathlib import Path

# Disable OneDNN for PaddleOCR compatibility
os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_enable_mkldnn'] = '0'
os.environ['FLAGS_mkldnn'] = '0'

# Ensure the backend directory is in the import path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app import create_app
from backend.app.config.settings import settings

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=settings.port,
        debug=(settings.flask_env == "development"),
        use_reloader=False
    )
