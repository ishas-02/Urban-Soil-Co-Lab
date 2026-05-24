# """Provider-agnostic VLM call interface.

# Two backends are supported:
#   - Gemini 2.5 Flash (primary, cheap-or-free)
#   - Claude Sonnet 4.6 (fallback for sketches the user marks as messy)

# Both backends return the same shape: a dict matching the extractor
# schema, already parsed from JSON. Use ``extract_from_image`` for the
# common path; it picks the provider based on the ``backend`` argument.
# """

# from __future__ import annotations

# import base64
# import json
# import mimetypes
# import os
# import re
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any, Optional

# from .prompt import SYSTEM_PROMPT, build_user_message
# from .schema import normalize_extraction, validate_extraction


# # ─────────────────────────────────────────────────────────────────
# #  Public types
# # ─────────────────────────────────────────────────────────────────

# @dataclass
# class ExtractionResult:
#     """Outcome of a single VLM call."""
#     data: dict[str, Any]
#     backend: str
#     model: str
#     raw_response: str
#     problems: list[str]      # validation problems; empty list ⇒ ok
#     usage: dict[str, Any]    # provider-specific token/cost info if available

#     @property
#     def ok(self) -> bool:
#         return not self.problems


# # ─────────────────────────────────────────────────────────────────
# #  Image loading helper
# # ─────────────────────────────────────────────────────────────────

# def _read_image_bytes(image_path: str | Path) -> tuple[bytes, str]:
#     """Return (raw_bytes, mime_type) for the image at ``image_path``."""
#     p = Path(image_path)
#     if not p.exists():
#         raise FileNotFoundError(f"image not found: {image_path}")
#     data = p.read_bytes()
#     mime, _ = mimetypes.guess_type(str(p))
#     if not mime:
#         # Default to JPEG; both providers tolerate a slightly-wrong mime.
#         mime = "image/jpeg"
#     return data, mime


# def _strip_code_fences(text: str) -> str:
#     """Some VLMs return ```json ... ``` despite being told not to.
#     Strip those fences so json.loads succeeds.
#     """
#     text = text.strip()
#     if text.startswith("```"):
#         # ```json\n...\n```  or  ```\n...\n```
#         text = re.sub(r"^```(?:json)?\s*\n?", "", text)
#         text = re.sub(r"\n?```\s*$", "", text)
#     return text.strip()


# def _parse_json_response(raw: str) -> dict[str, Any]:
#     """Parse a VLM text response as JSON, tolerating code fences."""
#     cleaned = _strip_code_fences(raw)
#     # Some models wrap the JSON in a leading sentence; find the first
#     # `{` and the last `}` and parse that slice.
#     start = cleaned.find("{")
#     end   = cleaned.rfind("}")
#     if start == -1 or end == -1 or end <= start:
#         raise ValueError(
#             "VLM response did not contain a JSON object. "
#             f"First 200 chars: {cleaned[:200]!r}"
#         )
#     return json.loads(cleaned[start:end + 1])


# # ─────────────────────────────────────────────────────────────────
# #  Gemini backend
# # ─────────────────────────────────────────────────────────────────

# def _call_gemini(
#     image_path: str | Path,
#     *,
#     api_key: str,
#     model: str = "gemini-2.5-flash",
#     extra_hints: Optional[str] = None,
#     timeout: int = 60,
# ) -> tuple[dict[str, Any], str, dict[str, Any]]:
#     """Call Gemini's generateContent endpoint with the sketch.

#     Returns (parsed_json, raw_text, usage_dict).
#     """
#     import requests  # already in requirements.txt

#     img_bytes, mime = _read_image_bytes(image_path)
#     img_b64 = base64.standard_b64encode(img_bytes).decode("ascii")

