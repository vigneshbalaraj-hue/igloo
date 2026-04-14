import { redirect } from "next/navigation";
import { isAdmin } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

type AlertRow = {
  id: string;
  razorpay_payment_id: string;
  razorpay_order_id: string | null;
  email: string | null;
  clerk_user_id: string | null;
  step: string;
  error_message: string | null;
  source: string | null;
  resolved: boolean;
  created_at: string;
};

type PipelineAlertRow = {
  id: string;
  run_id: string | null;
  user_id: string | null;
  kind: string;
  error_message: string | null;
  context: Record<string, unknown> | null;
  resolved: boolean;
  created_at: string;
};

export default async function AdminAlertsPage() {
  if (!(await isAdmin())) {
    redirect("/");
  }

  const supabase = getServerSupabase();
  const [paymentResult, pipelineResult] = await Promise.all([
    supabase
      .from("payment_alerts")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(100),
    supabase
      .from("pipeline_alerts")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(100),
  ]);

  const { data: alerts, error } = paymentResult;
  const { data: pipelineAlerts, error: pipelineError } = pipelineResult;

  const rows = (alerts ?? []) as AlertRow[];
  const unresolved = rows.filter((a) => !a.resolved).length;
  const pipelineRows = (pipelineAlerts ?? []) as PipelineAlertRow[];
  const pipelineUnresolved = pipelineRows.filter((a) => !a.resolved).length;

  return (
    <main className="flex-1 px-6 py-12">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          Payment alerts
        </h1>
        <p className="text-neutral-400 mb-6">
          Failures where a customer was charged but credit/run recording failed.
          {unresolved > 0 && (
            <span className="ml-2 inline-flex items-center rounded-full bg-red-950 border border-red-800 px-2.5 py-0.5 text-xs text-red-300">
              {unresolved} unresolved
            </span>
          )}
        </p>

        {error && (
          <div className="rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
            {error.message}
          </div>
        )}

        {rows.length === 0 && !error && (
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-6 py-12 text-center text-neutral-400">
            No payment alerts. All clear.
          </div>
        )}

        <div className="space-y-3">
          {rows.map((alert) => (
            <div
              key={alert.id}
              className={`rounded-xl border px-5 py-4 ${
                alert.resolved
                  ? "bg-neutral-900/50 border-neutral-800/50"
                  : "bg-red-950/30 border-red-900/50"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${
                        alert.resolved ? "bg-neutral-600" : "bg-red-500"
                      }`}
                    />
                    <code className="text-sm text-neutral-200">
                      {alert.step}
                    </code>
                    <span className="text-xs text-neutral-500">
                      {new Date(alert.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-400 font-mono truncate">
                    {alert.razorpay_payment_id}
                  </p>
                  {alert.error_message && (
                    <p className="mt-2 text-xs text-neutral-500 truncate max-w-xl">
                      {alert.error_message}
                    </p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs text-neutral-400">
                    {alert.email ?? "Unknown"}
                  </p>
                  <p className="mt-1 text-xs text-neutral-600">
                    {alert.source ?? "—"}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight mb-2">
            Pipeline alerts
          </h2>
          <p className="text-neutral-400 mb-6">
            Silent pipeline failures: refunds that didn&apos;t land, external API
            blowups, status updates that got lost.
            {pipelineUnresolved > 0 && (
              <span className="ml-2 inline-flex items-center rounded-full bg-red-950 border border-red-800 px-2.5 py-0.5 text-xs text-red-300">
                {pipelineUnresolved} unresolved
              </span>
            )}
          </p>

          {pipelineError && (
            <div className="rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
              {pipelineError.message}
            </div>
          )}

          {pipelineRows.length === 0 && !pipelineError && (
            <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-6 py-12 text-center text-neutral-400">
              No pipeline alerts.
            </div>
          )}

          <div className="space-y-3">
            {pipelineRows.map((alert) => (
              <div
                key={alert.id}
                className={`rounded-xl border px-5 py-4 ${
                  alert.resolved
                    ? "bg-neutral-900/50 border-neutral-800/50"
                    : "bg-red-950/30 border-red-900/50"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${
                          alert.resolved ? "bg-neutral-600" : "bg-red-500"
                        }`}
                      />
                      <code className="text-sm text-neutral-200">
                        {alert.kind}
                      </code>
                      <span className="text-xs text-neutral-500">
                        {new Date(alert.created_at).toLocaleDateString(
                          "en-IN",
                          {
                            day: "numeric",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          }
                        )}
                      </span>
                    </div>
                    {alert.run_id && (
                      <p className="text-xs text-neutral-400 font-mono truncate">
                        run {alert.run_id}
                      </p>
                    )}
                    {alert.error_message && (
                      <p className="mt-2 text-xs text-neutral-500 truncate max-w-xl">
                        {alert.error_message}
                      </p>
                    )}
                    {alert.context && (
                      <pre className="mt-2 text-xs text-neutral-600 overflow-x-auto">
                        {JSON.stringify(alert.context, null, 0)}
                      </pre>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
