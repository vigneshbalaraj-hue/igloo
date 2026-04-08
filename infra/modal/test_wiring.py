"""
End-to-end wiring test for the Igloo Modal worker.

What it does:
  1. Reads SUPABASE + MODAL_TRIGGER_URL from .env
  2. Inserts a test users row + a test runs row (status='queued') via Supabase REST
  3. POSTs the run_id to the Modal trigger endpoint
  4. Polls the runs row every 15s, printing every status transition
  5. On terminal state (delivered/failed/awaiting_review), prints the full row
  6. If awaiting_review: verifies the file exists in Supabase Storage at reels/<run_id>/final.mp4
  7. Prints SQL cleanup commands the user can run after inspection

This is a REAL pipeline run. Estimated cost: ~$1–2 (Gemini + ElevenLabs + Kling + music).

Usage:
    python infra/modal/test_wiring.py
    python infra/modal/test_wiring.py --topic "morning sunlight benefits"
    python infra/modal/test_wiring.py --no-trigger   # only insert rows, don't trigger Modal
    python infra/modal/test_wiring.py --poll-only <run_id>   # resume polling an existing run
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

POLL_INTERVAL = 15      # seconds
POLL_TIMEOUT = 1800     # 30 minutes hard cap


# ---------------------------------------------------------------------------
# .env loader (matches run_pipeline.py's pattern)
# ---------------------------------------------------------------------------

def load_env(key: str) -> str | None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and not val.startswith("<"):
                    return val
    return None


def require(key: str) -> str:
    val = load_env(key)
    if not val:
        print(f"ERROR: {key} not set in .env", file=sys.stderr)
        sys.exit(1)
    return val


# ---------------------------------------------------------------------------
# Tiny Supabase REST client (no pip deps)
# ---------------------------------------------------------------------------

class Supabase:
    def __init__(self, url: str, service_role_key: str):
        self.url = url.rstrip("/")
        self.key = service_role_key
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body: dict | list | None = None,
                 extra_headers: dict | None = None) -> tuple[int, dict | list | None]:
        url = f"{self.url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {**self.headers, **(extra_headers or {})}
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if not raw:
                    return resp.status, None
                return resp.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            print(f"  HTTP {e.code} on {method} {path}: {raw}", file=sys.stderr)
            raise

    def insert(self, table: str, row: dict) -> dict:
        status, body = self._request(
            "POST", f"/rest/v1/{table}", body=row,
            extra_headers={"Prefer": "return=representation"})
        if status not in (200, 201):
            raise RuntimeError(f"insert failed: {status} {body}")
        return body[0] if isinstance(body, list) else body

    def select_one(self, table: str, eq_col: str, eq_val: str) -> dict | None:
        path = f"/rest/v1/{table}?{eq_col}=eq.{urllib.parse.quote(eq_val)}&limit=1"
        status, body = self._request("GET", path)
        if status != 200:
            raise RuntimeError(f"select failed: {status} {body}")
        return body[0] if body else None

    def delete(self, table: str, eq_col: str, eq_val: str) -> None:
        path = f"/rest/v1/{table}?{eq_col}=eq.{urllib.parse.quote(eq_val)}"
        self._request("DELETE", path)

    def storage_head(self, bucket: str, key: str) -> int:
        """Returns HTTP status code for HEAD on a storage object."""
        url = f"{self.url}/storage/v1/object/info/{bucket}/{urllib.parse.quote(key)}"
        req = urllib.request.Request(url, method="GET", headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code


# ---------------------------------------------------------------------------
# Modal trigger
# ---------------------------------------------------------------------------

def trigger_modal(trigger_url: str, run_id: str) -> dict:
    body = json.dumps({"run_id": run_id}).encode()
    req = urllib.request.Request(
        trigger_url, data=body, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Modal trigger HTTP {e.code}: {raw}")


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

TERMINAL_STATES = {"delivered", "failed", "awaiting_review", "rejected"}


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def poll(sb: Supabase, run_id: str) -> dict:
    print(f"\n[{ts()}] Polling runs.id={run_id} every {POLL_INTERVAL}s "
          f"(timeout {POLL_TIMEOUT}s)...", flush=True)
    start = time.time()
    last_status = None
    while True:
        if time.time() - start > POLL_TIMEOUT:
            print(f"[{ts()}] TIMEOUT after {POLL_TIMEOUT}s")
            return sb.select_one("runs", "id", run_id)

        # Tolerate transient network errors — pipeline runs independently on Modal
        try:
            row = sb.select_one("runs", "id", run_id)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            print(f"[{ts()}] (transient: {e}) — retrying in {POLL_INTERVAL}s", flush=True)
            time.sleep(POLL_INTERVAL)
            continue
        if not row:
            print(f"[{ts()}] ERROR: run row vanished")
            return {}

        status = row.get("status")
        if status != last_status:
            elapsed = int(time.time() - start)
            print(f"[{ts()}] +{elapsed:>4}s  status: {last_status} -> {status}", flush=True)
            last_status = status

        if status in TERMINAL_STATES:
            return row

        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(row: dict, sb: Supabase) -> bool:
    """Print a full report of the run row's terminal state. Returns True on success."""
    print("\n" + "=" * 60)
    print("  FINAL ROW STATE")
    print("=" * 60)
    interesting = [
        "id", "user_id", "status", "prompt", "voice_id",
        "storage_path", "duration_seconds",
        "qc_verdict", "qc_notes", "rejection_reason",
        "modal_cost_usd", "api_cost_usd",
        "started_at", "finished_at", "delivered_at",
    ]
    for k in interesting:
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + "..."
        print(f"  {k:<20} = {v}")

    status = row.get("status")
    print()
    if status == "awaiting_review":
        print("  [PASS] Pipeline succeeded -- verifying storage upload...")
        run_id = row["id"]
        storage_status = sb.storage_head("reels", f"{run_id}/final.mp4")
        if storage_status == 200:
            print(f"  [PASS] Storage object exists at reels/{run_id}/final.mp4")
            return True
        else:
            print(f"  [FAIL] Storage HEAD returned {storage_status} -- file MISSING "
                  f"despite row claiming success. INVESTIGATE.")
            return False
    elif status == "failed":
        print("  [FAIL] Pipeline FAILED. Inspect rejection_reason and qc_notes above.")
        print("  Also check Modal logs at https://modal.com/apps/")
        return False
    elif status == "rejected":
        print("  [WARN] Status='rejected' -- unexpected for an automated run.")
        return False
    else:
        print(f"  [WARN] Terminal state '{status}' not handled.")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="End-to-end wiring test for Igloo Modal worker")
    parser.add_argument("--topic", default="why morning sunlight matters",
                        help="Test topic for the pipeline")
    parser.add_argument("--theme", default="Health & Wellness")
    parser.add_argument("--duration", type=int, default=40)
    parser.add_argument("--no-trigger", action="store_true",
                        help="Insert rows but don't trigger Modal (for manual testing)")
    parser.add_argument("--poll-only", default=None, metavar="RUN_ID",
                        help="Skip insert+trigger, just poll an existing run")
    args = parser.parse_args()

    supabase_url = require("SUPABASE_URL")
    service_key = require("SUPABASE_SERVICE_ROLE_KEY")
    trigger_url = require("MODAL_TRIGGER_URL")

    sb = Supabase(supabase_url, service_key)

    print("=" * 60)
    print("  IGLOO MODAL WIRING TEST")
    print("=" * 60)
    print(f"  Supabase URL : {supabase_url}")
    print(f"  Modal URL    : {trigger_url}")
    print(f"  Topic        : {args.topic}")
    print(f"  Duration     : {args.duration}s")
    print()

    if args.poll_only:
        row = poll(sb, args.poll_only)
        ok = report(row, sb)
        sys.exit(0 if ok else 2)

    # ----- Insert test user -----
    test_email = f"wiring_test_{int(time.time())}@igloo.video"
    test_clerk_id = f"wiring_test_clerk_{int(time.time())}"
    print(f"[{ts()}] Inserting test user: {test_email}")
    user = sb.insert("users", {
        "clerk_user_id": test_clerk_id,
        "email": test_email,
    })
    user_id = user["id"]
    print(f"[{ts()}]   user.id = {user_id}")

    # ----- Insert test run -----
    print(f"[{ts()}] Inserting test run (status='queued')")
    run = sb.insert("runs", {
        "user_id": user_id,
        "prompt": args.topic,
        "status": "queued",
        "params": {"theme": args.theme, "duration": args.duration},
    })
    run_id = run["id"]
    print(f"[{ts()}]   run.id  = {run_id}")

    if args.no_trigger:
        print(f"\n--no-trigger set. Run this later to resume:")
        print(f"  python infra/modal/test_wiring.py --poll-only {run_id}")
        return

    # ----- Trigger Modal -----
    print(f"\n[{ts()}] POST to Modal trigger endpoint...")
    try:
        result = trigger_modal(trigger_url, run_id)
    except Exception as e:
        print(f"  ❌ Trigger failed: {e}")
        print(f"  Test row IDs (clean up manually): user={user_id} run={run_id}")
        sys.exit(1)
    print(f"[{ts()}]   trigger response: {result}")

    if not result.get("ok"):
        print(f"  ❌ Modal returned ok=false")
        sys.exit(1)

    # ----- Poll -----
    row = poll(sb, run_id)
    ok = report(row, sb)

    # ----- Cleanup hint -----
    print()
    print("=" * 60)
    print("  CLEANUP (run when done inspecting)")
    print("=" * 60)
    print(f"  -- In Supabase SQL Editor:")
    print(f"  delete from public.runs    where id = '{run_id}';")
    print(f"  delete from public.users   where id = '{user_id}';")
    print(f"  -- In Storage > reels: delete folder {run_id}/")
    print()

    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
