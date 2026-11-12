# Changelog

All notable changes to the **Document to Excel** codebase are documented here.

## [2.1.0] - 2026-11-12

### Added
- Public landing page shown before sign-in, with a sign-in dialog.
- `SETUP_GUIDE.pdf`: short client setup and deployment guide.
- Run without Docker: `start-windows.bat` / `start-linux.sh` install what is missing and start the app with Waitress on one port; `SERVE_FRONTEND=true` lets the backend serve the built web app (`backend/serve.py`).
- CI: full backend image build with OCR plus a real OCR read of a scanned image, and a no-Docker start test of `start-linux.sh`.

### Changed
- Removed the one-click demo login and the pre-filled default password from the frontend; a test now fails if the default password appears in frontend code.
- Landing page: removed unverified claims (fixed accuracy and speed numbers, "zero hallucination", SAP/Zoho push).
- Session-expiry dialog again says the session expired and that unsaved edits are kept.
- Removed unused scripts `backend/app/test_auto_model.py`, `backend/app/test_free_models.py`, `backend/app/config/ai_constants.py`; the secret scan test now covers all backend and frontend source.
- README: dev server port is 5180.

## [2.0.0] - 2026-10-21

### Added
- OpenAI API as the primary AI provider (Structured Outputs with a strict invoice schema, vision fallback for scanned documents, retries with backoff, typed errors). OpenRouter kept as an option. `AI_PROVIDER` selects `auto`, `openai`, `openrouter` or `none`.
- Embedded PDF text is used before OCR, so digital PDFs no longer need OCR.
- GSTIN checksum and state-code validation, CGST/SGST mismatch, IGST vs CGST/SGST conflict, low-confidence and low-OCR-quality warnings.
- Real WhatsApp Cloud API support (Meta payloads, Graph media download, replies, retry-safe idempotency); simulator can be disabled.
- Tally response parsing (`Synced` / `Failed` / `XML Generated`), configurable ledgers, custom ERP API key.
- `/api/v1/system/status`, database check in `/api/v1/health`, JSON error pages, security headers.
- Dashboard, toasts, confirmation dialogs, full-page login, session-expiry prompt, upload progress, mobile camera capture, mark-as-verified.
- Docker images (backend non-root with optional OCR, nginx-unprivileged frontend), Docker Compose, gunicorn config, `.env.example`, `.dockerignore`, GitHub Actions CI and GHCR publishing.
- Tests for AI providers (mocked), parser/amount regressions, WhatsApp Cloud API, Tally and API behaviour; tests now use an isolated temporary database.

### Fixed
- Amounts such as `1,180.00` were stored as `1.180.00`, breaking totals and analytics.
- Rule-based parser read the tax rate (e.g. `9` from `CGST 9%`) as the tax amount and confused HSN codes with quantities.
- Running the test suite could wipe the real invoice database.
- `python -m backend.app` did not start the server; the old `backend/app.py` ran with debug mode on all interfaces.
- Log lines were written several times.

### Changed
- Requirements split into core, OCR and dev files; gunicorn added.
- Removed unverifiable claims from the UI (fixed accuracy/speed figures, hard-coded endpoints and tokens).

## [1.1.0] - 2026-07-23

### Refactored
- **Backend Reorganization**:
  - Split flat backend files into logical `app/` subpackages: `api/v1`, `services`, `parsers`, `ocr`, `exports`, `models`, `repository`, `config`, `logging`, `utils`.
  - Replaced monolithic global dictionary tracking in `app.py` with an encapsulated, thread-safe `DocumentRepository`.
  - Replaced print calls with structured rotation file loggers inside `logs/`.
  - Replaced Pydantic dependency with standard Python `dataclasses`.
  - Created minimal `< 40` lines `app.py` at `backend/` root.
- **Frontend Reorganization**:
  - Reorganized monolith `App.jsx` into layout, document, and common components.
  - Isolated fetch operations into a unified `services/api.js`.
  - Separated state and business logic hooks into custom hooks (`useDocumentProcessor` and `useFilePreview`).
