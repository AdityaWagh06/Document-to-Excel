# Project Folder Structure

## Project Root

- `backend/` - Flask API, document processing, AI providers, OCR, exports.
- `frontend/` - React single-page app (Vite, Tailwind, AG Grid).
- `deploy/nginx.conf` - nginx config used by the frontend container (static files + `/api` proxy).
- `docs/` - API, architecture, changelog, roadmap.
- `.github/workflows/` - CI (tests, build, Docker validation) and GHCR image publishing.
- `docker-compose.yml`, `.dockerignore`, `.env.example` - container setup and configuration template.

## Backend Layout

- `app/`
  - `ai/` - OpenAI and OpenRouter providers, invoice JSON schema, prompts.
  - `api/v1/` - REST routes and the WhatsApp webhook.
  - `auth/` - Login, sessions, CSRF, API key checks.
  - `config/` - Settings (from environment) and regex patterns.
  - `db/` - SQLite connection, schema, session and webhook repositories, JSON migration.
  - `exports/` - Excel, CSV, text summary and Tally XML builders.
  - `models/` - Dataclasses (`ParsedDocument`, `ParsedItem`, `OCRResult`).
  - `ocr/` - PDF text layer, page rendering, PaddleOCR/EasyOCR manager.
  - `parsers/` - AI + rule-based field extraction.
  - `repository/` - Invoice repository and analytics.
  - `services/` - Document processing, validation, ERP sync.
  - `app_logging/` - Logging setup with secret redaction.
  - `utils/` - Amount/text helpers, file signature checks, SSRF-safe URL validation.
  - `__main__.py` - Development server (`python -m backend.app`).
- `tests/` - pytest suite (AI and HTTP calls mocked).
- `data/` - SQLite database (local runs; not committed).
- `logs/` - Rotating log files when `LOG_TO_FILE=true`.
- `Dockerfile`, `gunicorn.conf.py` - production image and server config.
- `requirements.txt`, `requirements-ocr.txt`, `requirements-dev.txt` - core, OCR and test dependencies.
- `app.py`, `parser.py`, `ocr.py`, `export.py` - thin backward-compatibility wrappers.

## Frontend Layout

- `src/`
  - `components/layout/` - Header, footer.
  - `components/document/` - Dashboard, scan & review, invoices, analytics, ERP, WhatsApp sections.
  - `components/common/` - Login, confirm dialog, status badges, cards.
  - `context/` - Toast notifications.
  - `hooks/` - Document processing and file preview state.
  - `services/api.js` - All HTTP calls (CSRF, upload progress, session expiry handling).
  - `utils/` - Grid mapping, downloads and currency formatting.
  - `constants/`, `config/` - UI strings and API paths.
- `Dockerfile` - Node build stage, nginx-unprivileged runtime.
