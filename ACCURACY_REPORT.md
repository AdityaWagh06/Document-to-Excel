# Extraction accuracy report

Run on 2026-10-22 against the code now in `D:\Document_to_excel`.

## Result

| Mode | Fields correct |
|---|---|
| Rule-based parser only (no AI) | 39 / 67 (58%) |
| Gemini, OCR text only | 49 / 49 (100%, the 6 photo/scan bills) |
| Gemini, OCR text + page image (what the app now does) | 67 / 67 (100%) |

Every AI run kept the bill's own currency (USD, INR, GBP, AED, EUR). Nothing was converted.

## Per document

| Document | Currency | Rules | AI text | AI text + image |
|---|---|---|---|---|
| US grocery receipt (photo) | USD | 3/6 | 6/6 | 6/6 |
| US restaurant bill with tip | USD | 4/9 | 9/9 | 9/9 |
| Indian GST invoice (photo, CGST+SGST) | INR | 7/10 | 10/10 | 10/10 |
| Indian IGST invoice (scan) | INR | 7/9 | 9/9 | 9/9 |
| UK cafe receipt | GBP | 2/7 | 7/7 | 7/7 |
| UAE supermarket receipt | AED | 4/8 | 8/8 | 8/8 |
| German invoice (digital PDF) | EUR | 2/8 | n/a | 8/8 |
| Indian invoice (digital PDF) | INR | 10/10 | n/a | 10/10 |

Digital PDFs have a real text layer, so no image is sent for them. That is why "AI text" is n/a for them.

Fields checked per document: vendor, invoice number, date, GSTIN (Indian bills), currency, subtotal, CGST/SGST/IGST or tax, tip/other charges, total, and the number of line items. Amounts must match to the cent.

## What this does and does not prove

- These are 8 synthetic bills I generated with known answers. They are not your real bills. Real crumpled or low-light photos will be harder.
- The sandbox could not download PaddleOCR's models, so RapidOCR (same family of models) produced the OCR text. Your PC uses PaddleOCR.
- It ran on the free Gemini tier. That tier allows about 20 requests per day **per model**, so some bills were read by `gemini-3.5-flash` and others by the `gemini-flash-lite-latest` fallback. Both scored 100% here.
- The OCR in the sandbox read these clean synthetic images well, so text-only AI also scored 100%. The image matters on real photos: your US receipt's OCR read "$25.97" as "525.97". A unit test reproduces that exact case and checks that the image-assisted path returns 25.97 USD.
- The Indian IGST sample uses a made-up GSTIN, so the app correctly warns that its checksum is invalid.

## Why the US bill showed rupees before

1. The app had the ₹ sign hard-coded across the screen, exports and dashboard.
2. OCR turned the "$" in "$25.97" into a "5", and the AI only saw that text.

Now each invoice stores its currency code, the AI also sees the page image, and every screen and export shows the invoice's own currency. Totals in other currencies are listed separately on the dashboard and never added together.
