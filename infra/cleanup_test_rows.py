"""
Igloo — cleanup test rows before Phase 9 go-live.

Deletes the Phase 5 / Phase 6 smoke-test artifacts so the production
database starts from a clean slate.

Safety:
  - Dry-run by default. You must pass --yes to actually delete.
  - Prints every row it intends to touch before acting.
  - Deletes in FK-safe order (payments -> user -> cascades runs/credits).
  - Storage files are deleted last (after DB rows are gone).

Target runs (from checkpoints 2026-04-08 sessions 23 + 24):
  - 776cff7c-379c-415c-9812-4cf251e00a01  ("why morning sunlight matters")
  - 518012c6-50f5-415f-b78b-bc8a94bd15d2  ("Fasting benefits")

Usage:
    python infra/cleanup_test_rows.py            # dry-run (default)
    python infra/cleanup_test_rows.py --yes      # actually delete
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_RUN_IDS = [
    "776cff7c-379c-415c-9812-4cf251e00a01",
    "518012c6-50f5-415f-b78b-bc8a94bd15d2",
]

STORAGE_BUCKET = "reels"


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
                return val
    return None


def require(key: str) -> str:
    val = load_env(key)
    if not val:
        print(f"ERROR: {key} not set in .env", file=sys.stderr)
        sys.exit(1)
    return val


# ---------------------------------------------------------------------------
# Supabase REST client
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

    def _request(self, method, path, body=None, extra_headers=None):
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

    def select(self, table: str, filter_query: str) -> list:
        """filter_query is PostgREST query string, e.g. 'id=eq.<uuid>' or 'user_id=in.(a,b)'."""
        path = f"/rest/v1/{table}?{filter_query}"
        status, body = self._request("GET", path)
        if status != 200:
            raise RuntimeError(f"select failed: {status} {body}")
        return body or []

    def delete(self, table: str, filter_query: str) -> None:
        path = f"/rest/v1/{table}?{filter_query}"
        self._request("DELETE", path)

    # Storage API
    def storage_list(self, bucket: str, prefix: str) -> list:
        """List objects under a prefix. Returns list of {name, id, ...}."""
        path = f"/storage/v1/object/list/{bucket}"
        body = {"prefix": prefix, "limit": 1000, "offset": 0}
        status, resp = self._request("POST", path, body=body)
        if status != 200:
            raise RuntimeError(f"storage list failed: {status} {resp}")
        return resp or []

    def storage_remove(self, bucket: str, paths: list) -> None:
        """Delete a list of object paths within a bucket."""
        if not paths:
            return
        url = f"{self.url}/storage/v1/object/{bucket}"
        data = json.dumps({"prefixes": paths}).encode()
        req = urllib.request.Request(
            url, data=data, method="DELETE", headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            print(f"  storage DELETE HTTP {e.code}: {raw}", file=sys.stderr)
            raise


# ---------------------------------------------------------------------------
# Dry-run inspection
# ---------------------------------------------------------------------------

def inspect(sb: Supabase) -> dict:
    """Walk the graph from test run IDs and return everything we'd delete."""
    print("=" * 64)
    print("  INSPECTING TEST ROWS")
    print("=" * 64)

    run_ids_query = ",".join(TEST_RUN_IDS)
    runs = sb.select("runs", f"id=in.({run_ids_query})")
    print(f"\nruns: {len(runs)} rows matched")
    for r in runs:
        print(f"  - {r['id']}  status={r['status']:<16}  "
              f"prompt={(r.get('prompt') or '')[:50]!r}")

    if not runs:
        print("\n(No matching runs found — already cleaned up?)")
        return {"runs": [], "users": [], "payments": [], "credits": [], "storage": []}

    # Collect user_ids and payment_ids from the runs
    user_ids = sorted({r["user_id"] for r in runs})
    payment_ids_from_runs = sorted({r["payment_id"] for r in runs if r.get("payment_id")})

    print(f"\nusers touched: {len(user_ids)}")
    users = []
    for uid in user_ids:
        rows = sb.select("users", f"id=eq.{uid}")
        users.extend(rows)
        for u in rows:
            print(f"  - {u['id']}  clerk={u['clerk_user_id']}  email={u['email']}")

    # For each user, list ALL their runs/payments so we can warn if there's
    # anything we DON'T want to delete.
    print(f"\nall runs belonging to these users:")
    user_ids_query = ",".join(user_ids)
    all_user_runs = sb.select("runs", f"user_id=in.({user_ids_query})")
    test_run_id_set = set(TEST_RUN_IDS)
    extra_runs = [r for r in all_user_runs if r["id"] not in test_run_id_set]
    for r in all_user_runs:
        marker = "  (TEST)" if r["id"] in test_run_id_set else "  (EXTRA - will also be deleted!)"
        print(f"  - {r['id']}  status={r['status']:<16}{marker}")

    print(f"\nall payments belonging to these users:")
    all_user_payments = sb.select("payments", f"user_id=in.({user_ids_query})")
    for p in all_user_payments:
        print(f"  - {p['id']}  razorpay={p.get('razorpay_payment_id')}  "
              f"status={p['status']}  amount_paise={p['amount_paise']}")

    print(f"\nall credits belonging to these users:")
    all_user_credits = sb.select("credits", f"user_id=in.({user_ids_query})")
    for c in all_user_credits:
        print(f"  - {c['id']}  delta={c['delta']:+d}  reason={c['reason']}  "
              f"note={c.get('note') or ''}")

    # Storage
    print(f"\nstorage objects under reels/<run_id>/:")
    storage_paths = []
    for run_id in TEST_RUN_IDS:
        try:
            objs = sb.storage_list(STORAGE_BUCKET, run_id)
        except Exception as e:
            print(f"  {run_id}/  <list failed: {e}>")
            continue
        if not objs:
            print(f"  {run_id}/  (empty)")
            continue
        for obj in objs:
            full = f"{run_id}/{obj['name']}"
            print(f"  {full}")
            storage_paths.append(full)

    if extra_runs:
        print("\n" + "!" * 64)
        print("  WARNING: These users have runs that are NOT in the test list.")
        print("  Deleting the user will CASCADE DELETE those extra runs too.")
        print("  Review the list above carefully before passing --yes.")
        print("!" * 64)

    return {
        "runs": all_user_runs,
        "users": users,
        "payments": all_user_payments,
        "credits": all_user_credits,
        "storage": storage_paths,
        "user_ids": user_ids,
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute(sb: Supabase, plan: dict) -> None:
    print("\n" + "=" * 64)
    print("  EXECUTING DELETIONS")
    print("=" * 64)

    user_ids = plan["user_ids"]
    if not user_ids:
        print("Nothing to delete.")
        return

    user_ids_query = ",".join(user_ids)

    # 1. Delete payments first (FK on users is ON DELETE RESTRICT)
    if plan["payments"]:
        print(f"\n[1/4] Deleting {len(plan['payments'])} payments rows...")
        sb.delete("payments", f"user_id=in.({user_ids_query})")
        print("      ok")
    else:
        print("\n[1/4] No payments to delete.")

    # 2. Delete users (cascades runs + credits)
    print(f"\n[2/4] Deleting {len(plan['users'])} users rows "
          f"(cascades runs + credits)...")
    sb.delete("users", f"id=in.({user_ids_query})")
    print("      ok")

    # 3. Verify cascade worked
    print("\n[3/4] Verifying cascade...")
    remaining_runs = sb.select("runs", f"user_id=in.({user_ids_query})")
    remaining_credits = sb.select("credits", f"user_id=in.({user_ids_query})")
    print(f"      runs remaining for these users: {len(remaining_runs)}")
    print(f"      credits remaining for these users: {len(remaining_credits)}")
    if remaining_runs or remaining_credits:
        print("      WARNING: cascade incomplete — investigate manually")

    # 4. Storage cleanup
    if plan["storage"]:
        print(f"\n[4/4] Deleting {len(plan['storage'])} storage objects...")
        sb.storage_remove(STORAGE_BUCKET, plan["storage"])
        print("      ok")
    else:
        print("\n[4/4] No storage objects to delete.")

    print("\nDone. Database is clean.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true",
                    help="actually delete (default is dry-run)")
    args = ap.parse_args()

    url = require("SUPABASE_URL")
    key = require("SUPABASE_SERVICE_ROLE_KEY")
    sb = Supabase(url, key)

    plan = inspect(sb)

    if not args.yes:
        print("\n" + "-" * 64)
        print("  DRY RUN — nothing was deleted.")
        print("  Re-run with --yes to execute.")
        print("-" * 64)
        return

    execute(sb, plan)


if __name__ == "__main__":
    main()
