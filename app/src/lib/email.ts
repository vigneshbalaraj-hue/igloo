// Resend wrapper for the drip-email system.
//
// One public function: sendDripEmail({ userId, emailType }).
// - Looks up the user (email, first_name, unsubscribe_token).
// - Checks email_unsubscribed gate.
// - Inserts a sent_emails row first (UNIQUE on user_id+email_type),
//   so concurrent webhook+cron firings collapse on the index.
// - Renders the template, calls Resend, updates the row with the result.
// - Idempotent: if a sent_emails row already exists with status='sent',
//   we no-op. If it's 'failed', we retry.

import "server-only";
import { getServerSupabase } from "@/lib/supabase-server";
import { TEMPLATES, type EmailType } from "@/lib/emails/templates";

const RESEND_API_KEY = process.env.RESEND_API_KEY ?? "";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://igloo.video";
const FROM_ADDRESS = "Vignesh from Igloo <support@igloo.video>";
const REPLY_TO = "support@igloo.video";

type ClerkSdkUser = {
  emailAddresses?: Array<{ id: string; emailAddress: string }>;
  primaryEmailAddressId?: string | null;
  firstName?: string | null;
};

export type SendDripResult =
  | { ok: true; status: "sent"; resendMessageId: string | null }
  | { ok: true; status: "skipped"; reason: string }
  | { ok: false; error: string };

type SupabaseUserRow = {
  id: string;
  clerk_user_id: string;
  email: string;
  email_unsubscribed: boolean;
  unsubscribe_token: string;
  /** Optional first_name shipped from Clerk, if a webhook/backfill populated it */
  first_name?: string | null;
};

function deriveFirstNameFromEmail(email: string): string {
  const local = email.split("@")[0] ?? "";
  // strip digits + suffixes after ./_/-
  const cleaned = local.replace(/[\d._\-]+.*$/, "");
  if (cleaned.length < 2) return "there";
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1).toLowerCase();
}

export async function sendDripEmail(args: {
  userId: string;
  emailType: EmailType;
  /** Optional override for the recipient's first name (e.g. from Clerk webhook payload) */
  firstNameOverride?: string | null;
}): Promise<SendDripResult> {
  const supabase = getServerSupabase();

  if (!RESEND_API_KEY) {
    console.error("[email] RESEND_API_KEY not set");
    return { ok: false, error: "resend_key_missing" };
  }

  const { data: userRow, error: userErr } = await supabase
    .from("users")
    .select("id, clerk_user_id, email, email_unsubscribed, unsubscribe_token, first_name")
    .eq("id", args.userId)
    .maybeSingle<SupabaseUserRow>();

  if (userErr) {
    console.error("[email] user lookup failed", userErr);
    return { ok: false, error: "user_lookup_failed" };
  }
  if (!userRow) return { ok: false, error: "user_not_found" };

  if (userRow.email_unsubscribed) {
    return { ok: true, status: "skipped", reason: "unsubscribed" };
  }

  const firstName =
    args.firstNameOverride?.trim() ||
    userRow.first_name?.trim() ||
    deriveFirstNameFromEmail(userRow.email);

  const unsubscribeUrl = `${APP_URL}/unsubscribe/${userRow.unsubscribe_token}`;

  // Insert/upsert the sent_emails row first. UNIQUE(user_id, email_type)
  // catches concurrent firings — second insert raises 23505 and we treat
  // that as "already in flight" and bail.
  const { data: existingRow, error: existingErr } = await supabase
    .from("sent_emails")
    .select("id, status")
    .eq("user_id", args.userId)
    .eq("email_type", args.emailType)
    .maybeSingle();

  if (existingErr) {
    console.error("[email] sent_emails lookup failed", existingErr);
    return { ok: false, error: "sent_emails_lookup_failed" };
  }

  let rowId: string;
  if (existingRow) {
    if (existingRow.status === "sent" || existingRow.status === "skipped") {
      return { ok: true, status: "skipped", reason: `already_${existingRow.status}` };
    }
    rowId = existingRow.id;
  } else {
    const { data: inserted, error: insertErr } = await supabase
      .from("sent_emails")
      .insert({
        user_id: args.userId,
        email_type: args.emailType,
        status: "pending",
      })
      .select("id")
      .single();

    if (insertErr) {
      // 23505 means another caller raced us. Treat as already-handled.
      if ((insertErr as { code?: string }).code === "23505") {
        return { ok: true, status: "skipped", reason: "race_already_recorded" };
      }
      console.error("[email] sent_emails insert failed", insertErr);
      return { ok: false, error: "sent_emails_insert_failed" };
    }
    rowId = inserted.id;
  }

  // Render template
  const template = TEMPLATES[args.emailType];
  if (!template) {
    return { ok: false, error: `unknown_email_type:${args.emailType}` };
  }
  const rendered = template({ firstName, unsubscribeUrl });

  // Send via Resend
  let resendMessageId: string | null = null;
  let sendError: string | null = null;

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: FROM_ADDRESS,
        to: [userRow.email],
        reply_to: REPLY_TO,
        subject: rendered.subject,
        html: rendered.html,
        text: rendered.text,
        // Resend honors a List-Unsubscribe header automatically when
        // the body has one, but explicit is better.
        headers: {
          "List-Unsubscribe": `<${unsubscribeUrl}>`,
          "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        tags: [{ name: "email_type", value: args.emailType }],
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      sendError = `resend_${res.status}: ${text.slice(0, 500)}`;
    } else {
      const json = (await res.json()) as { id?: string };
      resendMessageId = json.id ?? null;
    }
  } catch (e) {
    sendError = e instanceof Error ? e.message : String(e);
  }

  // Update the sent_emails row with the outcome.
  const { error: updateErr } = await supabase
    .from("sent_emails")
    .update({
      status: sendError ? "failed" : "sent",
      resend_message_id: resendMessageId,
      error_message: sendError,
      sent_at: sendError ? null : new Date().toISOString(),
    })
    .eq("id", rowId);

  if (updateErr) {
    console.error("[email] sent_emails update failed", updateErr);
    // Don't bail — the email was sent (or wasn't), and the update
    // failure is recoverable on next sweep.
  }

  if (sendError) {
    console.error("[email] resend send failed", { emailType: args.emailType, sendError });
    return { ok: false, error: sendError };
  }

  return { ok: true, status: "sent", resendMessageId };
}

/**
 * Update a Clerk user's first_name in our Supabase row, if available.
 * Called from the Clerk webhook on user.created so subsequent drips
 * use the real name instead of the email-derived fallback.
 */
export function extractClerkFirstName(clerkUser: ClerkSdkUser): string | null {
  const fn = clerkUser.firstName?.trim();
  if (fn && fn.length > 0) return fn;
  return null;
}
