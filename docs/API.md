# API Documentation

The AI-Powered Invoice & ERP Automation Platform exposes both a legacy compatibility layer and a modular REST API v1.

---

## 1. Modular REST API (`/api/v1`)

### 1.1 Health Check
- **URL**: `/api/v1/health`
- **Method**: `GET`
- **Response**: `200 OK`
```json
{
  "service": "Invoice & ERP Automation Platform",
  "status": "ok"
}
```

### 1.2 Upload & Process Document
- **URL**: `/api/v1/upload`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file` or `image` (binary file): Supported formats: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp` (up to 16 MiB). Validated with file extension and magic byte inspection.
- **Response**: `200 OK` (JSON document object)
```json
{
  "id": "doc-uuid-string",
  "vendor": "Acme Supplies Ltd",
  "gstin": "27AABCU9603R1ZM",
  "invoice_number": "INV-2026-0042",
  "date": "2026-04-15",
  "due_date": "2026-04-30",
  "subtotal": "1000.00",
  "cgst": "90.00",
  "sgst": "90.00",
  "igst": "0.00",
  "tax_total": "180.00",
  "total": "1180.00",
  "items": [
    {
      "description": "Office Supplies Box",
      "hsn_sac": "8471",
      "qty": "2",
      "unit_price": "500.00",
      "tax_rate": "18%",
      "tax_amount": "180.00",
      "amount": "1000.00"
    }
  ],
  "confidence": 0.95,
  "ocr_confidence": 0.92,
  "raw_text": "Full extracted OCR text...",
  "status": "Pending Verification",
  "erp_sync_status": "Not Synced",
  "validation_warnings": [],
  "created_at": "2026-04-15T10:00:00"
}
```

### 1.3 List All Invoices
- **URL**: `/api/v1/documents`
- **Method**: `GET`
- **Response**: `200 OK` (array of invoice objects)

### 1.4 Get Invoice by ID
- **URL**: `/api/v1/documents/<doc_id>`
- **Method**: `GET`
- **Response**: `200 OK` or `404 Not Found`

### 1.5 Update Invoice Corrections
- **URL**: `/api/v1/documents/<doc_id>`
- **Method**: `PUT`
- **Content-Type**: `application/json`
- **Payload**: JSON object containing fields to update (e.g. `vendor`, `total`, `items`, etc.). Immutable fields (`id`, `created_at`) cannot be overwritten.
- **Validation**: Server automatically strips any client-submitted `validation_warnings`, re-runs the authoritative `ValidationEngine`, and recalculates `status` (`Flagged Error` vs `Pending Verification`).
- **Response**: `200 OK` (canonical updated document) or `400 Bad Request` or `404 Not Found`.

### 1.6 Delete Invoice
- **URL**: `/api/v1/documents/<doc_id>`
- **Method**: `DELETE`
- **Response**: `200 OK` (`{"status": "deleted", "id": "<doc_id>"}`) or `404 Not Found`.

### 1.7 Export Document
- **URL**: `/api/v1/documents/<doc_id>/export/<format_type>`
- **Method**: `GET`
- **URL Parameters**:
  - `doc_id`: Invoice UUID or `latest`
  - `format_type`: `excel`, `csv`, `doc`, or `tally`
- **Response**:
  - `excel`: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` binary attachment
  - `csv`: `text/csv` attachment
  - `doc`: `text/plain` summary attachment
  - `tally`: `application/xml` Tally voucher attachment

### 1.8 Financial Analytics
- **URL**: `/api/v1/analytics`
- **Method**: `GET`
- **Response**: `200 OK`
```json
{
  "total_spend": 125000.0,
  "total_tax": 22500.0,
  "total_invoices": 15,
  "flagged_invoices": 1,
  "synced_invoices": 8,
  "vendors_summary": [
    {"vendor": "Acme Supplies Ltd", "invoice_count": 5, "total_spend": 45000.0}
  ]
}
```

### 1.9 ERP Synchronization
- **URL**: `/api/v1/documents/<doc_id>/sync-erp`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "erp_type": "tally",
    "tally_url": "http://localhost:9000"
  }
  ```
  or for custom ERP:
  ```json
  {
    "erp_type": "custom",
    "custom_endpoint": "https://erp.example.com/api/v1/invoices"
  }
  ```
- **Security**: Custom ERP URLs are validated via `url_validator` to reject loopback, link-local, cloud metadata (`169.254.169.254`), and non-HTTPS endpoints.
- **Response**: `200 OK` or `400 Bad Request`.

### 1.10 WhatsApp Automation Webhook
- **URL**: `/api/v1/whatsapp/webhook`
- **Methods**:
  - `GET`: Webhook verification challenge (`hub.mode`, `hub.verify_token`, `hub.challenge`).
  - `POST`: Incoming invoice intake. Expects JSON with `image_url` or `media_url` and optional `from` phone number. Media URLs are strictly SSRF-validated before fetching.

---

## 2. Legacy Compatibility Layer

For backward compatibility with early scripts and curl snippets:
- `GET /` — API root status.
- `GET /health` — Legacy health check.
- `POST /upload` — Multipart upload returning extracted JSON.
- `GET /download` — Downloads the latest extracted document as Excel.
