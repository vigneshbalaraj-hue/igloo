import Link from "next/link";
import { redirect } from "next/navigation";
import { clerkClient } from "@clerk/nextjs/server";
import { isAdmin } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

const BETA_CAP = 30;

function formatINR(paise: number): string {
  return "₹" + (paise / 100).toLocaleString("en-IN");
}

type TileProps = {
  label: string;
  total: string | number;
  last7?: string | number;
  href?: string;
  sub?: string;
};

function Tile({ label, total, last7, href, sub }: TileProps) {
  const inner = (
    <div className="rounded-xl bg-neutral-900 border border-neutral-800 hover:border-neutral-700 transition px-5 py-4 h-full">
      <div className="text-xs uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold">{total}</div>
      {last7 !== undefined && (
        <div className="mt-1 text-xs text-neutral-500">
          <span className="text-neutral-400">{last7}</span> in last 7 days
        </div>
      )}
      {sub && <div className="mt-1 text-xs text-neutral-500">{sub}</div>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export default async function AdminMetricsPage() {
  if (!(await isAdmin())) {
    redirect("/");
  }

  const supabase = getServerSupabase();
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const sevenDaysAgoIso = sevenDaysAgo.toISOString();
  const sevenDaysAgoMs = sevenDaysAgo.getTime();

  const [
    clerkTotalRes,
    clerkRecentRes,
    paymentsAllRes,
    paymentsRecentRes,
    runsDeliveredRes,
    runsDeliveredRecentRes,
    runsInFlightRes,
    runsFailedRes,
    runsFailedRecentRes,
    feedbackRes,
  ] = await Promise.all([
    (async () => {
      try {
        const c = await clerkClient();
        return await c.users.getCount();
      } catch {
        return null;
      }
    })(),
    (async () => {
      try {
        const c = await clerkClient();
        // Beta-scale: fetch most recent 500 and filter client-side.
        const list = await c.users.getUserList({ limit: 500, orderBy: "-created_at" });
        return list.data.filter((u) => u.createdAt >= sevenDaysAgoMs).length;
      } catch {
        return null;
      }
    })(),
    supabase
      .from("payments")
      .select("user_id, amount_paise")
      .eq("status", "captured"),
    supabase
      .from("payments")
      .select("user_id, amount_paise")
      .eq("status", "captured")
      .gte("created_at", sevenDaysAgoIso),
    supabase
      .from("runs")
      .select("id", { count: "exact", head: true })
      .eq("status", "delivered"),
    supabase
      .from("runs")
      .select("id", { count: "exact", head: true })
      .eq("status", "delivered")
      .gte("created_at", sevenDaysAgoIso),
    supabase
      .from("runs")
      .select("id", { count: "exact", head: true })
      .in("status", ["running", "queued", "awaiting_review"]),
    supabase
      .from("runs")
      .select("id", { count: "exact", head: true })
      .eq("status", "failed"),
    supabase
      .from("runs")
      .select("id", { count: "exact", head: true })
      .eq("status", "failed")
      .gte("created_at", sevenDaysAgoIso),
    supabase.from("run_feedback").select("rating"),
  ]);

  type PaymentRow = { user_id: string; amount_paise: number };
  const paymentsAll = (paymentsAllRes.data ?? []) as PaymentRow[];
  const paymentsRecent = (paymentsRecentRes.data ?? []) as PaymentRow[];
  const revenueTotal = paymentsAll.reduce((s, p) => s + (p.amount_paise ?? 0), 0);
  const revenueRecent = paymentsRecent.reduce((s, p) => s + (p.amount_paise ?? 0), 0);
  const payingTotal = new Set(paymentsAll.map((p) => p.user_id)).size;
  const payingRecent = new Set(paymentsRecent.map((p) => p.user_id)).size;

  const ratings = (feedbackRes.data ?? []) as { rating: number }[];
  const avgRating =
    ratings.length > 0 ? ratings.reduce((s, r) => s + r.rating, 0) / ratings.length : null;

  return (
    <main className="flex-1 px-6 py-12">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Metrics</h1>
            <p className="mt-1 text-neutral-400 text-sm">
              Snapshot of the business. Traffic lives in the Vercel dashboard.
            </p>
          </div>
          <div className="flex gap-4 text-sm">
            <Link href="/admin" className="text-neutral-400 hover:text-neutral-200">
              Queue
            </Link>
            <Link href="/admin/feedback" className="text-neutral-400 hover:text-neutral-200">
              Feedback
            </Link>
            <Link href="/admin/waitlist" className="text-neutral-400 hover:text-neutral-200">
              Waitlist
            </Link>
            <Link href="/admin/alerts" className="text-neutral-400 hover:text-neutral-200">
              Alerts
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Tile
            label="Signups (Clerk)"
            total={clerkTotalRes ?? "—"}
            last7={clerkRecentRes ?? "—"}
          />
          <Tile
            label="Paying customers"
            total={payingTotal}
            last7={payingRecent}
            sub={`${payingTotal} / ${BETA_CAP} beta cap`}
            href="/admin/waitlist"
          />
          <Tile
            label="Revenue"
            total={formatINR(revenueTotal)}
            last7={formatINR(revenueRecent)}
          />
          <Tile
            label="Avg rating"
            total={avgRating !== null ? `${avgRating.toFixed(2)} ★` : "—"}
            sub={`n = ${ratings.length}`}
            href="/admin/feedback"
          />
          <Tile
            label="Reels delivered"
            total={runsDeliveredRes.count ?? 0}
            last7={runsDeliveredRecentRes.count ?? 0}
            href="/admin"
          />
          <Tile
            label="Reels in flight"
            total={runsInFlightRes.count ?? 0}
            sub="running / queued / awaiting review"
            href="/admin"
          />
          <Tile
            label="Reels failed"
            total={runsFailedRes.count ?? 0}
            last7={runsFailedRecentRes.count ?? 0}
          />
          <Tile
            label="Beta cap usage"
            total={`${payingTotal} / ${BETA_CAP}`}
            sub={payingTotal >= BETA_CAP ? "Cap reached — waitlist active" : `${BETA_CAP - payingTotal} slots left`}
            href="/admin/waitlist"
          />
        </div>

        <p className="mt-8 text-xs text-neutral-600">
          Revenue &amp; payments count captured Razorpay payments only. Clerk 7d count is approximate (scans 500 most recent users).
        </p>
      </div>
    </main>
  );
}
