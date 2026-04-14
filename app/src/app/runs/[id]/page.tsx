"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { createBrowserSupabase } from "@/lib/supabase";
import FeedbackForm from "./feedback-form";

type Run = {
  id: string;
  status:
    | "draft"
    | "queued"
    | "running"
    | "awaiting_review"
    | "delivered"
    | "rejected"
    | "failed";
  prompt: string;
  storage_path: string | null;
  rejection_reason: string | null;
  created_at: string;
};

const STATUS_COPY: Record<Run["status"], string> = {
  draft: "You haven't finished designing your reel yet.",
  queued: "Warming up the engines…",
  running: "Crafting your reel — this takes about 8 minutes.",
  awaiting_review: "Almost done — final quality check.",
  delivered: "Ready to watch.",
  rejected: "We couldn't ship this one. Refunding your credit.",
  failed: "Something broke on our end. We've been notified.",
};

const ERROR_CODE_COPY: Record<string, { title: string; action: string }> = {
  SCRIPT_UNDER_MIN: {
    title:
      "This topic didn't produce enough material for a 30-second reel. Try a broader or more specific angle.",
    action: "Try another topic",
  },
  SCRIPT_OVER_MAX: {
    title:
      "This topic produced too much material to fit in a 60-second reel. Try a narrower angle.",
    action: "Try another topic",
  },
  ALIGNMENT_POOR: {
    title:
      "We couldn't match the voiceover to the captions cleanly this time. Your credit has been refunded — please try again.",
    action: "Try again",
  },
  ALIGNMENT_FAILED: {
    title:
      "The voiceover couldn't be processed. Your credit has been refunded — please try again.",
    action: "Try again",
  },
};

export default function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { getToken, isLoaded } = useAuth();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);

  async function handleResume() {
    setResuming(true);
    setError(null);
    try {
      const res = await fetch(`/api/runs/${id}/resume`, { method: "POST" });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`Resume failed: ${t}`);
      }
      const { studio_url } = await res.json();
      if (!studio_url) throw new Error("Missing studio URL in response.");
      window.location.href = studio_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResuming(false);
    }
  }

  useEffect(() => {
    if (!isLoaded) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const token = await getToken({ template: "supabase" });
        const supabase = createBrowserSupabase(token);
        const { data, error } = await supabase
          .from("runs")
          .select("id,status,prompt,storage_path,rejection_reason,created_at")
          .eq("id", id)
          .maybeSingle();
        if (cancelled) return;
        if (error) {
          setError(error.message);
        } else if (data) {
          setRun(data as Run);
          if (
            data.status !== "delivered" &&
            data.status !== "failed" &&
            data.status !== "rejected" &&
            data.status !== "draft"
          ) {
            timer = setTimeout(poll, 5000);
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id, isLoaded, getToken]);

  return (
    <main className="flex-1 flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-xl">
        <Link
          href="/profile"
          className="text-sm text-neutral-400 hover:text-neutral-200 mb-4 inline-block"
        >
          ← Back to profile
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mb-1">
          Your reel
        </h1>
        <p className="text-sm text-neutral-500 mb-8 font-mono">{id}</p>

        {error && (
          <div className="rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {!run && !error && (
          <div className="text-neutral-400">Loading…</div>
        )}

        {run && (
          <>
            <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-6">
              <div className="text-xs uppercase tracking-wider text-neutral-500 mb-2">
                Status
              </div>
              <div className="text-lg font-medium">{run.status.replace(/_/g, " ")}</div>
              <div className="mt-3 text-neutral-400">{STATUS_COPY[run.status]}</div>

              {run.rejection_reason && (() => {
                const code = run.rejection_reason.trim();
                const tailored = ERROR_CODE_COPY[code];
                if (tailored) {
                  return (
                    <div className="mt-4 rounded-lg bg-neutral-950 border border-neutral-800 p-4">
                      <div className="text-neutral-200">{tailored.title}</div>
                      <Link
                        href="/create"
                        className="mt-3 inline-block rounded-full bg-white text-black px-5 py-2 text-sm font-medium hover:bg-neutral-200 transition"
                      >
                        {tailored.action}
                      </Link>
                    </div>
                  );
                }
                return (
                  <div className="mt-3 text-sm text-red-300">
                    Reason: {run.rejection_reason}
                  </div>
                );
              })()}
            </div>

            <div className="mt-6 rounded-xl bg-neutral-900 border border-neutral-800 p-6">
              <div className="text-xs uppercase tracking-wider text-neutral-500 mb-2">
                Topic
              </div>
              <div className="text-neutral-200">{run.prompt}</div>
            </div>

            {run.status === "delivered" && run.storage_path && (
              <a
                href={`/api/runs/${run.id}/download`}
                className="mt-6 block w-full text-center rounded-full bg-white text-black px-6 py-4 font-medium hover:bg-neutral-200 transition"
              >
                Download your reel
              </a>
            )}

            {run.status === "delivered" && (
              <div className="mt-6">
                <FeedbackForm runId={run.id} />
              </div>
            )}

            {run.status === "draft" && (
              <button
                onClick={handleResume}
                disabled={resuming}
                className="mt-6 w-full rounded-full bg-white text-black px-6 py-4 font-medium hover:bg-neutral-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {resuming ? "Opening studio…" : "Return to studio"}
              </button>
            )}
          </>
        )}
      </div>
    </main>
  );
}
