"""Unified Gemini API client with flash → pro fallback.

All call sites across the codebase should import from here:
    from gemini_client import call_gemini, GeminiAPIError
"""

import json
import sys
import time
import urllib.error
import urllib.request

FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"

API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)

RETRYABLE_CODES = (429, 500, 502, 503, 504)


class GeminiAPIError(Exception):
    """Raised when both flash and pro retries are exhausted."""

    def __init__(self, message: str, last_error=None):
        super().__init__(message)
        self.last_error = last_error


def _extract_text(result: dict) -> str:
    """Pull the text from a Gemini generateContent response."""
    parts = result["candidates"][0]["content"]["parts"]
    text = ""
    for part in parts:
        if "text" in part:
            text = part["text"].strip()
    return text


def _try_model(model: str, base_payload: dict, api_key: str, timeout: int,
               retries: int, backoffs: list[int],
               thinking_config: dict | None = None) -> str | None:
    """Try a model with retries. Returns text on success, None on exhaustion.

    thinking_config is merged into generationConfig per-model. Flash gets
    {thinkingBudget: 0} (cheap/fast); Pro gets None so it uses dynamic
    thinking — Pro 400s on thinkingBudget:0.
    """
    url = API_URL_TEMPLATE.format(model=model, api_key=api_key)
    payload_dict = json.loads(json.dumps(base_payload))  # deep copy
    if thinking_config is not None:
        payload_dict["generationConfig"]["thinkingConfig"] = thinking_config
    payload = json.dumps(payload_dict).encode()
    last_err = None

    for attempt in range(retries):
        if attempt > 0:
            wait = backoffs[attempt - 1]
            print(f"  [gemini] Retry {attempt}/{retries - 1} on {model} "
                  f"after {wait}s (last: {last_err})", file=sys.stderr)
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
            return _extract_text(result)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            last_err = f"HTTP {e.code}: {body[:200]}"
            if e.code not in RETRYABLE_CODES:
                raise GeminiAPIError(
                    f"Gemini {model} returned non-retryable {e.code}: {body[:500]}",
                    last_error=e,
                )
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"

    return None  # retries exhausted


def call_gemini(prompt: str, api_key: str, temperature: float = 0.5,
                max_tokens: int = 8192, timeout: int = 90,
                force_model: str | None = None) -> str:
    """Call Gemini with flash → pro fallback.

    Tries gemini-2.5-flash up to 6 times with exponential backoff.
    If flash is exhausted, falls back to gemini-2.5-pro with 3 retries.
    Raises GeminiAPIError if both models fail.

    force_model: when set (e.g. PRO_MODEL), bypass flash entirely and call
    only that model. Used by callers that want explicit escalation, e.g.
    script-gen retry loop switching to Pro after Flash exhausts its budget.
    """
    base_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    if force_model == PRO_MODEL:
        result = _try_model(
            PRO_MODEL, base_payload, api_key, timeout,
            retries=3, backoffs=[4, 8, 16],
            thinking_config=None,
        )
        if result is not None:
            return result
        raise GeminiAPIError(
            f"Gemini API failed: {PRO_MODEL} (3 attempts) exhausted",
        )

    # --- Flash: 6 attempts, backoff [2, 4, 8, 16, 32, 64]s ---
    # thinkingBudget:0 disables thinking on Flash for cost/speed.
    # Do NOT copy this to Pro — Pro 400s with "Budget 0 is invalid".
    result = _try_model(
        FLASH_MODEL, base_payload, api_key, timeout,
        retries=6, backoffs=[2, 4, 8, 16, 32, 64],
        thinking_config={"thinkingBudget": 0},
    )
    if result is not None:
        return result

    # --- Fallback: Pro, 3 attempts, backoff [4, 8, 16]s ---
    # Pro omits thinkingConfig so it uses its default dynamic thinking —
    # that's the reasoning we're paying for on fallback.
    print(f"  [gemini] FALLBACK: {FLASH_MODEL} exhausted, "
          f"switching to {PRO_MODEL}", file=sys.stderr)
    result = _try_model(
        PRO_MODEL, base_payload, api_key, timeout,
        retries=3, backoffs=[4, 8, 16],
        thinking_config=None,
    )
    if result is not None:
        print(f"  [gemini] FALLBACK succeeded on {PRO_MODEL}", file=sys.stderr)
        return result

    raise GeminiAPIError(
        f"Gemini API failed: both {FLASH_MODEL} (6 attempts) and "
        f"{PRO_MODEL} (3 attempts) exhausted",
    )
