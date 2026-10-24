"""
LLM provider abstraction.

Both supported providers speak the OpenAI Chat Completions wire format, so a
single HTTP client handles them; each provider only differs in base URL,
headers, model fallbacks and whether Structured Outputs are requested.
API keys are only ever read from server-side settings and never logged.
"""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from pydantic import ValidationError

from backend.app.ai.schema import (
    INVOICE_JSON_SCHEMA,
    SYSTEM_PROMPT,
    InvoiceExtraction,
    build_user_prompt,
)
from backend.app.config.settings import settings
from backend.app.utils.text_utils import strip_code_fences

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 20.0


class AIProviderError(Exception):
    """
    Raised when an AI provider call fails. `kind` is a stable machine-readable
    category; `str(exc)` is a safe, actionable message (never contains secrets).
    """

    def __init__(self, message: str, kind: str = "error", retryable: bool = False, status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.status = status


@dataclass
class AIResult:
    extraction: InvoiceExtraction
    provider: str
    model: str


def _error_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, list) and body:  # Gemini wraps errors in a list
            body = body[0]
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or err.get("code") or "")[:300]
        if isinstance(err, str):
            return err[:300]
    except ValueError:
        pass
    return (response.text or "")[:200]


# Phrases in a 400 error that mean the model/provider rejected our response_format
RESPONSE_FORMAT_ERROR_HINTS = (
    "response_format", "json_schema", "json mode", "schema", "strict", "additionalproperties",
    "unknown name", "invalid json payload",
)

PROVIDER_LABELS = {"openai": "OpenAI", "gemini": "Google Gemini", "groq": "Groq", "openrouter": "OpenRouter"}


def _classify_http_error(provider: str, model: str, response: requests.Response) -> AIProviderError:
    status = response.status_code
    detail = _error_detail(response)
    name = PROVIDER_LABELS.get(provider, provider)
    cfg = settings.ai_provider_settings(provider) if provider in PROVIDER_LABELS else {}
    key_var = cfg.get("key_var", "the API key")
    model_var = cfg.get("model_var", "the model setting")

    # Gemini reports a bad key as 400 INVALID_ARGUMENT instead of 401
    if status == 401 or (status == 400 and ("api key" in detail.lower() or "api_key_invalid" in detail.lower())):
        return AIProviderError(f"{name} rejected the API key ({status}). Check {key_var}.", "auth", status=status)
    if status == 402:
        return AIProviderError(f"{name} account has insufficient credits (402).", "billing", status=status)
    if status == 403:
        return AIProviderError(
            f"{name} denied access to model '{model}' (403). Check that your account/project can use it.",
            "permission", status=status,
        )
    if status == 404:
        return AIProviderError(
            f"Model '{model}' was not found on {name} (404). Check {model_var}.", "model_not_found", status=status
        )
    if status == 429:
        quota = "quota" in detail.lower() or "billing" in detail.lower()
        if quota:
            hint = (
                "Free-tier limits are per model, per minute and per day; retry later or use a paid key."
                if provider in ("gemini", "groq") else "Add billing credit to your account."
            )
            return AIProviderError(f"{name} quota exceeded. {hint} ({detail})", "quota", status=status)
        return AIProviderError(f"{name} rate limit reached (429). Retry shortly.", "rate_limit", True, status)
    if status >= 500 or status in RETRYABLE_STATUS:
        return AIProviderError(f"{name} service error ({status}).", "unavailable", True, status)
    return AIProviderError(f"{name} request failed ({status}): {detail}", "bad_request", status=status)


def _image_part(b64_png: str) -> Dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_png}", "detail": "high"}}


