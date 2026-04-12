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
 * Retry an async function with exponential backoff.
 * 3 attempts total (1 initial + 2 retries), 200ms/400ms delays.
 * Zero overhead on success — only sleeps after a failure.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  { attempts = 3, baseDelayMs = 200 } = {}
): Promise<T> {
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      if (i === attempts - 1) throw err;
      await new Promise((r) => setTimeout(r, baseDelayMs * 2 ** i));
    }
  }
  throw new Error("unreachable");
}

/**
 * Retry a Supabase call that returns { data, error } instead of throwing.
 * Converts Supabase errors into thrown exceptions so withRetry can catch them.
 * Returns NonNullable<T> — throws if data is null after a successful call.
 */
export async function supabaseRetry<T>(
  fn: () => PromiseLike<{ data: T; error: unknown }>,
  opts?: { attempts?: number; baseDelayMs?: number }
): Promise<NonNullable<T>> {
  return withRetry(async () => {
    const { data, error } = await fn();
    if (error) throw error;
    if (data == null) throw new Error("supabase returned null data");
    return data as NonNullable<T>;
  }, opts);
}

/**
 * Find or create a public.users row for a Clerk user.
 * Lazy-creation pattern: avoids needing a Clerk webhook for Phase 6.
 * (Scale debt: replace with a real user.created webhook later — see
 *  memory/project_phase6_scale_debt.md.)
 *
 * Retries up to 3 times on transient Supabase failures.
 */
export async function getOrCreateUser(
  clerkUserId: string,
  email: string
): Promise<{ id: string; clerk_user_id: string; email: string }> {
  return withRetry(async () => {
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
  });
}
