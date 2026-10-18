# Changelog

All notable changes to the **Document to Excel** codebase are documented here.

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
