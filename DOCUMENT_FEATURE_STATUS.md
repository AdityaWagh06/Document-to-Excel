# Feature Status

> **Project:** AI-Powered Invoice & ERP Automation Platform (DocExtract Pro)
> **Last updated:** 21 October 2026

This file states what is implemented, how it was verified, and what still depends on outside services or accounts. "Verified" means checked by the automated test suite or by a browser run of the app; "needs a live account" means the code is written and tested against mocked responses but has not been exercised against the real service.

## Summary

| Area | Status | Notes |
|---|---|---|
| Upload (PDF, PNG, JPG, WEBP; mobile camera) | Done, verified | Extension + file signature checks, size and page limits |
| Text reading: digital PDFs | Done, verified | Embedded text layer used, no OCR needed |
| Text reading: scanned PDFs/images | Done | Needs local OCR (`requirements-ocr.txt` / `INSTALL_OCR=true`) or an AI key for vision fallback |
| AI extraction (OpenAI Structured Outputs) | Done, tested with mocked API | Needs `OPENAI_API_KEY` with billing; not run against the live API during development |
| AI extraction (OpenRouter) | Done, tested with mocked API | Optional |
| Rule-based extraction (no AI) | Done, verified | Indian GST invoices; accuracy depends on layout |
| Validation | Done, verified | Required fields, GSTIN format + checksum + state code, tax maths, line items, duplicates, confidence |
| Human review and correction | Done, verified | Edit, save (server re-validates), mark verified |
| Export: Excel, CSV, text summary, Tally XML | Done, verified | |
| History, search, delete | Done, verified | |
| Dashboard and analytics | Done, verified | |
| Tally sync | Done, tested with simulated Tally responses | Needs TallyPrime with XML server and matching ledgers; offline produces downloadable XML |
| Custom ERP push | Done, tested with mocked endpoint | JSON POST with optional Bearer key |
| WhatsApp Cloud API intake + replies | Done, tested with mocked Graph API | Needs a Meta WhatsApp Business app and public HTTPS URL |
| WhatsApp simulator | Done, verified | Clearly labelled as simulated |
| Login, sessions, CSRF, rate limit, API key | Done, verified | Single admin account from `.env` |
| SQLite persistence, webhook idempotency, session revocation | Done, verified | |
| Docker / Compose / nginx / gunicorn | Done | Compose file validated, gunicorn and nginx config run successfully; full image builds must be confirmed on a machine with normal internet (see README) |
| GitHub Actions CI + GHCR publishing | Written | Runs on first push to GitHub |

## Not included

- Multiple user accounts / roles (one admin login).
- Connectors for SAP, Zoho, QuickBooks.
- Automatic creation of Tally ledgers or stock items.
- Storage of the original uploaded file (only extracted data and text are kept).
- Google Vision / OCR.Space cloud OCR (removed; OpenAI vision is the cloud fallback).

## Accuracy note

No accuracy percentage is claimed. Extraction quality depends on document quality, layout and the AI model used. Every invoice gets a confidence score, values the AI returned that are not found in the document text are flagged, and a person can correct every field before export.

## Where things are in the code

| Feature | Code |
|---|---|
| AI providers and schema | `backend/app/ai/` |
| Extraction and fallback | `backend/app/parsers/document_parser.py` |
| Text layer and OCR | `backend/app/ocr/ocr_engine.py` |
| Processing pipeline | `backend/app/services/document_service.py` |
| Validation | `backend/app/services/validation_service.py` |
| ERP / Tally | `backend/app/services/erp_service.py`, `backend/app/exports/tally_exporter.py` |
| WhatsApp | `backend/app/api/v1/whatsapp_routes.py` |
| Settings | `backend/app/config/settings.py`, `.env.example` |
| UI | `frontend/src/components/` |
