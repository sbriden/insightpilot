"""
AI provider access with graceful degradation.

Analytical correctness never depends on this module succeeding.
When the provider is unavailable, credentials are missing, quota
is exhausted, the request fails, or output is invalid, callers
must fall back to deterministic overlays.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)

# Failure / availability reasons surfaced to callers and UI.
AI_REASON_OK = "ok"
AI_REASON_NO_CREDENTIALS = "no_credentials"
AI_REASON_DISABLED = "disabled"
AI_REASON_PROVIDER_UNAVAILABLE = "provider_unavailable"
AI_REASON_REQUEST_FAILED = "request_failed"
AI_REASON_INVALID_OUTPUT = "invalid_output"
AI_REASON_QUOTA_EXHAUSTED = "quota_exhausted"
AI_REASON_TIMEOUT = "timeout"
AI_REASON_FALLBACK = "fallback"

_JSON_OBJECT_PATTERN = re.compile(
    r"\{.*\}",
    re.DOTALL,
)


@dataclass(frozen=True)
class AICompletionResult:
    """Outcome of an optional AI completion attempt."""

    ok: bool
    data: dict[str, Any] | None = None
    reason: str = AI_REASON_FALLBACK
    message: str | None = None
    source: str = "fallback"  # ai | fallback


def ai_enabled() -> bool:
    """Feature flag — set INSIGHTPILOT_AI_ENABLED=0 to force fallback."""

    raw = str(os.getenv("INSIGHTPILOT_AI_ENABLED", "1")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_openai_api_key() -> str | None:
    key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if not key or key.lower() in {"changeme", "your-key-here"}:
        return None
    return key


def get_openai_model() -> str:
    return str(os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()


def probe_ai_availability() -> AICompletionResult:
    """
    Cheap preflight — does not call the provider.

    Returns ok=True only when AI is enabled and credentials exist.
    """

    if not ai_enabled():
        return AICompletionResult(
            ok=False,
            reason=AI_REASON_DISABLED,
            message="AI enrichment is disabled.",
            source="fallback",
        )
    if not get_openai_api_key():
        return AICompletionResult(
            ok=False,
            reason=AI_REASON_NO_CREDENTIALS,
            message="No AI credentials configured.",
            source="fallback",
        )
    return AICompletionResult(
        ok=True,
        reason=AI_REASON_OK,
        message="AI credentials present.",
        source="ai",
    )


def _classify_exception(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(
        token in text
        for token in (
            "rate limit",
            "quota",
            "insufficient_quota",
            "billing",
            "429",
        )
    ):
        return AI_REASON_QUOTA_EXHAUSTED
    if any(
        token in text
        for token in ("timeout", "timed out", "deadline")
    ):
        return AI_REASON_TIMEOUT
    if any(
        token in text
        for token in (
            "connection",
            "unavailable",
            "dns",
            "network",
            "ssl",
            "503",
            "502",
            "504",
        )
    ):
        return AI_REASON_PROVIDER_UNAVAILABLE
    if any(
        token in text
        for token in ("auth", "api key", "unauthorized", "401", "403")
    ):
        return AI_REASON_NO_CREDENTIALS
    return AI_REASON_REQUEST_FAILED


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model text; None if invalid."""

    cleaned = str(text or "").strip()
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = _JSON_OBJECT_PATTERN.search(cleaned)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def complete_json(
    prompt: str,
    *,
    required_keys: set[str] | frozenset[str] | None = None,
) -> AICompletionResult:
    """
    Request JSON from the configured AI provider.

    Never raises to callers — failures become AICompletionResult(ok=False).
    """

    availability = probe_ai_availability()
    if not availability.ok:
        return availability

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - import env
        return AICompletionResult(
            ok=False,
            reason=AI_REASON_PROVIDER_UNAVAILABLE,
            message=f"OpenAI client unavailable: {exc}",
            source="fallback",
        )

    try:
        client = OpenAI(api_key=get_openai_api_key())
        # Prefer Responses API when available; fall back to chat.
        raw_text = ""
        model = get_openai_model()
        try:
            response = client.responses.create(
                model=model,
                input=prompt,
            )
            raw_text = str(getattr(response, "output_text", "") or "")
        except Exception:
            chat = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return JSON only. Do not invent analytical "
                            "numbers. Omit rather than guess."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            raw_text = str(
                chat.choices[0].message.content or ""
            )
    except Exception as exc:
        reason = _classify_exception(exc)
        logger.warning("AI completion failed (%s): %s", reason, exc)
        return AICompletionResult(
            ok=False,
            reason=reason,
            message=str(exc),
            source="fallback",
        )

    parsed = extract_json_object(raw_text)
    if parsed is None:
        return AICompletionResult(
            ok=False,
            reason=AI_REASON_INVALID_OUTPUT,
            message="Model returned non-JSON or empty output.",
            source="fallback",
        )

    if required_keys:
        missing = sorted(set(required_keys) - set(parsed))
        if missing:
            return AICompletionResult(
                ok=False,
                reason=AI_REASON_INVALID_OUTPUT,
                message=f"Model JSON missing keys: {', '.join(missing)}",
                source="fallback",
            )

    return AICompletionResult(
        ok=True,
        data=parsed,
        reason=AI_REASON_OK,
        source="ai",
    )
