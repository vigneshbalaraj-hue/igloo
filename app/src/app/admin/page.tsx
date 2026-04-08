import Link from "next/link";
import { redirect } from "next/navigation";
import { isAdmin } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

export default async function AdminQueuePage() {
  if (!(await isAdmin())) {
    redirect("/");
  }

  const supabase = getServerSupabase();
  const { data: runs, error } = await supabase
    .from("runs")
    .select("id, prompt, status, created_at, finished_at")
    .in("status", ["awaiting_review", "running", "queued"])
    .order("created_at", { ascending: false })
    .limit(50);

  return (
    <main className="flex-1 px-6 py-12">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          Review queue
        </h1>
        <p className="text-neutral-400 mb-8">
          Reels awaiting your call. Newest first.
        </p>

        {error && (
          <div className="rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
            {error.message}
          </div>
        )}

        {runs && runs.length === 0 && (
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-6 py-12 text-center text-neutral-400">
            Queue is empty.
          </div>
        )}

        <div className="space-y-3">
          {runs?.map((run) => (
            <Link
              key={run.id}
              href={`/admin/runs/${run.id}`}
              className="block rounded-xl bg-neutral-900 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900/80 transition px-5 py-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="text-base font-medium truncate">
                    {run.prompt}
                  </div>
                  <div className="mt-1 text-xs text-neutral-500 font-mono">
                    {run.id}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      run.status === "awaiting_review"
                        ? "bg-amber-950 text-amber-300 border border-amber-900"
                        : "bg-neutral-800 text-neutral-400 border border-neutral-700"
                    }`}
                  >
                    {run.status.replace(/_/g, " ")}
                  </span>
                  <div className="mt-1 text-xs text-neutral-500">
                    {new Date(run.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
