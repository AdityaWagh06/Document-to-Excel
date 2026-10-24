# API Documentation

The AI-Powered Invoice & ERP Automation Platform exposes a secure modular REST API v1 along with legacy compatibility routes.

---

## 1. Authentication & Security Architecture

### 1.1 Endpoint Protection Scope

| Endpoint Category | Endpoints | Access Control | CSRF Required? |
| :--- | :--- | :--- | :--- |
| **Public Endpoints** | `GET /health`, `GET /api/v1/health`<br>`GET /`, `GET /api/v1/`<br>`GET /favicon.ico`<br>`GET /api/v1/auth/session`<br>`POST /api/v1/auth/login` | Public (Unauthenticated) | No |
| **Meta WhatsApp Webhook** | `GET /api/v1/whatsapp/webhook`<br>`POST /api/v1/whatsapp/webhook` | Meta Verified (`hub.verify_token` for GET, `X-Hub-Signature-256` HMAC-SHA256 for POST) | Exempt (Webhook HMAC) |
| **Protected Invoices & Processing** | `POST /api/v1/upload`, `POST /upload`<br>`GET /api/v1/documents`, `GET /documents`<br>`GET /api/v1/documents/<id>`<br>`PUT /api/v1/documents/<id>`<br>`DELETE /api/v1/documents/<id>`<br>`GET /api/v1/analytics`, `GET /analytics`<br>`GET /api/v1/download`, `GET /download`<br>`GET /api/v1/documents/<id>/export/<format>`<br>`POST /api/v1/documents/<id>/sync-erp`<br>`POST /api/v1/whatsapp/simulate` | Requires Active Session or Valid `X-API-Key` | **Yes** on state-changing methods (`POST`, `PUT`, `DELETE`, `PATCH`) when authenticated via session cookie |

### 1.2 Authentication Methods

#### Method A: Server-Managed Session Cookies (Browser UI)
- **Login**: `POST /api/v1/auth/login` with credentials.
- **Session Cookie**: Sets a cryptographically signed `session` cookie with `HttpOnly`, `SameSite=Lax`, and `Secure` (over HTTPS).
- **CSRF Token**: Login and `/session` endpoints provide a 32-byte hexadecimal `csrf_token`.
- **State-Changing Requests**: Any `POST`, `PUT`, or `DELETE` request authenticated via cookies must include header:
  `X-CSRF-Token: <token>`
- **Failures**:
  - Missing or invalid session: `401 Unauthorized` (`{"error": "Authentication required. Please log in."}`).
  - Missing or invalid CSRF token: `403 Forbidden` (`{"error": "CSRF validation failed. Missing or invalid CSRF token."}`).

#### Method B: Programmatic API Key (Machine-to-Machine / Testing)
- Pass header: `X-API-Key: <API_SECRET_KEY>` or `Authorization: Bearer <API_SECRET_KEY>`.
- API key requests do not rely on ambient browser cookies and therefore bypass CSRF checks.

---

## 2. Authentication Endpoints (`/api/v1/auth`)

