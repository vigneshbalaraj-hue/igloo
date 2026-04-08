import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { isAdmin } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";
import AdminActions from "./AdminActions";

export const dynamic = "force-dynamic";

const STORAGE_BUCKET = "reels";
const SIGNED_URL_TTL_SECONDS = 60 * 60; // 1h

export default async function AdminReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  if (!(await isAdmin())) {
    redirect("/");
  }

  const { id } = await params;
  const supabase = getServerSupabase();

  const { data: run, error } = await supabase
    .from("runs")
    .select(
      "id, status, prompt, storage_path, rejection_reason, created_at, finished_at, user_id"
    )
    .eq("id", id)
    .maybeSingle();

  if (error) {
    return (
      <main className="flex-1 px-6 py-12">
        <div className="mx-auto max-w-3xl">
          <div className="rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
            {error.message}
          </div>
        </div>
      </main>
    );
  }
  if (!run) notFound();

  let signedUrl: string | null = null;
  if (run.storage_path) {
    // storage_path is like 'reels/<run_id>/final.mp4' — strip the bucket prefix
    const objectKey = run.storage_path.replace(/^reels\//, "");
    const { data: signed } = await supabase.storage
      .from(STORAGE_BUCKET)
      .createSignedUrl(objectKey, SIGNED_URL_TTL_SECONDS);
    signedUrl = signed?.signedUrl ?? null;
  }

  return (
    <main className="flex-1 px-6 py-12">
      <div className="mx-auto max-w-3xl">
        <Link
          href="/admin"
          className="text-sm text-neutral-400 hover:text-neutral-200 mb-4 inline-block"
        >
          ← Back to queue
        </Link>

        <h1 className="text-2xl font-semibold tracking-tight mb-1">
          Review reel
        </h1>
        <p className="text-xs text-neutral-500 font-mono mb-8">{run.id}</p>

        <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-5 mb-6">
          <div className="text-xs uppercase tracking-wider text-neutral-500 mb-1">
            Topic
          </div>
          <div className="text-neutral-100">{run.prompt}</div>
        </div>

        <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-5 mb-6">
          <div className="text-xs uppercase tracking-wider text-neutral-500 mb-3">
            Status
          </div>
          <div className="text-neutral-100">{run.status.replace(/_/g, " ")}</div>
          {run.rejection_reason && (
            <div className="mt-2 text-sm text-red-300">
              {run.rejection_reason}
            </div>
          )}
        </div>

        {signedUrl ? (
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-5 mb-6">
            <div className="text-xs uppercase tracking-wider text-neutral-500 mb-3">
              Final reel
            </div>
            <video
              src={signedUrl}
              controls
              className="w-full max-h-[80vh] rounded-lg bg-black"
            />
          </div>
        ) : (
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-5 mb-6 text-neutral-400">
            No video uploaded yet — pipeline likely still running.
          </div>
        )}

        {run.status === "awaiting_review" && (
          <AdminActions runId={run.id} />
        )}
      </div>
    </main>
  );
}
