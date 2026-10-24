# Handover report: Document_to_excel

Date: 21 October 2026. Work done on a copy of `D:\Document_to_excel`; changed and new files were written back into that folder. Your `backend/.env`, your database (`backend/data/invoices.db`), your logs and your Git history were not touched. Nothing was committed to Git.

## 1. Do these steps on your PC

1. **Install the updated packages** (gunicorn and test packages are new):
   ```powershell
   cd D:\Document_to_excel
   .venv\Scripts\activate          # or your existing virtual environment
   pip install -r backend\requirements-dev.txt
   pip install -r backend\requirements-ocr.txt   # only if PaddleOCR/EasyOCR are not installed yet
   cd frontend; npm install; cd ..
   ```
2. **Add your OpenAI key** to `backend\.env` (or a new root `.env` copied from `.env.example`):
   ```env
   AI_PROVIDER=auto
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   ```
   Your existing OpenRouter key keeps working; with `AI_PROVIDER=auto` OpenAI is used when its key is set.
3. **Run it:**
   ```powershell
   python -m backend.app              # backend on http://127.0.0.1:5000
   cd frontend; npm run dev           # app on http://localhost:5173
   ```
4. **Move the GitHub Actions files.** The tool I used is not allowed to write inside `.github`, so the two workflow files are in `deploy\github-workflows\`. Move them:
   ```powershell
   mkdir .github\workflows -Force
   move deploy\github-workflows\*.yml .github\workflows\
   ```
5. **Optional clean-up** (I cannot delete files on your PC): `backend\app\test_auto_model.py`, `backend\app\test_free_models.py` and `backend\app\config\ai_constants.py` are no longer used. `frontend\dist` is an old build; `npm run build` regenerates it.
6. **Docker** (optional): `copy .env.example .env`, fill in the secrets, `docker compose up -d --build`, open http://localhost:8080.

## Update 22 Oct: free AI option

No paid key? Get a free Google Gemini key at https://aistudio.google.com/apikey and put `GEMINI_API_KEY=...` in `backend\.env` (keep `AI_PROVIDER=auto`). Groq (`GROQ_API_KEY`, free) is also supported. With no key at all the app still runs using rule-based extraction. Tests: 162 passed.

## 2. What was built or fixed

**AI:** new `backend/app/ai/` package. OpenAI is the primary provider using Structured Outputs (strict JSON schema), with timeouts, retries/backoff on 429/5xx, and clear errors for bad key, billing, quota, unknown model and refusals. OpenRouter is still supported. AI runs only on the backend; keys are never logged or sent to the browser. If AI fails, the rule-based parser is used and the reason is shown on the invoice. AI values not found in the document text lower the confidence score, so values are not silently invented.

**Document processing:** digital PDFs use their embedded text (no OCR needed); scanned pages use PaddleOCR/EasyOCR; if OCR is unavailable, page images can go to the AI vision model. Clear 503 error when nothing can read a scanned file.

**Bugs fixed:** amounts like `1,180.00` were saved as `1.180.00` (broke totals and analytics); the rule parser took the tax rate (`9` from `CGST 9%`) as the tax amount and confused HSN codes with quantities; running the tests could wipe your real invoice database; `python -m backend.app` did not start; the old `backend/app.py` ran in debug mode open to the network; duplicated log lines.

**Validation:** GSTIN checksum and state code, CGST/SGST mismatch, IGST vs CGST/SGST conflict, low confidence and low OCR quality warnings, on top of the existing checks.

**WhatsApp:** real Meta Cloud API messages are now understood (media download through the Graph API, optional reply to the sender, safe retries). The simulator is clearly labelled and can be turned off.

**ERP/Tally:** Tally's reply is now read; an invoice is "Synced" only if Tally confirms it, "Failed" with Tally's error otherwise, "XML Generated" when Tally is offline. Ledger names and company are configurable. The custom ERP push can send an API key.

**UI:** new Dashboard tab, toast messages, confirmation before delete, full-page login, "session expired" prompt, upload progress, "Mark as verified", camera button on phones, honest status badges, mobile layout fixed. Removed fake claims (fixed accuracy/speed numbers, hard-coded endpoints and tokens).

**Deployment:** backend and frontend Dockerfiles (non-root), `docker-compose.yml` with health checks and data volumes, nginx reverse proxy with security headers, gunicorn config, `.env.example` with placeholders only, `.dockerignore`, CI and GHCR publishing workflows, rewritten README and docs.

## 3. What was verified, and how

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest backend/tests -q` | **155 passed** |
| Frontend build | `cd frontend && npm run build` | **Succeeded** |
| Production server | `gunicorn -c backend/gunicorn.conf.py "backend.app:create_app()"` | **Started**, `/api/v1/health` returned `{"status":"ok","database":true}` |
| nginx config | nginx-unprivileged container with `deploy/nginx.conf`, read-only | **`nginx -t` OK**, served the app and proxied `/api` |
| Compose file | `docker compose config -q` | **Valid** |
| Browser end-to-end (Playwright, desktop + phone size) | login, wrong password, upload digital PDF, edit + save, mark verified, Excel export, history + delete confirm, Tally offline → XML, WhatsApp simulator, dashboard, analytics, mobile layout, session expiry, logout | **All 16 steps passed** |

## 4. Not verified (be aware)

- **Full Docker image builds** did not run here: the build sandbox had no internet access for Debian/PyPI/PyTorch downloads. The Dockerfiles, compose file and nginx config were checked as above, but run `docker compose up -d --build` once on your PC (or let the CI workflow do it on GitHub) before giving it to a client.
- **Live OpenAI, OpenRouter, WhatsApp and Tally calls** were not made (no keys/accounts here). They are covered by tests with mocked responses.
- **OCR engines** were not installed in my environment, so scanned-image OCR was tested through mocks; PaddleOCR worked on your PC before. Your logs show EasyOCR failing on Windows with `shm.dll` / `WinError 127` (a PyTorch install problem); PaddleOCR is tried first, or set `OCR_ENGINES=paddleocr`.
- The GitHub Actions workflows have not run yet; they run on the first push once moved into `.github\workflows`.

## 5. Git status

53 files modified and 22 new files, plus the two new workflow files in `deploy\github-workflows\`. Nothing committed. Review with `git status` and `git diff`, then commit when you are happy.

## 6. Environment variables

The full list with explanations is in `.env.example` and the README "Environment variables" section. Minimum for production: `SECRET_KEY`, `APP_ADMIN_USERNAME`, `APP_ADMIN_PASSWORD`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, and `OPENAI_API_KEY` for AI extraction.
