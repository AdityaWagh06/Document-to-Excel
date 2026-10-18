# AI-Powered Invoice & ERP Automation Platform

An automated platform for document ingestion, optical character recognition (OCR), structured invoice extraction, rule-based auditing, multi-format export, and ERP/accounting synchronization.

The system extracts vendor details, GSTIN, invoice numbers, dates, line items (descriptions, HSN/SAC codes, quantities, rates, amounts), and tax breakdowns (CGST, SGST, IGST) from PDFs and images using local open-source OCR engines (PaddleOCR + EasyOCR) and AI heuristics.

> 📋 **Detailed Requirement & Implementation Matrix**: See [`DOCUMENT_FEATURE_STATUS.md`](DOCUMENT_FEATURE_STATUS.md) for the complete breakdown of features and roadmap items.

---

## Prerequisites & Supported Runtimes

* **Operating Systems**: Windows 10/11, macOS, or Linux (Ubuntu 20.04+).
* **Python Runtime**: Python 3.9, 3.10, or 3.11 (tested on Windows with Python 3.9.9).
* **Node.js Runtime**: Node.js 18.x or 20.x with npm 9.x+.
* **Hardware**: Minimum 4 GB RAM (8 GB+ recommended for local OCR model inference).

---

## Architecture Overview

The system uses a decoupled client-server architecture:
- **Backend**: Flask REST API organized into domain subpackages (`api/v1`, `services`, `repository`, `parsers`, `ocr`, `exports`, `models`, `config`, `utils`).
- **Frontend**: Single-Page Application (SPA) built with React 18, Vite, Tailwind CSS, and AG-Grid.

```
backend/
├── app/
│   ├── api/v1/          # Flask Blueprints, REST endpoints & WhatsApp webhook
│   ├── services/        # Orchestration layer, ValidationEngine & ERPConnectorService
│   ├── repository/      # Thread-safe persistent document repository (temp/documents.json)
│   ├── parsers/         # Regex heuristics, Indian GST rules & AI parsing fallback
│   ├── ocr/             # Preprocessing, PyMuPDF multi-page rendering & OCR pipeline
│   ├── exports/         # Excel (.xlsx), CSV, DOC summary & Tally XML voucher builders
│   ├── models/          # Native python dataclasses (ParsedDocument, ParsedItem, OCRResult)
│   ├── config/          # Central settings, regex patterns, and AI constants
│   ├── app_logging/     # Structured log rotation configuration
│   └── utils/           # Text sanitization and SSRF outbound URL validator
├── logs/                # Rotated application logs
├── tests/               # Automated regression tests (Security, PDF, Persistence)
└── app.py               # Minimal Flask entrypoint & backward compatibility wrapper

frontend/
├── src/
│   ├── components/      # UI components (Scanner, History, ERP Sync, WhatsApp, Analytics)
│   ├── hooks/           # Custom React hooks (useDocumentProcessor, useFilePreview)
│   ├── services/        # Centralized HTTP API services (api.js)
│   ├── utils/           # Grid mapping & calculation helpers (gridHelpers.js)
│   ├── constants/       # User-facing strings and copy
│   └── config/          # API endpoint configuration
```

---

## How Document Processing Works

1. **Upload & Format Validation**: The system accepts `.pdf`, `.png`, `.jpg`, `.jpeg`, and `.webp` files (up to 16 MiB). File extensions and binary magic bytes (`%PDF-`, `\x89PNG`, `\xff\xd8\xff`, `RIFF...WEBP`) are verified before processing to prevent extension spoofing.
2. **Multi-Page PDF Rendering**: Multi-page PDFs are processed using PyMuPDF (`fitz`). Each page is rendered into a high-resolution 150 DPI raster image buffer in memory. Encrypted and corrupt PDFs are safely rejected with descriptive error messages.
3. **Local OCR Pipeline**:
   - PaddleOCR runs as the primary high-accuracy local OCR engine.
   - EasyOCR acts as the secondary engine.
   - Bounding boxes are clustered into text lines based on spatial proximity.
4. **Structured Parsing**:
   - Indian GSTIN 15-character regex and state code validation.
   - Multi-pattern invoice number, date, and due date normalization (ISO format).
   - Table line-item extraction with HSN/SAC code detection, quantities, rates, and amounts.
   - Tax breakdown (CGST, SGST, IGST) and mathematical total reconciliation.
5. **LLM Gateway Parsing (Optional)**: If local heuristic confidence is low and an `OPENROUTER_API_KEY` is configured, the system calls the OpenRouter gateway API (`openrouter/auto`) for structured JSON extraction. *(Note: AI parsing uses OpenRouter as an API gateway; direct OpenAI API access is not configured.)*
6. **Authoritative Backend Validation**:
   - Re-runs business rules on every upload and edit.
   - Detects duplicate invoices, missing mandatory fields, GST format errors, tax mismatches, and line-item math discrepancies.
   - Dynamically marks status (`Flagged Error` vs `Pending Verification`).
