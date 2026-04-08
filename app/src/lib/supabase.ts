// Browser-side Supabase client.
// Uses the anon key + a Clerk-issued Supabase JWT so RLS gates rows
// to the authenticated user.
//
// Usage in a client component:
//   const { getToken } = useAuth();
//   const supabase = createBrowserSupabase(await getToken({ template: "supabase" }));
//   const { data } = await supabase.from("runs").select("*");

import { createClient, SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export function createBrowserSupabase(clerkToken: string | null): SupabaseClient {
  return createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: {
      headers: clerkToken ? { Authorization: `Bearer ${clerkToken}` } : {},
    },
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
  });
}
