# Project Folder Structure

This document outlines the organized folder layout of the **Document to Excel** project.

## Project Root

- `backend/` - Flask API server, OCR pipeline, and spreadsheet generator.
- `frontend/` - React SPA user interface.
- `docs/` - System architecture and developer guides.

## Backend Layout

- `app/`
  - `api/v1/` - Route endpoints.
  - `services/` - Processing controllers and orchestration logic.
  - `repository/` - In-memory database repository.
  - `parsers/` - Regex and OpenRouter parser modules.
  - `ocr/` - Local PaddleOCR and external OCR.Space runners.
  - `exports/` - Excel exporter.
  - `models/` - Dataclass templates.
  - `utils/` - Clean date/amount string utilities.
  - `config/` - Segmented configurations.
  - `logging/` - Central logging parameters.
- `logs/` - Rotating log output file logs.
- `tests/` - Standalone integration tests directory.
- `app.py` - Minimal Flask bootstrap application.

## Frontend Layout

- `src/`
  - `components/` - Subdivided layout, document-specific, and common UI panels.
  - `hooks/` - State and file previews.
  - `services/` - Server request handlers.
  - `utils/` - Grid parsers.
  - `constants/` - Copy writing.
  - `config/` - Path names.
  - `tests/` - Testing mocks and specs.
