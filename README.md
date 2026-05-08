# Document to Excel

A full-stack document processing MVP that uploads invoice or receipt images, runs OCR with PaddleOCR, extracts fields with regex plus an OpenRouter DeepSeek fallback, and exports the latest result to Excel.

## Stack

- Backend: Flask
- OCR: PaddleOCR
- AI parsing: OpenRouter API with `deepseek/deepseek-chat:free`
- Data handling: pandas
- Frontend: React, Tailwind CSS, AG Grid

## Project Layout

- `backend/` - Flask API, OCR, parsing, and Excel export
- `frontend/` - React UI with drag and drop upload, image preview, and editable grid

## Backend Setup

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Create `backend/.env` from `backend/.env.example` and set your OpenRouter API key.
4. Start the API:

```bash
python backend/app.py
```

The backend runs on `http://localhost:5000`.

## Frontend Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Start the dev server:

```bash
npm run dev
```

The frontend runs on `http://localhost:5173` and proxies API requests to the Flask backend.

## API

- `POST /upload` - accepts multipart form data with an `image` field, runs OCR, parses the text, and returns structured JSON.
- `GET /download` - exports the latest processed document to `.xlsx`.

## Notes

- Raw OCR text is logged on the backend for debugging.
- The frontend table is editable for quick review before export.
- PaddleOCR may require additional system-level dependencies depending on your local environment.
