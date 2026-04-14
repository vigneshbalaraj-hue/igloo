/**
 * fetchWithTimeout — wraps fetch with an AbortController so client pages never
 * hang silently on a slow internal API. Default 15s, caller can override.
 * Throws a TimeoutError (standard DOMException 'AbortError') on timeout.
 */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = 15_000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}
