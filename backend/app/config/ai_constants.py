# AI Parsing parameters

AI_TIMEOUT = 60
DEFAULT_AI_CONFIDENCE = 0.9

def build_prompt(text: str) -> str:
    return (
        "You extract structured invoice or receipt data. Return ONLY valid JSON with this exact schema:\n"
        '{"vendor":"","date":"","total":"","items":[]}\n'
        "Rules:\n"
        "- Output must be raw JSON only. No markdown, no code fences, no commentary.\n"
        "- vendor, date, and total must be strings.\n"
        "- items must be an array. Use objects with description and amount when possible.\n"
        "- If data is missing, use empty strings or empty arrays.\n"
        "OCR TEXT:\n"
        f"{text}"
    )