class ChatCompletionsProvider:
    name = "base"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float, max_retries: int,
                 fallback_models: Optional[List[str]] = None):
        self.api_key = api_key
        self.fallback_models = fallback_models or []
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

    # -- provider specific hooks --------------------------------------
    def headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def models(self) -> List[str]:
        """Primary model first, then fallbacks tried when a model is unavailable."""
        ordered = [self.model] + [m for m in self.fallback_models if m != self.model]
        return [m for m in ordered if m]

    def supports_structured_outputs(self) -> bool:
        return False

    def build_body(self, model: str, messages: List[Dict[str, Any]], response_mode: str, use_temperature: bool) -> Dict[str, Any]:
        """response_mode: 'schema' (Structured Outputs), 'json' (JSON mode) or 'none' (prompt only)."""
        body: Dict[str, Any] = {"model": model, "messages": messages}
        if use_temperature:
            body["temperature"] = 0
        if response_mode == "schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "invoice_extraction", "strict": True, "schema": INVOICE_JSON_SCHEMA},
            }
        elif response_mode == "json":
            body["response_format"] = {"type": "json_object"}
        return body

    # -- public API -----------------------------------------------------
    def extract_invoice(self, ocr_text: str, images_b64_png: Optional[List[str]] = None) -> AIResult:
        """Text-only extraction, or image + OCR text when page images are given."""
        if images_b64_png:
            content: List[Dict[str, Any]] = [{
                "type": "text",
                "text": build_user_prompt(ocr_text, settings.ai_max_input_chars, with_images=True),
            }]
            content += [_image_part(b64) for b64 in images_b64_png]
            messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(ocr_text, settings.ai_max_input_chars)},
            ]
        return self._extract(messages)

    def extract_invoice_from_images(self, images_b64_png: List[str]) -> AIResult:
        content: List[Dict[str, Any]] = [{
            "type": "text",
            "text": build_user_prompt("(No OCR text available - read the attached invoice page images.)", with_images=True),
        }]
        content += [_image_part(b64) for b64 in images_b64_png]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
        return self._extract(messages)

    def _extract(self, messages: List[Dict[str, Any]]) -> AIResult:
        last_error: Optional[AIProviderError] = None
        models = self.models()
        for index, model in enumerate(models):
            try:
                # With a fallback model available, an overloaded model is skipped instead of retried
                payload = self._complete_json(model, messages, retry_unavailable=index == len(models) - 1)
                extraction = InvoiceExtraction.model_validate(payload)
                return AIResult(extraction=extraction, provider=self.name, model=model)
            except ValidationError as exc:
                last_error = AIProviderError(
                    f"Model '{model}' returned data that does not match the invoice schema ({exc.error_count()} errors).",
                    "invalid_response",
                )
            except AIProviderError as exc:
                last_error = exc
                # Credential/billing problems will not be fixed by another model. Free tiers
                # (Gemini, Groq) count quota per model, so a fallback model may still have some.
                per_model_quota = exc.kind == "quota" and self.name in ("gemini", "groq")
                if exc.kind in ("auth", "billing", "quota") and not per_model_quota:
                    raise
            logger.warning("AI extraction with %s model '%s' failed: %s", self.name, model, last_error)
        raise last_error or AIProviderError("AI extraction failed.", "error")

    def _complete_json(self, model: str, messages: List[Dict[str, Any]], retry_unavailable: bool = True) -> Dict[str, Any]:
        response_mode = "schema" if self.supports_structured_outputs() else "json"
        use_temperature = True
        attempt = 0
        compat_downgrades = 0
        while True:
            body = self.build_body(model, messages, response_mode, use_temperature)
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers(),
                    json=body,
                    timeout=(10, self.timeout),
                )
            except requests.Timeout:
                err = AIProviderError(
                    f"{self.name} request timed out after {self.timeout:.0f}s (AI_TIMEOUT_SECONDS).", "timeout", True
                )
            except requests.RequestException as exc:
                err = AIProviderError(f"Could not reach {self.name} API: {type(exc).__name__}.", "network", True)
            else:
                if response.status_code == 200:
                    return self._parse_response(response, model)
                err = _classify_http_error(self.name, model, response)
                if err.kind == "unavailable" and not retry_unavailable:
                    raise err
                # Some models reject temperature or json_schema: downgrade once and retry
                if response.status_code == 400 and compat_downgrades < 3:
                    detail = _error_detail(response).lower()
                    if use_temperature and "temperature" in detail:
                        use_temperature = False
                        compat_downgrades += 1
                        continue
                    if response_mode != "none" and any(hint in detail for hint in RESPONSE_FORMAT_ERROR_HINTS):
                        response_mode = "json" if response_mode == "schema" else "none"
                        compat_downgrades += 1
                        continue
                if err.retryable and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.replace(".", "", 1).isdigit():
                        attempt += 1
                        time.sleep(min(float(retry_after), MAX_BACKOFF_SECONDS))
                        continue

            if err.retryable and attempt < self.max_retries:
                attempt += 1
                delay = min(MAX_BACKOFF_SECONDS, (2 ** attempt) * 0.5 + random.uniform(0, 0.5))
                logger.info("Retrying %s call (attempt %d/%d) in %.1fs: %s", self.name, attempt, self.max_retries, delay, err)
                time.sleep(delay)
                continue
            raise err

    def _parse_response(self, response: requests.Response, model: str) -> Dict[str, Any]:
        try:
            payload = response.json()
            choice = payload["choices"][0]
            message = choice.get("message") or {}
        except (ValueError, KeyError, IndexError, TypeError):
            raise AIProviderError(f"{self.name} returned an unexpected response format.", "invalid_response", True)

        if message.get("refusal"):
            raise AIProviderError(f"Model '{model}' refused to process the document.", "refusal")
        if choice.get("finish_reason") == "length":
            raise AIProviderError(
                f"Model '{model}' output was cut off (max tokens). Try a model with a larger output limit.",
                "truncated",
            )
        content = message.get("content")
        if isinstance(content, list):  # some providers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content or not str(content).strip():
            raise AIProviderError(f"Model '{model}' returned an empty response.", "invalid_response", True)
        try:
            data = json.loads(strip_code_fences(str(content)))
        except json.JSONDecodeError:
            raise AIProviderError(f"Model '{model}' did not return valid JSON.", "invalid_response", True)
        if not isinstance(data, dict):
            raise AIProviderError(f"Model '{model}' returned JSON that is not an object.", "invalid_response")
        return data


