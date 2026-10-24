# DocExtract Pro: Invoice & ERP Automation

DocExtract Pro reads Indian GST invoices (PDF or photo), extracts the vendor, GSTIN, invoice number, dates, line items and CGST/SGST/IGST totals, checks them, lets a person review and correct them, and exports the result to Excel, CSV, a text summary or a Tally XML voucher. Invoices can also arrive through a WhatsApp Business number.

* **Backend:** Python / Flask REST API, SQLite, gunicorn
* **Frontend:** React 18 + Vite + Tailwind + AG Grid, served by nginx in production
* **AI:** OpenAI API (primary, Structured Outputs), free Google Gemini or Groq keys, or OpenRouter. Runs without any key using rule-based parsing. AI keys stay on the server; the browser never calls an AI provider.
* **OCR:** embedded PDF text first, then local PaddleOCR / EasyOCR for scanned pages, then (optional) AI vision as a last resort

---

## Contents

1. [Features](#features)
2. [How a document is processed](#how-a-document-is-processed)
3. [Architecture](#architecture)
4. [Quick start with Docker (recommended)](#quick-start-with-docker-recommended)
5. [Local development without Docker](#local-development-without-docker)
6. [Configuring OpenAI](#configuring-openai)
7. [Environment variables](#environment-variables)
8. [Database, migrations and backups](#database-migrations-and-backups)
9. [Authentication and production security](#authentication-and-production-security)
10. [WhatsApp setup](#whatsapp-setup)
11. [ERP / Tally integration and its limits](#erp--tally-integration-and-its-limits)
12. [Tests and CI/CD](#tests-and-cicd)
13. [Troubleshooting](#troubleshooting)

---

## Features

| Area | What works |
|---|---|
| Upload | PDF (multi-page, up to `MAX_PDF_PAGES`), PNG, JPG, WEBP up to 16 MB. Extension **and** file signature are checked. On phones, a "Take photo" button opens the camera. |
| Text reading | Digital PDFs use their embedded text (no OCR needed). Scanned pages go through PaddleOCR, with EasyOCR as backup. If no text can be read and an AI key is set, page images are sent to the AI vision model. |
| Field extraction | OpenAI Structured Outputs (strict JSON schema) when a key is configured; otherwise a rule-based parser for Indian GST invoices. AI values that do not appear in the document text are flagged and lower the confidence score. Missing values stay empty: nothing is invented. |
| Validation | Required fields, GSTIN format **and checksum**, GSTIN state code, CGST = SGST, intra- vs inter-state tax conflict, subtotal + tax = total, line-item `qty × rate`, duplicate invoice detection, low confidence and low OCR quality warnings. |
| Human review | Every field is editable in the grid. Saving re-runs validation on the server. Invoices are `Pending`, `Verified` or `Flagged Error`. |
| Export | Excel (.xlsx), CSV, text summary and Tally XML voucher. |
| History & analytics | Search/filter all invoices, delete with confirmation, spend by month and by vendor, GST totals. |
| ERP | Tally XML-server sync (with real response parsing) or "XML Generated" download when Tally is offline; generic JSON push to a custom ERP endpoint. |
| WhatsApp | Meta WhatsApp Cloud API webhook (signature verified, idempotent), media download, optional reply to the sender, plus a clearly-labelled simulator for testing. |
| Security | Session login with CSRF protection, login rate limit, server-side session revocation, optional API key access, SSRF-safe outbound URLs, security headers, secrets redacted from logs. |

---

## How a document is processed

1. **Upload checks.** Extension and magic bytes must match an allowed type; size and page limits are enforced.
2. **Text.** For each PDF page the embedded text layer is used if it has at least `PDF_TEXT_LAYER_MIN_CHARS` characters. Other pages (and images) are rendered and OCR'd locally.
3. **Extraction.** If an AI provider is configured, the text is sent to it with a strict JSON schema. On any AI error (bad key, quota, timeout, refusal) the app falls back to the rule-based parser and records why in `extraction_notes`. Empty AI fields are filled from the rule-based parser where the rules find a value.
4. **Vision fallback.** If OCR is not installed or reads almost nothing, and `AI_VISION_FALLBACK=true`, up to `AI_VISION_MAX_PAGES` page images are sent to the AI model.
5. **Validation** runs, the invoice is stored in SQLite and shown for review.
6. **Review and export.** A person corrects fields, saves (validation runs again), marks it verified and exports or syncs it.

Each invoice records how it was extracted (`extraction_method`: `ai`, `ai_vision`, `rules`) and which model was used, shown as a badge in the UI.

---

## Architecture

```
Browser ──HTTPS──> nginx (frontend container, :8080)
                    ├── /            React single-page app (static files)
                    └── /api/*  ──>  gunicorn + Flask (backend container, :5000)
                                       ├── SQLite (volume: app-data)
                                       ├── PaddleOCR / EasyOCR models (volume: ocr-models)
                                       ├── OpenAI / OpenRouter API  (outbound, server side only)
                                       ├── Meta Graph API           (WhatsApp media + replies)
                                       └── Tally XML server / custom ERP (operator configured)
```

```
backend/
├── app/
│   ├── ai/              # OpenAI + OpenRouter providers, invoice JSON schema, prompts
│   ├── api/v1/          # REST endpoints, WhatsApp webhook
│   ├── auth/            # Session login, CSRF, API key decorator
│   ├── services/        # Document processing, validation, ERP sync
│   ├── repository/      # Invoice repository (SQLite) and analytics
│   ├── db/              # SQLite connection, schema, sessions, webhook idempotency, JSON migration
│   ├── parsers/         # AI + rule-based extraction
│   ├── ocr/             # PDF text layer, rendering, OCR engines
│   ├── exports/         # Excel, CSV, text summary, Tally XML
│   ├── config/          # Settings (all from environment), regex patterns
│   ├── app_logging/     # Logging with secret redaction
│   └── utils/           # Amount/text helpers, file signature checks, SSRF-safe URL checks
├── tests/               # pytest suite (AI calls are mocked)
├── Dockerfile
├── gunicorn.conf.py
├── requirements.txt         # core runtime
├── requirements-ocr.txt     # PaddleOCR / EasyOCR (large)
└── requirements-dev.txt     # core + pytest
frontend/
├── src/                 # React app (components, hooks, services, context)
└── Dockerfile           # build with Node, serve with unprivileged nginx
deploy/nginx.conf        # reverse proxy + security headers
docker-compose.yml
.env.example             # every setting, placeholders only
.github/workflows/       # CI and GHCR image publishing
```

More detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), API reference: [`docs/API.md`](docs/API.md).

---

## Quick start with Docker (recommended)

Requirements: Docker Desktop (Windows/macOS) or Docker Engine + Compose v2 (Linux), about 6 GB of free disk for the OCR build.

```bash
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

Edit `.env` and set at least:

* `SECRET_KEY`: 64 random hex characters, e.g. `python -c "import secrets; print(secrets.token_hex(32))"`
* `APP_ADMIN_USERNAME` and `APP_ADMIN_PASSWORD`: the login for the web app
* `WHATSAPP_APP_SECRET` and `WHATSAPP_VERIFY_TOKEN`: any long random strings if you do not use WhatsApp yet
* `OPENAI_API_KEY`: recommended (see [Configuring OpenAI](#configuring-openai))
* `SESSION_COOKIE_SECURE=false` **only** if you will open the app over plain `http://` (for example on `localhost`). Keep `true` behind HTTPS.

Then:

```bash
docker compose up -d --build
docker compose ps                 # both services should become "healthy"
```

Open <http://localhost:8080> and sign in.

* The first build with OCR downloads PaddlePaddle, PyTorch (CPU) and EasyOCR and takes a while. For a much smaller image that relies on embedded PDF text and AI vision instead of local OCR, set `INSTALL_OCR=false` in `.env` before building.
* Data lives in the named volume `app-data` (`/app/data/invoices.db`). OCR models are cached in `ocr-models`.
* Change the port with `HTTP_PORT`; `HTTP_BIND` controls which interface it listens on (default `0.0.0.0`, i.e. reachable from your network; use `127.0.0.1` for this machine only).
* Tally running on the Docker host: set `PERMITTED_TALLY_URL=http://host.docker.internal:9000`.
* Logs: `docker compose logs -f backend`. Stop: `docker compose down` (volumes are kept).

### HTTPS

Put the stack behind a TLS-terminating proxy (Caddy, Traefik, a cloud load balancer or nginx with certificates) that forwards to `HTTP_PORT`. Keep `SESSION_COOKIE_SECURE=true` and set `TRUSTED_PROXIES_COUNT` to the number of proxies in front of the backend (the bundled nginx counts as 1, so use 2 when another proxy sits in front of it). Set `CORS_ALLOWED_ORIGINS` to your public origin.

### Using published images

Pushing a tag like `v1.0.0` publishes `ghcr.io/<owner>/<repo>-backend` and `-frontend` to GitHub Container Registry (see `.github/workflows/docker-publish.yml`). To run them instead of building, replace `build:` with `image:` in `docker-compose.yml`.

---

## Local development without Docker

Requirements: Python 3.10 or 3.11 (3.11 is what the Docker image and CI use), Node.js 20, npm.

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pip install -r backend/requirements-ocr.txt      # optional: local OCR for scanned documents
cp .env.example .env                              # then set FLASK_ENV=development and your OPENAI_API_KEY
python -m backend.app                             # http://127.0.0.1:5000
```

Run all commands from the project root (the folder that contains `backend/` and `frontend/`). An existing `backend/.env` is still read, so older setups keep working. If both files exist, values in `backend/.env` win over the root `.env`, and real environment variables win over both.

In development (`FLASK_ENV=development`) unset secrets get safe development defaults and the login is `admin` / `dev-admin-pass-change-in-production` unless you set `APP_ADMIN_USERNAME` / `APP_ADMIN_PASSWORD`.

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to http://127.0.0.1:5000
```

Point the dev proxy elsewhere with `VITE_BACKEND_URL=http://host:port npm run dev`. `npm run build` writes the production bundle to `frontend/dist`.

### Production without Docker

```bash
pip install -r backend/requirements.txt
gunicorn -c backend/gunicorn.conf.py "backend.app:create_app()"
```

Serve `frontend/dist` with any web server and proxy `/api/` to gunicorn (see `deploy/nginx.conf`). gunicorn does not run on Windows; on Windows use Docker Desktop.

---

## Configuring OpenAI

1. Create a key at <https://platform.openai.com/api-keys> and make sure the project has billing/credits.
2. In `.env`:
   ```env
   AI_PROVIDER=openai          # or "auto": OpenAI if a key is set, else OpenRouter, else rules only
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini    # any chat model that supports Structured Outputs and images
   ```
3. Restart the backend. **Dashboard → System setup** shows whether AI extraction is configured (it never shows the key).

Optional: `OPENAI_ORGANIZATION`, `OPENAI_PROJECT`, `OPENAI_BASE_URL` (Azure/OpenAI-compatible gateways), `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`, `AI_MAX_INPUT_CHARS`.

How errors are handled: rate limits, timeouts and 5xx responses are retried with backoff (respecting `Retry-After`). Invalid keys, missing billing, unknown models and refusals are not retried; the invoice is extracted with the rule-based parser instead and the reason is shown in the review screen and logged (without the key). In production, an explicitly selected provider with a missing key stops the app at start-up so the misconfiguration is noticed.

### Free option: Google Gemini (no paid key needed)

1. Sign in at <https://aistudio.google.com/apikey> with a Google account and click **Create API key** (no card required).
2. In `.env` (or `backend/.env`):
   ```env
   AI_PROVIDER=auto
   GEMINI_API_KEY=your-key
   GEMINI_MODEL=gemini-3.5-flash
   ```
3. Restart the backend. The dashboard shows "AI extraction: Google Gemini".

Gemini is called through Google's OpenAI-compatible endpoint, supports images (so scanned invoices work through the vision fallback even without local OCR) and JSON-schema output. The free tier has per-minute and per-day request limits; when they are hit the invoice is extracted with the rule-based parser and the note says so. Google's terms allow free-tier data to be used to improve their products, so use a paid key for confidential client invoices. If the model is busy or retired, the models in `GEMINI_FALLBACK_MODELS` (default `gemini-flash-latest,gemini-flash-lite-latest`, aliases that always point at Google's current Flash models) are tried next.

**Groq** (also free, very fast, text only with the default model): `GROQ_API_KEY` from <https://console.groq.com/keys>, `GROQ_MODEL=llama-3.3-70b-versatile`.

With no key at all the app still runs: digital PDFs and OCR text are extracted with the rule-based parser.

**OpenRouter** remains supported: `AI_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, optional comma-separated `OPENROUTER_FALLBACK_MODELS`.

`AI_PROVIDER=none` disables AI completely.

Note: when AI is enabled, invoice text (and for vision fallback, page images) is sent to the provider you configure. Choose a provider and data-retention settings that suit your data.

---

## Environment variables

All settings are read from the environment (or `.env`). [`.env.example`](.env.example) documents every variable with placeholders; the most important ones:

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_ENV` | `development` (compose: `production`) | `production` enforces real secrets and secure cookies |
| `SECRET_KEY` | random per start in dev | Session signing key, ≥32 chars in production |
| `APP_ADMIN_USERNAME` / `APP_ADMIN_PASSWORD` | dev defaults | Web login (required in production) |
| `API_SECRET_KEY` | empty in production | Enables `X-API-Key` access for scripts; ≥32 chars |
| `SESSION_COOKIE_SECURE` | `true` in production | Set `false` only for plain-HTTP testing |
| `SESSION_LIFETIME_HOURS` | `24` | Session length |
| `CORS_ALLOWED_ORIGINS` | localhost dev origins | Comma-separated allowed origins |
| `TRUSTED_PROXIES_COUNT` | `0` (compose: `1`) | Reverse proxies in front of the backend |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | Use `redis://...` when running several workers/hosts |
| `AI_PROVIDER` | `auto` | `auto`, `openai`, `gemini`, `groq`, `openrouter`, `none` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-3.5-flash` | Free Google Gemini key |
| `GROQ_API_KEY` / `GROQ_MODEL` | – / `llama-3.3-70b-versatile` | Free Groq key |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | – / `gpt-4o-mini` | OpenAI settings |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | – | OpenRouter settings |
| `AI_VISION_FALLBACK` / `AI_VISION_MAX_PAGES` | `true` / `3` | Send page images to AI when OCR cannot read the document |
| `OCR_ENGINES` | `paddleocr,easyocr` | Order of local OCR engines |
| `OCR_PRELOAD` | `true` | Load OCR models at start (slower start, faster first upload) |
| `MAX_UPLOAD_SIZE_BYTES` / `MAX_PDF_PAGES` | 16 MB / `20` | Upload limits |
| `DATABASE_PATH` | `backend/data/invoices.db` (Docker: `/app/data/invoices.db`) | SQLite file |
| `WHATSAPP_*` | – | See [WhatsApp setup](#whatsapp-setup) |
| `PERMITTED_TALLY_URL`, `TALLY_*` | `http://localhost:9000` | Tally connection and ledger names |
| `CUSTOM_ERP_ENDPOINT` / `CUSTOM_ERP_API_KEY` | – | Custom ERP push target |
| `LOG_LEVEL` / `LOG_TO_FILE` | `INFO` / `true` | Logging |
| `WEB_CONCURRENCY` | `1` | gunicorn worker processes |
| `INSTALL_OCR` (build arg) | `true` | Include local OCR engines in the backend image |

Never commit `.env`. Only `.env.example` (placeholders) belongs in Git.

---

## Database, migrations and backups

* SQLite in WAL mode. The schema (`backend/app/db/schema.sql`) is created automatically on first start; there is no separate migration step.
* Older versions stored invoices in `backend/temp/documents.json`. These are imported automatically on start, or manually:
  ```bash
  python -m backend.app.db.migrate_json_to_sqlite --json-path backend/temp/documents.json
  ```
  A backup copy of the JSON file is made unless `--no-backup` is passed.
* **Backup (Docker):**
  ```bash
  docker compose exec backend python -c "import sqlite3; s=sqlite3.connect('/app/data/invoices.db'); d=sqlite3.connect('/app/data/backup.db'); s.backup(d); d.close()"
  docker compose cp backend:/app/data/backup.db ./invoices-backup.db
  ```
* **Backup (local):** `sqlite3 backend/data/invoices.db ".backup invoices-backup.db"` (or stop the app and copy the `.db` file).
* **Restore:** stop the backend, replace the database file (`docker compose cp ./invoices-backup.db backend:/app/data/invoices.db` while the container exists, then `docker compose restart backend`).

---

## Authentication and production security

* Users sign in with the admin account from `.env`. Sessions are stored server side, so **Sign out** revokes them immediately; expired sessions show a "session expired" prompt in the UI.
* State-changing requests need a CSRF token (handled by the frontend). Login is rate limited (`LOGIN_RATE_LIMIT`).
* Scripts can use `X-API-Key: <API_SECRET_KEY>` instead of a session.
* In production the app refuses to start without a strong `SECRET_KEY`, admin credentials and WhatsApp secrets.
* Outbound requests (Tally, custom ERP, WhatsApp media) are validated against SSRF; Tally is only reachable at the operator-configured `PERMITTED_TALLY_URL`.
* nginx and Flask add security headers (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`); API responses are not cached.
* Containers run as non-root users; the frontend container is read-only.
* Secrets and API keys are redacted from logs.

Checklist before exposing the app: HTTPS in front, `SESSION_COOKIE_SECURE=true`, strong unique secrets, `HTTP_BIND` restricted or firewall in place, regular database backups, and `RATE_LIMIT_STORAGE_URI=redis://...` if you scale beyond one worker.

---

## WhatsApp setup

1. Create a Meta app with the WhatsApp product and a business phone number.
2. In `.env` set `WHATSAPP_APP_SECRET` (App settings → Basic → App secret), `WHATSAPP_VERIFY_TOKEN` (any random string you choose), `WHATSAPP_ACCESS_TOKEN` (a permanent system-user token) and `WHATSAPP_PHONE_NUMBER_ID`.
3. In the Meta dashboard set the webhook URL to `https://<your-domain>/api/v1/whatsapp/webhook` with the same verify token and subscribe to `messages`. The URL must be public HTTPS.
4. Send an invoice photo or PDF to the business number. It is downloaded, processed and appears in **Invoices** (source WhatsApp). With `WHATSAPP_SEND_REPLIES=true` the sender gets a short summary reply.

Each message is processed once (webhook idempotency); if processing fails temporarily the event is released so Meta's retry works. The **WhatsApp** tab has a simulator (disable with `WHATSAPP_SIMULATOR_ENABLED=false`) that runs a local file through the same pipeline without Meta; results are marked as simulated.

---

## ERP / Tally integration and its limits

* **Tally (TallyPrime / Tally.ERP 9).** Enable Tally's XML server (default port 9000), create the ledgers named in `TALLY_*` (purchase, CGST/SGST/IGST input, round off) and set `TALLY_COMPANY_NAME`. **Send to Tally** posts a purchase voucher; the invoice is marked `Synced` only when Tally reports the voucher created with no errors. Tally's error message is shown otherwise (`Failed`). The party ledger (vendor name) must already exist in Tally.
* **Tally offline.** The voucher XML is generated and the invoice is marked `XML Generated`; download it and import via Tally's Import → Vouchers.
* **Custom ERP.** `CUSTOM_ERP_ENDPOINT` receives a JSON POST of the invoice fields (with `Authorization: Bearer <CUSTOM_ERP_API_KEY>` if set). Any 2xx counts as synced.
* **Limits:** no SAP/Zoho/QuickBooks connectors; no automatic creation of Tally ledgers or stock items; inventory entries are only included when `TALLY_INCLUDE_INVENTORY=true` and the stock items exist. The Tally integration has been tested against generated responses, not against a live Tally installation in this repository's CI.

---

## Tests and CI/CD

```bash
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
cd frontend && npm ci && npm run build
docker compose config -q
```

Tests use a temporary database and mock every AI/HTTP call, so they need no keys or network.

GitHub Actions:

* `.github/workflows/ci.yml` (push / pull request): backend tests on Python 3.11, frontend build, compose validation, backend (without OCR) and frontend image builds, and a container health smoke test.
* `.github/workflows/docker-publish.yml` (tags `v*` or manual): builds and pushes both images to GHCR using the built-in `GITHUB_TOKEN`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "AI extraction not configured" on the dashboard | Set `OPENAI_API_KEY`, or a free `GEMINI_API_KEY`, keep `AI_PROVIDER=auto` and restart the backend. |
| Review screen says the AI call failed (auth / billing / quota) | Check the key, billing and model name in the OpenAI dashboard. Rule-based extraction is used meanwhile. |
| Upload returns "No OCR engine available" (503) | Scanned images need OCR or AI: install `backend/requirements-ocr.txt` (or build with `INSTALL_OCR=true`) or configure an AI key. Digital PDFs work without either. |
| EasyOCR fails on Windows with `shm.dll` / `WinError 127` | A PyTorch DLL problem on that machine. PaddleOCR is used first, so either set `OCR_ENGINES=paddleocr` or reinstall torch CPU (`pip install torch --index-url https://download.pytorch.org/whl/cpu`). |
| Login works but you are logged out at once over `http://` | Set `SESSION_COOKIE_SECURE=false` for plain-HTTP testing, or use HTTPS. |
| App will not start in production | Read the log: it lists each missing/weak secret. |
| "Too many login attempts" | Wait for the `LOGIN_RATE_LIMIT` window to pass. |
| Tally sync shows `XML Generated` | Tally was unreachable at `PERMITTED_TALLY_URL`; start Tally with the XML server enabled (from Docker use `host.docker.internal`). |
| Tally sync shows `Failed` | The message is Tally's own error, usually a missing ledger. Create it in Tally and retry. |
| WhatsApp webhook verification fails | `WHATSAPP_VERIFY_TOKEN` must equal the token typed in the Meta dashboard and the URL must be public HTTPS. |
| Frontend shows network errors in `npm run dev` | Start the backend first, or set `VITE_BACKEND_URL`. |

More: [`docs/API.md`](docs/API.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/CHANGELOG.md`](docs/CHANGELOG.md), [`DOCUMENT_FEATURE_STATUS.md`](DOCUMENT_FEATURE_STATUS.md).
