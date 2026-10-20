-- AI-Powered Invoice & ERP Automation Platform
-- SQLite Database Schema Definition

-- 1. Invoices & Documents Table
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    vendor TEXT,
    gstin TEXT,
    invoice_number TEXT,
    date TEXT,
    due_date TEXT,
    subtotal TEXT DEFAULT '0.00',
    cgst TEXT DEFAULT '0.00',
    sgst TEXT DEFAULT '0.00',
    igst TEXT DEFAULT '0.00',
    tax_total TEXT DEFAULT '0.00',
    total TEXT DEFAULT '0.00',
    items TEXT DEFAULT '[]', -- JSON string of line items
    confidence REAL DEFAULT 0.0,
    ocr_confidence REAL DEFAULT 0.0,
    raw_text TEXT DEFAULT '',
    status TEXT DEFAULT 'Pending Verification',
    erp_sync_status TEXT DEFAULT 'Not Synced',
    validation_warnings TEXT DEFAULT '[]', -- JSON string of warnings
    source TEXT DEFAULT 'Manual Upload',
    extra_data TEXT DEFAULT '{}', -- JSON string for arbitrary forward-compatible metadata
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_vendor ON documents(vendor);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_erp_sync ON documents(erp_sync_status);

-- 2. WhatsApp Webhook Events (Durable, Atomic Idempotency)
CREATE TABLE IF NOT EXISTS webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    sender TEXT,
    event_type TEXT DEFAULT 'whatsapp_message',
    status TEXT DEFAULT 'processed',
    payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_events_message_id ON webhook_events(message_id);

-- 3. Server-Side Session Revocation Records
CREATE TABLE IF NOT EXISTS revoked_sessions (
    session_id TEXT PRIMARY KEY,
    user TEXT,
    revoked_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_revoked_sessions_expires_at ON revoked_sessions(expires_at);