7. **Multi-Format Export**: Generates multi-sheet Excel files (`openpyxl`), CSV files, text summaries, and Tally Prime / Tally ERP 9 purchase voucher XML (`<VOUCHER VCHTYPE="Purchase">`).

---

## Configuration & Environment Variables

Configure your settings in `backend/.env` (refer to [`backend/.env.example`](backend/.env.example)):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | *(None)* | Optional API key for AI fallback parsing via OpenRouter. |
| `OPENROUTER_MODEL` | `openrouter/auto` | OpenRouter model identifier. |
| `FLASK_ENV` | `development` | Flask runtime mode (`development` or `production`). |
| `PORT` | `5000` | Backend API port. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of trusted frontend origins. |
| `PERMITTED_TALLY_URL` | `http://localhost:9000` | Strictly bounded loopback endpoint for Tally XML integration. |
| `MAX_UPLOAD_SIZE_BYTES`| `16777216` | Maximum file upload size in bytes (16 MiB). |
| `MAX_PDF_PAGES` | `20` | Maximum pages permitted per uploaded PDF invoice. |
| `PDF_RENDER_DPI` | `150` | DPI resolution for PDF page rasterization. |
| `WHATSAPP_VERIFY_TOKEN`| `your_whatsapp_verify_token_here` | Challenge token for WhatsApp Business Cloud API webhooks. |

### Outbound URL Validation & SSRF Protection
- Outbound requests to custom ERP endpoints and WhatsApp media URLs are validated via `url_validator.py`.
- Insecure `http://` schemes, loopback addresses (`127.0.0.0/8`, `localhost`), link-local (`169.254.0.0/16`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and multicast addresses are blocked.
- Redirects are validated at each hop.
- *Limitation*: Standard DNS pre-validation cannot fully prevent DNS rebinding attacks at socket connection time. In high-assurance production deployments, configure an egress proxy or firewall policy.

---

## Installation & Setup

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/AdityaWagh06/Document-to-Excel.git
cd Document_to_excel

# Create and activate Python virtual environment
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env

# Run the Flask backend
python -m backend.app
```
The backend API server will start on `http://localhost:5000`.

### 2. Frontend Setup

```bash
# Open a new terminal in the frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
The frontend interface will open at `http://localhost:5173`.

### 3. Building for Production

```bash
cd frontend
npm run build
```
Build output is emitted to `frontend/dist/`.

---

## Running Automated Tests

Run the backend regression and security test suite:
```bash
# From the project root
python -m unittest discover -s backend/tests
```

The test suite includes:
- **`test_security.py`** (30 tests): Secret scrubbing, SSRF outbound URL validator, upload size and magic byte checks, CORS headers, and webhook verify tokens.
- **`test_pdf_processing.py`** (25 tests): Multi-page rendering, encryption checks, page limits, OCR integration, and Windows file handle safety.
- **`test_document_updates.py`** (10 tests): Persistence of corrections, GET consistency, 404/400 validation, rule recalculation, immutability, export consistency, and analytics.

---

## Known Limitations & Production Handover Notes

1. **Authentication & Multi-Tenancy**: The application currently operates as a single-workspace local tool. User logins, session tokens, and tenant isolation are planned for Phase 3 (see [`docs/ROADMAP.md`](docs/ROADMAP.md)).
2. **Persistence Storage**: Invoices are persisted to local JSON (`backend/temp/documents.json`) with an in-memory fallback. For enterprise multi-user concurrency, migration to PostgreSQL with SQLAlchemy is recommended (Phase 2).
3. **Camera Capture**: Live camera input utilizes the standard browser file picker (`accept="image/*" capture="environment"`).
4. **External Integrations**:
   - **Tally**: Requires Tally Prime or Tally ERP 9 running locally with XML server enabled on `http://localhost:9000`.
   - **WhatsApp**: Requires an active Meta WhatsApp Business Cloud API account pointing to `/api/v1/whatsapp/webhook`.
   - **AI Extraction**: Requires an active OpenRouter API key configured in `backend/.env`. Without an API key, the system relies entirely on local regex and OCR heuristics.
5. **Windows File Locks**: Ensure file handles are explicitly closed before removing temporary PDF raster buffers on Windows.

---

## Documentation Links

* [Feature Implementation Matrix](DOCUMENT_FEATURE_STATUS.md)
* [System Architecture](docs/ARCHITECTURE.md)
* [REST API Documentation](docs/API.md)
* [Project Folder Structure](docs/FOLDER_STRUCTURE.md)
* [Changelog](docs/CHANGELOG.md)
* [Development Roadmap](docs/ROADMAP.md)