class OpenAIProvider(ChatCompletionsProvider):
    name = "openai"

    def headers(self) -> Dict[str, str]:
        headers = super().headers()
        if settings.openai_organization:
            headers["OpenAI-Organization"] = settings.openai_organization
        if settings.openai_project:
            headers["OpenAI-Project"] = settings.openai_project
        return headers

    def supports_structured_outputs(self) -> bool:
        return True


class OpenRouterProvider(ChatCompletionsProvider):
    name = "openrouter"

    def headers(self) -> Dict[str, str]:
        headers = super().headers()
        if settings.openrouter_site_url:
            headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_app_name:
            headers["X-Title"] = settings.openrouter_app_name
        return headers


class GeminiProvider(ChatCompletionsProvider):
    """Google Gemini through its OpenAI-compatible endpoint (free tier available)."""
    name = "gemini"

    def supports_structured_outputs(self) -> bool:
        return True


class GroqProvider(ChatCompletionsProvider):
    """Groq through its OpenAI-compatible endpoint (free tier available)."""
    name = "groq"


PROVIDER_CLASSES = {"openai": OpenAIProvider, "gemini": GeminiProvider, "groq": GroqProvider}


def get_provider() -> Optional[ChatCompletionsProvider]:
    """
    Returns the configured provider, or None when AI extraction is disabled.
    Raises AIProviderError with an actionable message when misconfigured.
    """
    provider = settings.resolved_ai_provider
    if provider == "none":
        return None
    errors = settings.ai_config_errors()
    if errors:
        raise AIProviderError(" ".join(errors), "config")
    if provider in PROVIDER_CLASSES:
        cfg = settings.ai_provider_settings(provider)
        return PROVIDER_CLASSES[provider](
            cfg["api_key"], cfg["model"], cfg["base_url"],
            settings.ai_timeout_seconds, settings.ai_max_retries,
            fallback_models=cfg["fallback_models"],
        )
    return OpenRouterProvider(
        settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_base_url,
        settings.ai_timeout_seconds, settings.ai_max_retries,
        fallback_models=settings.openrouter_fallback_models,
    )


def describe_ai_config() -> Dict[str, Any]:
    """Non-secret summary of the AI configuration for status endpoints."""
    provider = settings.resolved_ai_provider
    model = settings.ai_model
    errors = settings.ai_config_errors()
    return {
        "provider": provider,
        "model": model,
        "configured": provider != "none" and not errors,
        "vision_fallback": settings.ai_vision_fallback and provider != "none",
        "errors": errors,
    }
