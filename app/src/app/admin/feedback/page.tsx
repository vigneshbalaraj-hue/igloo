import { redirect } from "next/navigation";
import { isAdmin } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

type FeedbackRow = {
  id: string;
  rating: number;
  comment: string | null;
  created_at: string;
  run_id: string;
  runs: { prompt: string } | null;
  users: { email: string } | null;
};

function Stars({ rating }: { rating: number }) {
  return (
    <span className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <svg
          key={i}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill={i <= rating ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth={1.5}
          className={`h-4 w-4 ${
            i <= rating ? "text-yellow-400" : "text-neutral-600"
          }`}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
          />
        </svg>
      ))}
    </span>
  );
}

export default async function AdminFeedbackPage({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; order?: string }>;
}) {
  if (!(await isAdmin())) {
    redirect("/");
  }

  const { sort, order } = await searchParams;
  const sortColumn = sort === "rating" ? "rating" : "created_at";
  const ascending = order === "asc";

  const supabase = getServerSupabase();
  const { data: feedback, error } = await supabase
    .from("run_feedback")
    .select("id, rating, comment, created_at, run_id, runs(prompt), users(email)")
    .order(sortColumn, { ascending })
    .limit(200);

  const rows = (feedback ?? []) as unknown as FeedbackRow[];

  function sortLink(col: string) {
    const isActive = sortColumn === col;
    const nextOrder = isActive && !ascending ? "asc" : "desc";
    return `/admin/feedback?sort=${col}&order=${nextOrder}`;
  }

  return (
    <main className="flex-1 px-6 py-12">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          Customer feedback
        </h1>
        <p className="text-neutral-400 mb-6">
          All feedback from delivered reels.
        </p>

        <div className="flex gap-4 mb-6 text-sm">
          <a
            href={sortLink("created_at")}
            className={`px-3 py-1.5 rounded-full border transition ${
              sortColumn === "created_at"
                ? "border-neutral-600 bg-neutral-800 text-neutral-200"
                : "border-neutral-800 text-neutral-500 hover:text-neutral-300"
            }`}
          >
            Sort by date {sortColumn === "created_at" ? (ascending ? "\u2191" : "\u2193") : ""}
          </a>
          <a
            href={sortLink("rating")}
            className={`px-3 py-1.5 rounded-full border transition ${
              sortColumn === "rating"
                ? "border-neutral-600 bg-neutral-800 text-neutral-200"
                : "border-neutral-800 text-neutral-500 hover:text-neutral-300"
            }`}
          >
            Sort by rating {sortColumn === "rating" ? (ascending ? "\u2191" : "\u2193") : ""}
          </a>
        </div>

        {error && (
          <div className="rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
            {error.message}
          </div>
        )}

        {rows.length === 0 && !error && (
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-6 py-12 text-center text-neutral-400">
            No feedback yet.
          </div>
        )}

        <div className="space-y-3">
          {rows.map((fb) => (
            <div
              key={fb.id}
              className="rounded-xl bg-neutral-900 border border-neutral-800 px-5 py-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <Stars rating={fb.rating} />
                    <span className="text-xs text-neutral-500">
                      {new Date(fb.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  <p className="text-sm text-neutral-200 truncate">
                    {fb.runs?.prompt ?? "Unknown topic"}
                  </p>
                  {fb.comment && (
                    <p className="mt-2 text-sm text-neutral-400 whitespace-pre-line">
                      {fb.comment}
                    </p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs text-neutral-500">
                    {fb.users?.email ?? "Unknown user"}
                  </p>
                  <p className="mt-1 text-xs text-neutral-600 font-mono">
                    {fb.run_id.slice(0, 8)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
