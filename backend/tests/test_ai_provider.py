"""
Tests for the AI provider abstraction and AI-assisted parsing.
All HTTP calls are mocked; no API keys or network access are required.
"""
import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import requests

from backend.app.ai import AIProviderError, describe_ai_config, get_provider
from backend.app.ai.providers import GeminiProvider, GroqProvider, OpenAIProvider, OpenRouterProvider
from backend.app.config.settings import settings
from backend.app.parsers.document_parser import parse_document

OCR_TEXT = """ACME Industrial Supplies Pvt Ltd
GSTIN: 27AAPFU0939F1ZV
Invoice No: INV-2026-0042
Date: 12/03/2026
Steel Bolts 7318 10 50.00 500.00
Subtotal 1,000.00
CGST 9% 90.00
SGST 9% 90.00
Grand Total 1,180.00
"""

AI_PAYLOAD = {
    "vendor": "ACME Industrial Supplies Pvt Ltd",
    "gstin": "27AAPFU0939F1ZV",
    "invoice_number": "INV-2026-0042",
    "date": "2026-03-12",
    "due_date": "",
    "subtotal": "1000.00",
    "cgst": "90.00",
    "sgst": "90.00",
    "igst": "",
    "tax_total": "180.00",
    "total": "1,180.00",
    "currency": "INR",
    "items": [{
        "description": "Steel Bolts", "hsn_sac": "7318", "qty": "10", "unit_price": "50.00",
        "tax_rate": "18%", "tax_amount": "90.00", "amount": "500.00",
    }],
}


def _response(status=200, body=None, headers=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = body if body is not None else {}
    resp.text = json.dumps(body) if body is not None else ""
    return resp


def _completion(content, finish_reason="stop"):
    return _response(200, {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]})


def ai_settings(provider="openai", **overrides):
    """Patches the global settings object for the duration of a test."""
    values = {
        "ai_provider": provider,
        "openai_api_key": "sk-test-key-not-real" if provider == "openai" else None,
        "openai_model": "gpt-4o-mini",
        "openrouter_api_key": "or-test-key-not-real" if provider == "openrouter" else None,
        "openrouter_model": "openai/gpt-4o-mini",
        "openrouter_fallback_models": [],
        "gemini_api_key": "gm-test-key-not-real" if provider == "gemini" else None,
        "gemini_model": "gemini-flash-latest",
        "gemini_fallback_models": [],
        "groq_api_key": "gq-test-key-not-real" if provider == "groq" else None,
        "groq_model": "llama-3.3-70b-versatile",
        "ai_max_retries": 2,
        "ai_timeout_seconds": 5.0,
    }
    values.update(overrides)
    stack = ExitStack()
    for key, value in values.items():
        stack.enter_context(patch.object(settings, key, value))
    return stack


@patch("backend.app.ai.providers.time.sleep", lambda *_: None)
class TestOpenAIProvider(unittest.TestCase):
    def test_success_uses_structured_outputs_and_bearer_key(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion(json.dumps(AI_PAYLOAD))
            result = get_provider().extract_invoice(OCR_TEXT)

        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.extraction.invoice_number, "INV-2026-0042")
        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(body["model"], "gpt-4o-mini")
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(headers["Authorization"], "Bearer sk-test-key-not-real")

    def test_retries_on_rate_limit_then_succeeds(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = [
                _response(429, {"error": {"message": "Rate limit reached"}}),
                _completion(json.dumps(AI_PAYLOAD)),
            ]
            result = get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(result.extraction.vendor, AI_PAYLOAD["vendor"])

    def test_auth_error_is_not_retried(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _response(401, {"error": {"message": "Incorrect API key provided"}})
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "auth")
        self.assertEqual(post.call_count, 1)
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))
        self.assertNotIn("sk-test-key-not-real", str(ctx.exception))

    def test_quota_error_classified(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _response(429, {"error": {"message": "You exceeded your current quota"}})
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "quota")
        self.assertEqual(post.call_count, 1)

    def test_timeout_retried_then_reported(self):
        with ai_settings("openai", ai_max_retries=1), patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = requests.Timeout("read timed out")
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "timeout")
        self.assertEqual(post.call_count, 2)

    def test_invalid_json_response(self):
        with ai_settings("openai", ai_max_retries=0), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion("this is not json")
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "invalid_response")

    def test_truncated_output_rejected(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion('{"vendor": "AC', finish_reason="length")
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "truncated")

    def test_model_rejecting_temperature_is_retried_without_it(self):
        with ai_settings("openai", openai_model="gpt-5"), patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = [
                _response(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0"}}),
                _completion(json.dumps(AI_PAYLOAD)),
            ]
            get_provider().extract_invoice(OCR_TEXT)
        self.assertIn("temperature", post.call_args_list[0].kwargs["json"])
        self.assertNotIn("temperature", post.call_args_list[1].kwargs["json"])

    def test_model_without_structured_outputs_falls_back_to_json_mode(self):
        with ai_settings("openai", openai_model="gpt-3.5-turbo"), patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = [
                _response(400, {"error": {"message": "Invalid parameter: 'response_format' of type 'json_schema' is not supported"}}),
                _completion(json.dumps(AI_PAYLOAD)),
            ]
            get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["response_format"], {"type": "json_object"})

    def test_model_not_found(self):
        with ai_settings("openai", openai_model="gpt-nope"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _response(404, {"error": {"message": "The model does not exist"}})
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "model_not_found")
        self.assertIn("OPENAI_MODEL", str(ctx.exception))


