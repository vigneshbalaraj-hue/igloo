"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function AdminActions({ runId }: { runId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState<"deliver" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  async function deliver() {
    setError(null);
    setBusy("deliver");
    try {
      const res = await fetch(`/api/admin/runs/${runId}/deliver`, {
        method: "POST",
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || `HTTP ${res.status}`);
      }
      router.push("/admin");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function reject() {
    setError(null);
    setBusy("reject");
    try {
      const res = await fetch(`/api/admin/runs/${runId}/reject`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ reason: rejectReason || "no_reason" }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || `HTTP ${res.status}`);
      }
      router.push("/admin");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-5">
      <div className="text-xs uppercase tracking-wider text-neutral-500 mb-4">
        Actions
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {!showRejectForm ? (
        <div className="flex gap-3">
          <button
            onClick={deliver}
            disabled={busy !== null}
            className="flex-1 rounded-full bg-emerald-500 text-black px-5 py-3 font-medium hover:bg-emerald-400 transition disabled:opacity-50"
          >
            {busy === "deliver" ? "Delivering…" : "Deliver"}
          </button>
          <button
            onClick={() => setShowRejectForm(true)}
            disabled={busy !== null}
            className="flex-1 rounded-full bg-red-600 text-white px-5 py-3 font-medium hover:bg-red-500 transition disabled:opacity-50"
          >
            Reject + refund
          </button>
        </div>
      ) : (
        <div>
          <label className="block text-sm font-medium mb-2">Reason</label>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            placeholder="Why is this reel being rejected?"
            className="w-full rounded-lg bg-neutral-950 border border-neutral-800 px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-white/30"
          />
          <div className="mt-3 flex gap-3">
            <button
              onClick={reject}
              disabled={busy !== null}
              className="flex-1 rounded-full bg-red-600 text-white px-5 py-3 font-medium hover:bg-red-500 transition disabled:opacity-50"
            >
              {busy === "reject" ? "Rejecting…" : "Confirm reject"}
            </button>
            <button
              onClick={() => setShowRejectForm(false)}
              disabled={busy !== null}
              className="flex-1 rounded-full border border-neutral-700 px-5 py-3 font-medium hover:bg-neutral-800 transition disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
