"""
Backward-compatible entry point:  python backend/app.py
Prefer:  python -m backend.app   (development)  or Gunicorn (production, see README).
"""
import sys
from pathlib import Path

# Ensure the project root is importable so `backend.app` resolves to the package
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
