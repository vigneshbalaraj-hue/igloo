// Server-side Supabase client using the service_role key.
// Bypasses RLS. NEVER import this from a client component.

import "server-only";
import { createClient, SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!;

let cached: SupabaseClient | null = null;

export function getServerSupabase(): SupabaseClient {
  if (!cached) {
    cached = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
        detectSessionInUrl: false,
      },
    });
  }
  return cached;
}

/**
 * Find or create a public.users row for a Clerk user.
 * Lazy-creation pattern: avoids needing a Clerk webhook for Phase 6.
 * (Scale debt: replace with a real user.created webhook later — see
 *  memory/project_phase6_scale_debt.md.)
 */
export async function getOrCreateUser(
  clerkUserId: string,
  email: string
): Promise<{ id: string; clerk_user_id: string; email: string }> {
  const supabase = getServerSupabase();

  const { data: existing, error: selectError } = await supabase
    .from("users")
    .select("id, clerk_user_id, email")
    .eq("clerk_user_id", clerkUserId)
    .maybeSingle();

  if (selectError) throw selectError;
  if (existing) return existing;

  const { data: inserted, error: insertError } = await supabase
    .from("users")
    .insert({ clerk_user_id: clerkUserId, email })
    .select("id, clerk_user_id, email")
    .single();

  if (insertError) throw insertError;
  return inserted;
}
