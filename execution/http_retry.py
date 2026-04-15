"""
http_retry.py — shared retry-with-backoff helper for external HTTP APIs.

Mirrors the pattern in app/src/lib/supabase-server.ts (withRetry / supabaseRetry).
Used by generate_voiceover.py (ElevenLabs TTS), generate_images.py (Imagen),
generate_video_clips.py (Kling), generate_music.py (ElevenLabs Music) so one
transient 5xx or 429 from an upstream API no longer kills the whole pipeline.

Retry policy chosen in the s48 plan (harmonic-wibbling-river):
  - 3 attempts total
  - Backoff 0.5s / 1.0s / 2.0s  (max ~3.5s extra latency on failure)
  - Retry only on 5xx, 429, or connection/timeout errors
  - Never retry on 4xx (bad request, auth fail — retrying won't help)
"""

import time
import urllib.error
import urllib.request
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts fail. Wraps the last exception."""

    def __init__(self, attempts: int, last_exc: BaseException):
        super().__init__(f"all {attempts} attempts failed: {last_exc}")
        self.last_exc = last_exc
        self.attempts = attempts


class TransientUpstreamError(Exception):
    """Raise from inside a retry_with_backoff body to force a retry on a
    response that was HTTP 200 but semantically empty/unusable — e.g. Imagen
    returning `predictions: []` when the safety filter silently drops a prompt.
    These cases never raise an HTTPError so the default _is_retryable wouldn't
    catch them."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, TransientUpstreamError):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return True
    # Some libs wrap urllib errors — check by name as a last resort.
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name:
        return True
    return False


def retry_with_backoff(
    fn: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 0.5,
    label: str | None = None,
) -> T:
    """Call `fn` up to `attempts` times with exponential backoff (base_delay * 2**i).
    Only retries on transient errors (5xx / 429 / connection / timeout).
    4xx and other errors bubble immediately. Final failure raises RetryExhaustedError.
    """
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — intentional, filter inside
            last_exc = e
            if not _is_retryable(e):
                raise
            if i == attempts - 1:
                break
            delay = base_delay * (2 ** i)
            tag = f"[{label}] " if label else ""
            print(
                f"  {tag}attempt {i + 1}/{attempts} failed ({type(e).__name__}: {e}); "
                f"retrying in {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)
    assert last_exc is not None  # attempts >= 1
    raise RetryExhaustedError(attempts, last_exc) from last_exc