#     url = (
#         f"https://generativelanguage.googleapis.com/v1beta/models/"
#         f"{model}:generateContent"
#     )
#     headers = {
#         "Content-Type": "application/json",
#         "x-goog-api-key": api_key,
#     }
#     user_text = build_user_message(extra_hints)
#     body = {
#         # Gemini supports a top-level "systemInstruction" — use it so
#         # the schema/conventions don't eat user-message tokens.
#         "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": [
#                     {"inline_data": {"mime_type": mime, "data": img_b64}},
#                     {"text": user_text},
#                 ],
#             }
#         ],
#         "generationConfig": {
#             "temperature": 0.0,         # deterministic extraction
#             "responseMimeType": "application/json",
#             "maxOutputTokens": 4096,
#         },
#     }

#     resp = requests.post(url, headers=headers, json=body, timeout=timeout)
#     resp.raise_for_status()
#     payload = resp.json()

#     # ── Pull text out of Gemini's nested candidate structure ──
#     try:
#         candidates = payload["candidates"]
#         parts = candidates[0]["content"]["parts"]
#         raw_text = "".join(p.get("text", "") for p in parts)
#     except (KeyError, IndexError) as e:
#         raise RuntimeError(
#             f"Unexpected Gemini response shape: {payload!r}"
#         ) from e

#     usage = payload.get("usageMetadata", {})
#     parsed = _parse_json_response(raw_text)
#     return parsed, raw_text, usage


# # ─────────────────────────────────────────────────────────────────
# #  Claude backend
# # ─────────────────────────────────────────────────────────────────

# def _call_claude(
#     image_path: str | Path,
#     *,
#     api_key: str,
#     model: str = "claude-sonnet-4-6",
#     extra_hints: Optional[str] = None,
#     timeout: int = 60,
# ) -> tuple[dict[str, Any], str, dict[str, Any]]:
#     """Call Claude's /v1/messages endpoint with the sketch.

#     Returns (parsed_json, raw_text, usage_dict).
#     """
#     import requests

#     img_bytes, mime = _read_image_bytes(image_path)
#     img_b64 = base64.standard_b64encode(img_bytes).decode("ascii")

#     url = "https://api.anthropic.com/v1/messages"
#     headers = {
#         "Content-Type": "application/json",
#         "x-api-key": api_key,
#         "anthropic-version": "2023-06-01",
#     }
#     user_text = build_user_message(extra_hints)
#     body = {
#         "model": model,
#         "max_tokens": 4096,
#         "temperature": 0.0,
#         "system": SYSTEM_PROMPT,
#         "messages": [
#             {
#                 "role": "user",
#                 "content": [
#                     {
#                         "type": "image",
#                         "source": {
#                             "type": "base64",
#                             "media_type": mime,
#                             "data": img_b64,
#                         },
#                     },
#                     {"type": "text", "text": user_text},
#                 ],
#             }
#         ],
#     }

#     resp = requests.post(url, headers=headers, json=body, timeout=timeout)
#     resp.raise_for_status()
#     payload = resp.json()

#     # ── Concatenate any text blocks (typically one) ──
#     blocks = payload.get("content") or []
#     raw_text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
#     if not raw_text:
#         raise RuntimeError(f"Claude returned no text blocks: {payload!r}")

#     usage = payload.get("usage", {})
#     parsed = _parse_json_response(raw_text)
#     return parsed, raw_text, usage


# # ─────────────────────────────────────────────────────────────────
# #  Public entrypoint
# # ─────────────────────────────────────────────────────────────────

# def extract_from_image(
#     image_path: str | Path,
#     *,
#     backend: str = "gemini",
#     api_key: Optional[str] = None,
#     model: Optional[str] = None,
#     extra_hints: Optional[str] = None,
#     timeout: int = 60,
# ) -> ExtractionResult:
#     """Extract a site sketch using the chosen VLM backend.