### 2.1 User Login
- **URL**: `/api/v1/auth/login`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "username": "admin",
    "password": "your_secure_password"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "status": "authenticated",
    "user": "admin",
    "csrf_token": "a1b2c3d4e5f6..."
  }
  ```
- **Errors**:
  - `400 Bad Request`: Missing or malformed payload.
  - `401 Unauthorized`: Invalid credentials (constant-time verification).
  - `429 Too Many Requests`: Exceeded login rate limit (default 5 failed attempts per 5 minutes per client IP; includes `Retry-After` and `X-RateLimit-*` headers).

### 2.2 User Logout
- **URL**: `/api/v1/auth/logout`
- **Method**: `POST`
- **Headers**: `X-CSRF-Token: <token>` (if session-authenticated)
- **Response**: `200 OK`
  ```json
  {
    "status": "logged_out",
    "message": "Successfully logged out."
  }
  ```
- **Durable Revocation**: Persists the session identifier into the SQLite `revoked_sessions` table. Any subsequent requests attempting to reuse the revoked session cookie are immediately blocked with `401 Unauthorized` (`{"error": "Session has been revoked or logged out. Please log in again."}`).

### 2.3 Session Status
- **URL**: `/api/v1/auth/session`
- **Method**: `GET`
- **Response**: `200 OK`
  ```json
  {
    "authenticated": true,
    "user": "admin",
    "csrf_token": "a1b2c3d4e5f6..."
  }
  ```

---

## 3. WhatsApp Automation & Webhook (`/api/v1/whatsapp`)

### 3.1 Webhook Verification Challenge (Meta Setup)
- **URL**: `/api/v1/whatsapp/webhook`
- **Method**: `GET`
- **Query Parameters**:
  - `hub.mode`: `"subscribe"`
  - `hub.verify_token`: Must match configured `WHATSAPP_VERIFY_TOKEN` (verified in constant time).
  - `hub.challenge`: Arbitrary string returned verbatim on match.
- **Response**: `200 OK` with challenge string, or `403 Forbidden` on token mismatch.

### 3.2 Incoming Message Intake (Meta POST Webhook)
- **URL**: `/api/v1/whatsapp/webhook`
- **Method**: `POST`
- **Headers**:
  - `X-Hub-Signature-256: sha256=<hmac_sha256_hex>` (MANDATORY)
  - `Content-Type: application/json`
- **Signature Verification**:
  1. Computes expected HMAC-SHA256 signature using `WHATSAPP_APP_SECRET` over exact raw request body bytes.
  2. Compares signature in constant time using `hmac.compare_digest`.
  3. Rejects missing, malformed, or invalid signatures with `401 Unauthorized` BEFORE parsing JSON or fetching media URLs.
- **Payload**: either the standard Meta WhatsApp Cloud API notification (`entry[].changes[].value.messages[]` with an `image` or `document` message; the media is downloaded from the Graph API using `WHATSAPP_ACCESS_TOKEN`), or the legacy simple form:
  ```json
  {
    "media_url": "https://example.com/invoice.png",
    "from": "+919876543210"
  }
  ```
- **Non-media events**: status updates and text messages are acknowledged with `200 OK` (`"status": "ignored"`) so Meta does not retry them.
- **Retries**: if processing fails for a temporary reason (network, OCR unavailable), the event registration is released and `500` is returned so Meta's retry is processed. Permanent problems (unsupported file, missing configuration) return `200` with an error status to stop retries.
- **Defense**: Media URLs are SSRF-validated (rejecting private IPs, localhost, and non-HTTPS schemes) before image download.
- **Atomic Idempotency & Deduplication**: The webhook extracts Meta message identifiers (`id`, `message_id`, or `wamid`) and registers them in the SQLite `webhook_events` table under an atomic unique constraint. If Meta or a client retries a previously delivered event:
  - Image download and OCR parsing are bypassed completely.
  - The endpoint returns `200 OK` with:
    ```json
    {
      "status": "duplicate",
      "message": "Event already processed.",
      "message_id": "wamid.HBgL..."
    }
    ```
- **Response**: `200 OK` with the processed document. When `WHATSAPP_SEND_REPLIES=true` and `WHATSAPP_ACCESS_TOKEN`/`WHATSAPP_PHONE_NUMBER_ID` are set, a summary reply is sent to the sender.

### 3.3 WhatsApp Simulation (Browser Testing)
- **URL**: `/api/v1/whatsapp/simulate`
- **Method**: `POST` (Protected: requires session + CSRF or API key)
- **Content-Type**: `multipart/form-data`
- **Parameters**: `image` (binary file), `sender` (phone string).
- **Availability**: disabled (`404`) when `WHATSAPP_SIMULATOR_ENABLED=false`.
- **Response**: `200 OK` with the processed document, the reply text and `"simulated": true`. Nothing is sent to WhatsApp.

---

## 4. Invoice Processing & Persistence API (`/api/v1`)

### 4.1 Health Check
- **URL**: `/api/v1/health`
- **Method**: `GET` (Public, used by Docker health checks)
- **Response**: `200 OK` `{"service": "...", "status": "ok", "database": true}`, or `503` with `"status": "degraded"` when the database is unreachable.

### 4.2 System Status
- **URL**: `/api/v1/system/status` (Protected)
- **Method**: `GET`
- **Response**: `200 OK` with configuration flags only (never secrets): `ai` (provider, model, configured, errors), `ocr` (engines available), `erp` (Tally URL, company, custom endpoint configured), `whatsapp` (secrets/access token configured, simulator enabled) and upload `limits`.

### 4.3 Upload & Process Document
- **URL**: `/api/v1/upload` (Protected)
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file` or `image` (binary file): `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp` (up to `MAX_UPLOAD_SIZE_BYTES`). Validated by extension and magic bytes.
- **Response**: `200 OK` (JSON document object, including `extraction_method` (`ai`, `ai_vision`, `rules`), `ai_model`, `extraction_notes`, `confidence`, `ocr_confidence`, `warnings`, `status`).
- **Errors**: `400` invalid/unsupported/corrupt file, `413` too large, `422` no text could be read, `503` no OCR engine and no AI vision available for a scanned document.

