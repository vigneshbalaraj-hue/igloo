import { redirect } from "next/navigation";
import { isAdmin } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

export default async function AdminWaitlistPage() {
  if (!(await isAdmin())) {
    redirect("/");
  }

  const supabase = getServerSupabase();

  // All users
  const { data: allUsers } = await supabase
    .from("users")
    .select("id, email, created_at")
    .order("created_at", { ascending: false });

  // User IDs with at least one captured payment
  const { data: payingRows } = await supabase
    .from("payments")
    .select("user_id")
    .eq("status", "captured");

  const payingUserIds = new Set(
    (payingRows ?? []).map((p: { user_id: string }) => p.user_id)
  );

  const waitlisted = (allUsers ?? []).filter(
    (u: { id: string }) => !payingUserIds.has(u.id)
  );

  return (
    <main className="flex-1 px-6 py-12">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          Waitlist
        </h1>
        <p className="text-neutral-400 mb-8">
          {waitlisted.length} user{waitlisted.length !== 1 ? "s" : ""} signed
          up but haven&apos;t purchased yet.
        </p>

        {waitlisted.length === 0 ? (
          <div className="rounded-xl bg-neutral-900 border border-neutral-800 px-6 py-12 text-center text-neutral-400">
            No waitlisted users.
          </div>
        ) : (
          <div className="space-y-3">
            {waitlisted.map(
              (u: { id: string; email: string; created_at: string }) => (
                <div
                  key={u.id}
                  className="rounded-xl bg-neutral-900 border border-neutral-800 px-5 py-4 flex items-center justify-between"
                >
                  <div>
                    <p className="text-sm text-neutral-200">{u.email}</p>
                    <p className="text-xs text-neutral-500 font-mono mt-1">
                      {u.id.slice(0, 8)}
                    </p>
                  </div>
                  <p className="text-xs text-neutral-500">
                    {new Date(u.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </p>
                </div>
              )
            )}
          </div>
        )}
      </div>
    </main>
  );
}