#     Parameters
#     ----------
#     image_path:
#         Path to the sketch image file (jpg/png/heic — anything the
#         provider accepts).
#     backend:
#         "gemini" or "claude". Defaults to gemini (cheaper).
#     api_key:
#         If omitted, falls back to ``GEMINI_API_KEY`` or
#         ``ANTHROPIC_API_KEY`` env var depending on backend.
#     model:
#         Override the default model string.
#     extra_hints:
#         Optional free-text field-worker hints (e.g. "house is at
#         the bottom of the page", "all dimensions in feet").
#     """
#     backend = backend.lower().strip()

#     if backend == "gemini":
#         key = api_key or os.environ.get("GEMINI_API_KEY") \
#             or os.environ.get("GOOGLE_API_KEY")
#         if not key:
#             raise RuntimeError(
#                 "Gemini backend requires GEMINI_API_KEY (or GOOGLE_API_KEY) "
#                 "env var, or pass api_key="
#             )
#         mdl = model or "gemini-2.5-flash"
#         parsed, raw_text, usage = _call_gemini(
#             image_path, api_key=key, model=mdl,
#             extra_hints=extra_hints, timeout=timeout,
#         )

#     elif backend == "claude":
#         key = api_key or os.environ.get("ANTHROPIC_API_KEY")
#         if not key:
#             raise RuntimeError(
#                 "Claude backend requires ANTHROPIC_API_KEY env var, "
#                 "or pass api_key="
#             )
#         mdl = model or "claude-sonnet-4-6"
#         parsed, raw_text, usage = _call_claude(
#             image_path, api_key=key, model=mdl,
#             extra_hints=extra_hints, timeout=timeout,
#         )

#     else:
#         raise ValueError(
#             f"unknown backend: {backend!r}. Use 'gemini' or 'claude'."
#         )

#     # Normalize before validating so missing-optional-keys don't show up
#     # as fake problems.
#     parsed = normalize_extraction(parsed)
#     ok, problems = validate_extraction(parsed)

#     return ExtractionResult(
#         data=parsed,
#         backend=backend,
#         model=mdl,
#         raw_response=raw_text,
#         problems=problems,
#         usage=dict(usage) if usage else {},
#     )

"""Provider-agnostic VLM call interface.

Two backends are supported:
  - Gemini 2.5 Flash (primary, cheap-or-free)
  - Claude Sonnet 4.6 (fallback for sketches the user marks as messy)

Both backends return the same shape: a dict matching the extractor
schema, already parsed from JSON. Use ``extract_from_image`` for the
common path; it picks the provider based on the ``backend`` argument.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .prompt import SYSTEM_PROMPT, build_user_message
from .schema import normalize_extraction, validate_extraction


# ─────────────────────────────────────────────────────────────────
#  Public types
# ─────────────────────────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """Outcome of a single VLM call."""
    data: dict[str, Any]
    backend: str
    model: str
    raw_response: str
    problems: list[str]      # validation problems; empty list ⇒ ok
    usage: dict[str, Any]    # provider-specific token/cost info if available

    @property
    def ok(self) -> bool:
        return not self.problems


# ─────────────────────────────────────────────────────────────────
#  Image loading helper
# ─────────────────────────────────────────────────────────────────

def _read_image_bytes(image_path: str | Path) -> tuple[bytes, str]:
    """Return (raw_bytes, mime_type) for the image at ``image_path``."""
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"image not found: {image_path}")
    data = p.read_bytes()
    mime, _ = mimetypes.guess_type(str(p))
    if not mime:
        # Default to JPEG; both providers tolerate a slightly-wrong mime.
        mime = "image/jpeg"
    return data, mime


def _strip_code_fences(text: str) -> str:
    """Some VLMs return ```json ... ``` despite being told not to.
    Strip those fences so json.loads succeeds.
    """
    text = text.strip()
    if text.startswith("```"):
        # ```json\n...\n```  or  ```\n...\n```
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Parse a VLM text response as JSON, tolerating code fences."""
    cleaned = _strip_code_fences(raw)
    # Some models wrap the JSON in a leading sentence; find the first
    # `{` and the last `}` and parse that slice.
    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "VLM response did not contain a JSON object. "
            f"First 200 chars: {cleaned[:200]!r}"
        )
    return json.loads(cleaned[start:end + 1])