### 4.4 List Invoices
- **URL**: `/api/v1/documents` (Protected)
- **Method**: `GET`
- **Response**: `200 OK` (array of saved documents).

### 4.5 Get Invoice by ID
- **URL**: `/api/v1/documents/<doc_id>` (Protected)
- **Method**: `GET`
- **Response**: `200 OK` or `404 Not Found`.

### 4.6 Save Invoice Corrections
- **URL**: `/api/v1/documents/<doc_id>` (Protected)
- **Method**: `PUT`
- **Headers**: `Content-Type: application/json`, `X-CSRF-Token: <token>`
- **Payload**: Updated document fields (e.g. `vendor`, `total`, `items`). `status` may be set to `Pending` or `Verified`; `Verified` is refused while validation errors remain. `erp_status` must be one of `Not Synced`, `Synced`, `XML Generated`, `Failed`.
- **Validation**: Server strips client warnings, re-runs authoritative validation and recomputes `status`.
- **Response**: `200 OK` (updated document), `400 Bad Request` or `404 Not Found`.

### 4.7 Delete Invoice
- **URL**: `/api/v1/documents/<doc_id>` (Protected)
- **Method**: `DELETE`
- **Headers**: `X-CSRF-Token: <token>`
- **Response**: `200 OK` (`{"status": "deleted", "id": "<doc_id>"}`) or `404 Not Found`.

### 4.8 Export Document
- **URL**: `/api/v1/documents/<doc_id>/export/<format_type>` (Protected)
- **Method**: `GET`
- **Parameters**: `format_type`: `excel`, `csv`, `doc` (text summary) or `tally` (XML voucher).
- **Response**: Binary or text attachment with a sanitised file name based on the invoice number.

### 4.9 Spend Analytics
- **URL**: `/api/v1/analytics` (Protected)
- **Method**: `GET`
- **Response**: `200 OK` (totals, GST totals, status counts, spend by vendor and by month for the last 12 months).

### 4.10 ERP Synchronization
- **URL**: `/api/v1/documents/<doc_id>/sync-erp` (Protected). `<doc_id>` may be `latest` for the most recently processed invoice.
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`, `X-CSRF-Token: <token>`
- **Payload**: `{"erp_type": "tally"}` (optional `tally_url`, which must equal `PERMITTED_TALLY_URL`) or `{"erp_type": "custom"}` (optional `custom_endpoint`; defaults to `CUSTOM_ERP_ENDPOINT`).
- **Result `erp_status`**: `Synced` (Tally reported the voucher created with no errors, or the custom ERP returned 2xx), `Failed` (Tally's error message is returned), `XML Generated` (Tally unreachable; download the XML via the export endpoint).
- **Security**: URLs are validated against SSRF and cloud metadata access. Invoices missing vendor, invoice number or total are refused.
