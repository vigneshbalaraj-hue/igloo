// GET /api/runs/:id/download
// Mints a 60-min Supabase storage signed URL for the run's final
// video and 302-redirects to it.
//
// Auth: Clerk session required AND the run must belong to the user
// AND status must be 'delivered'.

import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { getServerSupabase } from "@/lib/supabase-server";

export const runtime = "nodejs";

const STORAGE_BUCKET = "reels";
const TTL_SECONDS = 60 * 60;

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const supabase = getServerSupabase();

  const { data: run, error } = await supabase
    .from("runs")
    .select("id, status, storage_path, user_id, users!inner(clerk_user_id)")
    .eq("id", id)
    .maybeSingle();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!run) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  // Ownership check: the joined users.clerk_user_id must match Clerk session.
  const owner = (run as unknown as { users: { clerk_user_id: string } | { clerk_user_id: string }[] }).users;
  const ownerClerkId = Array.isArray(owner) ? owner[0]?.clerk_user_id : owner?.clerk_user_id;
  if (ownerClerkId !== userId) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  if (run.status !== "delivered") {
    return NextResponse.json({ error: "not_delivered" }, { status: 400 });
  }
  if (!run.storage_path) {
    return NextResponse.json({ error: "no_video" }, { status: 404 });
  }

  const objectKey = run.storage_path.replace(/^reels\//, "");
  const { data: signed, error: signErr } = await supabase.storage
    .from(STORAGE_BUCKET)
    .createSignedUrl(objectKey, TTL_SECONDS, { download: `igloo-${id}.mp4` });

  if (signErr || !signed) {
    return NextResponse.json(
      { error: signErr?.message ?? "sign_failed" },
      { status: 500 }
    );
  }

  return NextResponse.redirect(signed.signedUrl);
}