# ─────────────────────────────────────────────────────────────────
#  Gemini backend
# ─────────────────────────────────────────────────────────────────

def _call_gemini(
    image_path: str | Path,
    *,
    api_key: str,
    model: str = "gemini-2.5-flash",
    extra_hints: Optional[str] = None,
    timeout: int = 60,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Call Gemini's generateContent endpoint with the sketch.

    Returns (parsed_json, raw_text, usage_dict).
    """
    import requests  # already in requirements.txt

    img_bytes, mime = _read_image_bytes(image_path)
    img_b64 = base64.standard_b64encode(img_bytes).decode("ascii")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    user_text = build_user_message(extra_hints)
    body = {
        # Gemini supports a top-level "systemInstruction" — use it so
        # the schema/conventions don't eat user-message tokens.
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": img_b64}},
                    {"text": user_text},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.0,         # deterministic extraction
            "responseMimeType": "application/json",
            "maxOutputTokens": 4096,
        },
    }

    resp = requests.post(url, headers=headers, json=body, timeout=timeout)

    # ── Improved error reporting for rate-limit and quota issues ──
    # A bare resp.raise_for_status() throws away the response body, which
    # is where Google explains exactly which quota was hit and how long
    # to wait. Surface that detail.
    if resp.status_code == 429:
        detail = ""
        retry_after = resp.headers.get("Retry-After")
        try:
            err_payload = resp.json()
            err_obj = err_payload.get("error", {})
            detail = err_obj.get("message", "")
            for d in err_obj.get("details", []):
                if "quotaMetric" in d or "quotaId" in d:
                    detail += f"\n  quota: {d.get('quotaId') or d.get('quotaMetric')}"
                    if "quotaValue" in d:
                        detail += f" (limit: {d['quotaValue']})"
                if "retryDelay" in d:
                    detail += f"\n  retry after: {d['retryDelay']}"
        except (ValueError, KeyError):
            detail = resp.text[:500]
        raise RuntimeError(
            f"Gemini rate limit (429). Detail from Google:\n  {detail}"
            + (f"\n  Retry-After header: {retry_after}s" if retry_after else "")
        )
    if resp.status_code >= 400:
        try:
            err_msg = resp.json().get("error", {}).get("message", resp.text[:500])
        except (ValueError, KeyError):
            err_msg = resp.text[:500]
        raise RuntimeError(f"Gemini API {resp.status_code}: {err_msg}")

    payload = resp.json()

    # ── Pull text out of Gemini's nested candidate structure ──
    try:
        candidates = payload["candidates"]
        parts = candidates[0]["content"]["parts"]
        raw_text = "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError) as e:
        raise RuntimeError(
            f"Unexpected Gemini response shape: {payload!r}"
        ) from e

    usage = payload.get("usageMetadata", {})
    parsed = _parse_json_response(raw_text)
    return parsed, raw_text, usage


# ─────────────────────────────────────────────────────────────────
#  Claude backend
# ─────────────────────────────────────────────────────────────────

def _call_claude(
    image_path: str | Path,
    *,
    api_key: str,
    model: str = "claude-sonnet-4-6",
    extra_hints: Optional[str] = None,
    timeout: int = 60,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Call Claude's /v1/messages endpoint with the sketch.

    Returns (parsed_json, raw_text, usage_dict).
    """
    import requests

    img_bytes, mime = _read_image_bytes(image_path)
    img_b64 = base64.standard_b64encode(img_bytes).decode("ascii")

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    user_text = build_user_message(extra_hints)
    body = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.0,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    }

    resp = requests.post(url, headers=headers, json=body, timeout=timeout)
    if resp.status_code >= 400:
        try:
            err_payload = resp.json()
            err_msg = err_payload.get("error", {}).get("message", resp.text[:500])
        except (ValueError, KeyError):
            err_msg = resp.text[:500]
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise RuntimeError(
                f"Claude rate limit (429): {err_msg}"
                + (f"\n  Retry-After: {retry_after}s" if retry_after else "")
            )
        raise RuntimeError(f"Claude API {resp.status_code}: {err_msg}")
    payload = resp.json()

    # ── Concatenate any text blocks (typically one) ──
    blocks = payload.get("content") or []
    raw_text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    if not raw_text:
        raise RuntimeError(f"Claude returned no text blocks: {payload!r}")

    usage = payload.get("usage", {})
    parsed = _parse_json_response(raw_text)
    return parsed, raw_text, usage


