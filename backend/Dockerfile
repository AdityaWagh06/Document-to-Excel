# syntax=docker/dockerfile:1
# Backend API image (Flask + Gunicorn). Build context: repository root.
#   docker build -f backend/Dockerfile -t docextract-backend .
# Build without the local OCR engines (much smaller image; scanned images are
# then read by the AI model):  --build-arg INSTALL_OCR=false
FROM python:3.11-slim-bookworm

ARG INSTALL_OCR=true
# CPU-only PyTorch wheels keep the image ~2 GB smaller than the default CUDA build
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    LOG_TO_FILE=false \
    DATABASE_PATH=/app/data/invoices.db

# System libraries are only needed by the local OCR engines (Paddle/OpenCV)
RUN if [ "$INSTALL_OCR" = "true" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
        && rm -rf /var/lib/apt/lists/*; \
    fi \
    && useradd --create-home --home-dir /home/app --uid 10001 --shell /usr/sbin/nologin app

WORKDIR /app

COPY backend/requirements.txt backend/requirements-ocr.txt backend/
RUN pip install -r backend/requirements.txt
RUN if [ "$INSTALL_OCR" = "true" ]; then \
        if [ -n "$TORCH_INDEX_URL" ]; then pip install --index-url "$TORCH_INDEX_URL" torch torchvision; fi \
        && pip install -r backend/requirements-ocr.txt \
        # paddleocr pulls in the GUI OpenCV build; keep only the headless one
        && (pip uninstall -y opencv-python opencv-contrib-python || true) \
        && pip install --force-reinstall --no-deps opencv-python-headless==4.10.0.84; \
    fi

COPY backend/ backend/

RUN mkdir -p /app/data \
    && chown -R app:app /app/data /home/app

USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/v1/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "-c", "backend/gunicorn.conf.py", "backend.app:create_app()"]
