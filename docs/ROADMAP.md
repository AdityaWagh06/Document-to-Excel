# Roadmap

Done: SQLite persistence, session authentication, OpenAI structured extraction, Docker deployment, CI.

## Possible next steps

- **Multiple users and roles.** Today there is one admin account from `.env`. Add user accounts with reviewer/approver roles and an audit trail of who changed what.
- **PostgreSQL option** for multi-host deployments (the repository classes already isolate storage).
- **Background processing queue** (e.g. RQ/Celery + Redis) so long multi-page OCR jobs and WhatsApp messages do not occupy web workers.
- **Original file storage** (local volume or S3-compatible) so reviewers can reopen the source document from history.
- **More ERP connectors** (Zoho Books, QuickBooks, SAP) and automatic creation of missing Tally ledgers.
- **Bulk upload and bulk export** of many invoices into one spreadsheet.
- **Frontend tests** (component tests and the Playwright flow used during development) in CI.