# ─────────────────────────────────────────────────────────────────
#  Public entrypoint
# ─────────────────────────────────────────────────────────────────

def _is_rate_limit_error(exc: BaseException) -> bool:
    """True iff the exception message indicates a 429 rate-limit response."""
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "quota" in msg


def _call_with_retry(call_fn, *args, max_retries: int = 3, **kwargs):
    """Call a provider function, retrying transient 429 errors.

    Uses exponential backoff: 5s, 15s, 45s. Re-raises non-429 errors
    immediately and re-raises the final 429 once retries are exhausted
    (so the UI still sees a clean failure if the quota is actually
    exhausted, rather than silently hanging).
    """
    import time
    delays = [5, 15, 45]
    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            return call_fn(*args, **kwargs)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == max_retries - 1:
                raise
            last_exc = exc
            delay = delays[min(attempt, len(delays) - 1)]
            time.sleep(delay)
    # Unreachable, but mypy/static analysis appreciate the explicit raise.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry loop exited without a result or exception")


def extract_from_image(
    image_path: str | Path,
    *,
    backend: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    extra_hints: Optional[str] = None,
    timeout: int = 60,
    max_retries: int = 3,
) -> ExtractionResult:
    """Extract a site sketch using the chosen VLM backend.

    Parameters
    ----------
    image_path:
        Path to the sketch image file (jpg/png/heic — anything the
        provider accepts).
    backend:
        "gemini" or "claude". Defaults to gemini (cheaper).
    api_key:
        If omitted, falls back to ``GEMINI_API_KEY`` or
        ``ANTHROPIC_API_KEY`` env var depending on backend.
    model:
        Override the default model string.
    extra_hints:
        Optional free-text field-worker hints (e.g. "house is at
        the bottom of the page", "all dimensions in feet").
    max_retries:
        How many times to retry on 429 (rate-limit) errors. Set to 1
        to disable retries entirely.
    """
    backend = backend.lower().strip()

    if backend == "gemini":
        key = api_key or os.environ.get("GEMINI_API_KEY") \
            or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "Gemini backend requires GEMINI_API_KEY (or GOOGLE_API_KEY) "
                "env var, or pass api_key="
            )
        mdl = model or "gemini-2.5-flash"
        parsed, raw_text, usage = _call_with_retry(
            _call_gemini,
            image_path, api_key=key, model=mdl,
            extra_hints=extra_hints, timeout=timeout,
            max_retries=max_retries,
        )

    elif backend == "claude":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "Claude backend requires ANTHROPIC_API_KEY env var, "
                "or pass api_key="
            )
        mdl = model or "claude-sonnet-4-6"
        parsed, raw_text, usage = _call_with_retry(
            _call_claude,
            image_path, api_key=key, model=mdl,
            extra_hints=extra_hints, timeout=timeout,
            max_retries=max_retries,
        )

    else:
        raise ValueError(
            f"unknown backend: {backend!r}. Use 'gemini' or 'claude'."
        )

    # Normalize before validating so missing-optional-keys don't show up
    # as fake problems.
    parsed = normalize_extraction(parsed)
    ok, problems = validate_extraction(parsed)

    return ExtractionResult(
        data=parsed,
        backend=backend,
        model=mdl,
        raw_response=raw_text,
        problems=problems,
        usage=dict(usage) if usage else {},
    )