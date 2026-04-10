"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PRICING_TIERS } from "@/lib/pricing";
import type { PricingTier } from "@/lib/pricing";

type RunSummary = {
  id: string;
  status: "draft" | "queued" | "running" | "awaiting_review" | "delivered" | "rejected" | "failed";
  prompt: string;
  storage_path: string | null;
  created_at: string;
  delivered_at: string | null;
};

type Payment = {
  id: string;
  amount_paise: number;
  currency: string;
  status: string;
  tier: string;
  credits_granted: number;
  created_at: string;
};

type CreditEntry = {
  id: string;
  delta: number;
  reason: string;
  note: string | null;
  created_at: string;
};

const STATUS_LABELS: Record<RunSummary["status"], string> = {
  draft: "Draft",
  queued: "Queued",
  running: "Rendering",
  awaiting_review: "In review",
  delivered: "Delivered",
  rejected: "Rejected",
  failed: "Failed",
};

const STATUS_COLORS: Record<RunSummary["status"], string> = {
  draft: "bg-neutral-700 text-neutral-300",
  queued: "bg-yellow-900 text-yellow-300",
  running: "bg-blue-900 text-blue-300",
  awaiting_review: "bg-purple-900 text-purple-300",
  delivered: "bg-emerald-900 text-emerald-300",
  rejected: "bg-red-900 text-red-300",
  failed: "bg-red-900 text-red-300",
};

const REASON_LABELS: Record<string, string> = {
  payment: "Purchase",
  run: "Reel created",
  refund: "Refund",
  admin_grant: "Admin grant",
  admin_revoke: "Admin revoke",
};

const DOWNLOAD_EXPIRY_DAYS = 30;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function isDownloadAvailable(deliveredAt: string | null): boolean {
  if (!deliveredAt) return false;
  const expiry = new Date(deliveredAt);
  expiry.setDate(expiry.getDate() + DOWNLOAD_EXPIRY_DAYS);
  return new Date() < expiry;
}

function formatINR(paise: number): string {
  return "₹" + (paise / 100).toLocaleString("en-IN");
}

export default function ProfilePage() {
  const { user, isLoaded } = useUser();
  const router = useRouter();

  const [balance, setBalance] = useState<number | null>(null);
  const [history, setHistory] = useState<CreditEntry[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (!isLoaded) return;
    if (!user) {
      router.push("/sign-in");
      return;
    }

    Promise.all([
      fetch("/api/credits/balance").then((r) => r.json()),
      fetch("/api/credits/history").then((r) => r.json()),
      fetch("/api/runs").then((r) => r.json()),
      fetch("/api/payments").then((r) => r.json()),
    ])
      .then(([balData, histData, runsData, payData]) => {
        setBalance(balData.balance ?? 0);
        setHistory(histData.history ?? []);
        setRuns(runsData.runs ?? []);
        setPayments(payData.payments ?? []);
      })
      .catch(() => {
        setBalance(0);
      })
      .finally(() => setLoading(false));
  }, [isLoaded, user, router]);

  if (!isLoaded || loading) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p className="text-neutral-500">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col items-center px-6 py-16">
      <div className="w-full max-w-2xl space-y-10">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Your profile</h1>
          <p className="text-neutral-400 mt-1">{user?.primaryEmailAddress?.emailAddress}</p>
        </div>

        {/* ── Credit balance ── */}
        <section>
          <div
            className={`rounded-xl border px-5 py-4 ${
              balance && balance > 0
                ? "border-emerald-800 bg-emerald-950/50"
                : "border-neutral-800 bg-neutral-900"
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-300">Credit balance</p>
                <p
                  className={`text-2xl font-semibold mt-1 ${
                    balance && balance > 0 ? "text-emerald-300" : "text-neutral-100"
                  }`}
                >
                  {balance ?? 0}
                </p>
              </div>
              <Link
                href="/create"
                className="rounded-full bg-white text-black px-5 py-2.5 text-sm font-medium hover:bg-neutral-200 transition"
              >
                Create a reel
              </Link>
            </div>
          </div>

          {/* Transaction log toggle */}
          {history.length > 0 && (
            <div className="mt-3">
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="text-sm text-neutral-500 hover:text-neutral-300 transition"
              >
                {showHistory ? "Hide" : "Show"} transaction history ({history.length})
              </button>

              {showHistory && (
                <div className="mt-3 space-y-2">
                  {history.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between rounded-lg bg-neutral-900 border border-neutral-800 px-4 py-3"
                    >
                      <div>
                        <p className="text-sm text-neutral-200">
                          {REASON_LABELS[entry.reason] ?? entry.reason}
                        </p>
                        {entry.note && (
                          <p className="text-xs text-neutral-500 mt-0.5">{entry.note}</p>
                        )}
                        <p className="text-xs text-neutral-500 mt-0.5">
                          {formatDate(entry.created_at)}
                        </p>
                      </div>
                      <span
                        className={`text-sm font-medium ${
                          entry.delta > 0 ? "text-emerald-400" : "text-red-400"
                        }`}
                      >
                        {entry.delta > 0 ? "+" : ""}
                        {entry.delta}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Your reels ── */}
        <section>
          <h2 className="text-lg font-medium mb-4">Your reels</h2>
          {runs.length === 0 ? (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-5 py-8 text-center">
              <p className="text-neutral-500">No reels yet</p>
              <Link href="/create" className="text-sm text-neutral-400 hover:text-white mt-2 inline-block transition">
                Create your first reel
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <div
                  key={run.id}
                  className="rounded-xl border border-neutral-800 bg-neutral-900 px-5 py-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-neutral-200 truncate">
                        {run.prompt || "Untitled"}
                      </p>
                      <div className="flex items-center gap-3 mt-2">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            STATUS_COLORS[run.status]
                          }`}
                        >
                          {STATUS_LABELS[run.status]}
                        </span>
                        <span className="text-xs text-neutral-500">
                          {formatDate(run.created_at)}
                        </span>
                      </div>
                    </div>
                    {run.status === "delivered" &&
                      run.storage_path &&
                      isDownloadAvailable(run.delivered_at) && (
                        <a
                          href={`/api/runs/${run.id}/download`}
                          className="shrink-0 rounded-full border border-neutral-700 px-4 py-2 text-sm text-neutral-200 hover:bg-neutral-800 transition"
                        >
                          Download
                        </a>
                      )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── Payment history ── */}
        <section>
          <h2 className="text-lg font-medium mb-4">Payment history</h2>
          {payments.length === 0 ? (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-5 py-8 text-center">
              <p className="text-neutral-500">No payments yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {payments.map((payment) => (
                <div
                  key={payment.id}
                  className="flex items-center justify-between rounded-xl border border-neutral-800 bg-neutral-900 px-5 py-4"
                >
                  <div>
                    <p className="text-sm text-neutral-200">
                      {PRICING_TIERS[payment.tier as PricingTier]?.label ?? payment.tier}
                    </p>
                    <p className="text-xs text-neutral-500 mt-1">
                      {formatDate(payment.created_at)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-neutral-200">
                      {formatINR(payment.amount_paise)}
                    </p>
                    <p className="text-xs text-neutral-500 mt-0.5 capitalize">
                      {payment.status}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