@patch("backend.app.ai.providers.time.sleep", lambda *_: None)
class TestOpenRouterProvider(unittest.TestCase):
    def test_uses_openrouter_url_and_fallback_models(self):
        with ai_settings("openrouter", openrouter_fallback_models=["meta-llama/llama-3.1-70b-instruct"]), \
                patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = [
                _response(404, {"error": {"message": "No endpoints found"}}),
                _completion("```json\n" + json.dumps(AI_PAYLOAD) + "\n```"),
            ]
            provider = get_provider()
            self.assertIsInstance(provider, OpenRouterProvider)
            result = provider.extract_invoice(OCR_TEXT)
        self.assertEqual(result.model, "meta-llama/llama-3.1-70b-instruct")
        self.assertTrue(post.call_args.args[0].startswith("https://openrouter.ai/api/v1/"))


@patch("backend.app.ai.providers.time.sleep", lambda *_: None)
class TestFreeTierProviders(unittest.TestCase):
    def test_gemini_uses_openai_compatible_endpoint_and_schema(self):
        with ai_settings("gemini"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion(json.dumps(AI_PAYLOAD))
            provider = get_provider()
            self.assertIsInstance(provider, GeminiProvider)
            result = provider.extract_invoice(OCR_TEXT)
        url = post.call_args.args[0]
        self.assertEqual(url, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer gm-test-key-not-real")
        self.assertEqual(post.call_args.kwargs["json"]["response_format"]["type"], "json_schema")
        self.assertEqual(result.extraction.invoice_number, "INV-2026-0042")

    def test_gemini_schema_rejection_downgrades_to_json_mode(self):
        with ai_settings("gemini"), patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = [
                _response(400, {"error": {"message": 'Invalid JSON payload received. Unknown name "additionalProperties"'}}),
                _completion(json.dumps(AI_PAYLOAD)),
            ]
            get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["response_format"], {"type": "json_object"})

    def test_groq_uses_json_mode(self):
        with ai_settings("groq"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion(json.dumps(AI_PAYLOAD))
            provider = get_provider()
            self.assertIsInstance(provider, GroqProvider)
            provider.extract_invoice(OCR_TEXT)
        self.assertTrue(post.call_args.args[0].startswith("https://api.groq.com/openai/v1/"))
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})

    def test_free_tier_quota_message_does_not_ask_for_billing(self):
        with ai_settings("gemini", ai_max_retries=0), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _response(429, {"error": {"message": "You exceeded your current quota"}})
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "quota")
        self.assertIn("Free-tier", str(ctx.exception))

    def test_gemini_daily_quota_on_one_model_falls_back_to_the_next(self):
        # Gemini free-tier quota is counted per model
        with ai_settings("gemini", ai_max_retries=0, gemini_fallback_models=["gemini-flash-lite-latest"]), \
                patch("backend.app.ai.providers.requests.post") as post:
            post.side_effect = [
                _response(429, {"error": {"message": "You exceeded your current quota"}}),
                _completion(json.dumps(AI_PAYLOAD)),
            ]
            result = get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(result.model, "gemini-flash-lite-latest")

    def test_gemini_invalid_key_is_reported_as_auth_error(self):
        # Real response shape returned by the Gemini OpenAI-compatible endpoint for a bad key
        body = [{"error": {"code": 400, "message": "Please pass a valid API key", "status": "INVALID_ARGUMENT"}}]
        with ai_settings("gemini"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _response(400, body)
            with self.assertRaises(AIProviderError) as ctx:
                get_provider().extract_invoice(OCR_TEXT)
        self.assertEqual(ctx.exception.kind, "auth")
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        self.assertEqual(post.call_count, 1)

    def test_auto_picks_gemini_when_only_gemini_key_set(self):
        with ai_settings("auto", gemini_api_key="gm-key"):
            self.assertIsInstance(get_provider(), GeminiProvider)
            self.assertEqual(describe_ai_config()["model"], "gemini-flash-latest")

    def test_missing_gemini_key_points_to_free_key_page(self):
        with ai_settings("gemini", gemini_api_key=None):
            with self.assertRaises(AIProviderError) as ctx:
                get_provider()
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        self.assertIn("aistudio.google.com", str(ctx.exception))


class TestProviderSelection(unittest.TestCase):
    def test_auto_prefers_openai(self):
        with ai_settings("auto", openai_api_key="sk-test-key-not-real", openrouter_api_key="or-key"):
            self.assertIsInstance(get_provider(), OpenAIProvider)

    def test_auto_without_keys_disables_ai(self):
        with ai_settings("auto", openai_api_key=None, openrouter_api_key=None):
            self.assertIsNone(get_provider())
            self.assertEqual(describe_ai_config()["provider"], "none")

    def test_explicit_provider_without_key_reports_config_error(self):
        with ai_settings("openai", openai_api_key=None):
            with self.assertRaises(AIProviderError) as ctx:
                get_provider()
        self.assertEqual(ctx.exception.kind, "config")
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    def test_describe_config_never_exposes_keys(self):
        with ai_settings("openai"):
            described = json.dumps(describe_ai_config())
        self.assertNotIn("sk-test-key-not-real", described)

    def test_placeholder_keys_are_treated_as_unset(self):
        from backend.app.config.settings import _clean_secret
        self.assertIsNone(_clean_secret("your_openai_api_key"))
        self.assertIsNone(_clean_secret("replace_with_a_strong_password_min_12_chars"))
        self.assertIsNone(_clean_secret("   "))
        self.assertEqual(_clean_secret(" sk-real "), "sk-real")


@patch("backend.app.ai.providers.time.sleep", lambda *_: None)
class TestAIAssistedParsing(unittest.TestCase):
    def test_ai_result_is_normalized_and_marked(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion(json.dumps(AI_PAYLOAD))
            doc = parse_document(OCR_TEXT, ocr_confidence=0.9)
        self.assertEqual(doc.extraction_method, "ai:openai")
        self.assertEqual(doc.ai_model, "gpt-4o-mini")
        self.assertEqual(doc.total, "1180.00")
        self.assertEqual(doc.igst, "0.00")
        self.assertEqual(doc.items[0].amount, "500.00")
        self.assertGreaterEqual(doc.confidence, 0.8)
        self.assertEqual(doc.extraction_notes, [])

    def test_ai_failure_falls_back_to_rules_with_note(self):
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _response(401, {"error": {"message": "bad key"}})
            doc = parse_document(OCR_TEXT, ocr_confidence=0.9)
        self.assertEqual(doc.extraction_method, "rules")
        self.assertTrue(any("AI extraction failed" in n for n in doc.extraction_notes))
        self.assertEqual(doc.invoice_number, "INV-2026-0042")
        self.assertEqual(doc.total, "1180.00")

    def test_values_not_in_source_text_lower_confidence(self):
        hallucinated = dict(AI_PAYLOAD, invoice_number="INV-9999-FAKE", total="99999.00")
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion(json.dumps(hallucinated))
            doc = parse_document(OCR_TEXT, ocr_confidence=0.9)
        self.assertLess(doc.confidence, 0.75)
        self.assertTrue(any("invoice_number" in n for n in doc.extraction_notes))
        self.assertTrue(any("total" in n for n in doc.extraction_notes))

    def test_missing_values_are_not_invented(self):
        sparse = {k: "" for k in AI_PAYLOAD if k != "items"}
        sparse.update({"vendor": "ACME Industrial Supplies Pvt Ltd", "items": []})
        with ai_settings("openai"), patch("backend.app.ai.providers.requests.post") as post:
            post.return_value = _completion(json.dumps(sparse))
            doc = parse_document("ACME Industrial Supplies Pvt Ltd\nThank you", ocr_confidence=0.9)
        self.assertEqual(doc.total, "0.00")
        self.assertEqual(doc.invoice_number, "")
        self.assertEqual(doc.gstin, "")

    def test_no_provider_uses_rules_without_network(self):
        with ai_settings("none"), patch("backend.app.ai.providers.requests.post") as post:
            doc = parse_document(OCR_TEXT, ocr_confidence=0.9)
        post.assert_not_called()
        self.assertEqual(doc.extraction_method, "rules")


if __name__ == "__main__":
    unittest.main()
