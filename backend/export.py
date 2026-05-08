from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


def document_to_dataframe(document: dict[str, Any]) -> pd.DataFrame:
    items = document.get("items") or []
    item_rows = []
    for item in items:
        if isinstance(item, dict):
            item_rows.append({
                "vendor": document.get("vendor", ""),
                "date": document.get("date", ""),
                "total": document.get("total", ""),
                "description": item.get("description", ""),
                "amount": item.get("amount", ""),
                "confidence": document.get("confidence", 0.0),
            })
    if item_rows:
        return pd.DataFrame(item_rows)
    return pd.DataFrame([
        {
            "vendor": document.get("vendor", ""),
            "date": document.get("date", ""),
            "total": document.get("total", ""),
            "description": "",
            "amount": "",
            "confidence": document.get("confidence", 0.0),
        }
    ])


def export_document_to_excel_bytes(document: dict[str, Any]) -> bytes:
    dataframe = document_to_dataframe(document)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="extracted_data")
        pd.DataFrame([
            {
                "vendor": document.get("vendor", ""),
                "date": document.get("date", ""),
                "total": document.get("total", ""),
                "confidence": document.get("confidence", 0.0),
                "raw_text": document.get("raw_text", ""),
            }
        ]).to_excel(writer, index=False, sheet_name="summary")
    buffer.seek(0)
    return buffer.read()
