// /unsubscribe/[token]
// One-click unsubscribe page reached from the footer of every drip email.
// Token is users.unsubscribe_token (UUID, set in migration 0011).
//
// On render we set email_unsubscribed = true. A small "Re-subscribe"
// button uses a server action to flip it back.
//
// No Clerk session required — token is the only auth.

import { getServerSupabase } from "@/lib/supabase-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ token: string }>;
};

async function setUnsubscribed(token: string, value: boolean): Promise<{ ok: boolean; email?: string }> {
  const supabase = getServerSupabase();
  const { data, error } = await supabase
    .from("users")
    .update({ email_unsubscribed: value })
    .eq("unsubscribe_token", token)
    .select("email")
    .maybeSingle();
  if (error || !data) return { ok: false };
  return { ok: true, email: data.email };
}

async function resubscribeAction(formData: FormData): Promise<void> {
  "use server";
  const token = formData.get("token");
  if (typeof token !== "string") return;
  await setUnsubscribed(token, false);
}

export default async function UnsubscribePage({ params }: PageProps) {
  const { token } = await params;

  // Validate token shape — UUID v4-ish, 36 chars with dashes.
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(token);
  if (!isUuid) {
    return (
      <main style={pageStyles.wrap}>
        <div style={pageStyles.card}>
          <h1 style={pageStyles.title}>Unsubscribe link not recognised</h1>
          <p style={pageStyles.body}>
            The link looks malformed. If you got here from an Igloo email, check the URL or
            reply to the email and we&rsquo;ll handle it manually.
          </p>
          <a href="https://igloo.video" style={pageStyles.link}>Back to igloo.video</a>
        </div>
      </main>
    );
  }

  const result = await setUnsubscribed(token, true);

  if (!result.ok) {
    return (
      <main style={pageStyles.wrap}>
        <div style={pageStyles.card}>
          <h1 style={pageStyles.title}>We couldn&rsquo;t find that account</h1>
          <p style={pageStyles.body}>
            The unsubscribe link may have expired. Reply to any Igloo email with the word
            UNSUBSCRIBE and we&rsquo;ll take you off the list manually.
          </p>
          <a href="https://igloo.video" style={pageStyles.link}>Back to igloo.video</a>
        </div>
      </main>
    );
  }

  return (
    <main style={pageStyles.wrap}>
      <div style={pageStyles.card}>
        <h1 style={pageStyles.title}>You&rsquo;re unsubscribed.</h1>
        <p style={pageStyles.body}>
          We won&rsquo;t send any more marketing emails to <strong>{result.email}</strong>.
          You&rsquo;ll still receive transactional emails (payment receipts, reel-ready
          notifications) since those are tied to your account.
        </p>
        <p style={pageStyles.body}>Changed your mind?</p>
        <form action={resubscribeAction}>
          <input type="hidden" name="token" value={token} />
          <button type="submit" style={pageStyles.button}>Re-subscribe</button>
        </form>
        <a href="https://igloo.video" style={{ ...pageStyles.link, marginTop: 24 }}>Back to igloo.video</a>
      </div>
    </main>
  );
}

const pageStyles: Record<string, React.CSSProperties> = {
  wrap: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#050505",
    color: "#ededed",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    padding: "48px 24px",
  },
  card: {
    maxWidth: 520,
    width: "100%",
    backgroundColor: "#0a0a0a",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: "40px 32px",
    textAlign: "center",
  },
  title: {
    fontFamily: "Georgia, 'Times New Roman', serif",
    fontSize: 26,
    fontWeight: 400,
    margin: "0 0 16px 0",
    color: "#f0f0f0",
  },
  body: {
    fontSize: 15,
    lineHeight: 1.55,
    color: "#a3a3a3",
    margin: "0 0 16px 0",
  },
  button: {
    display: "inline-block",
    padding: "10px 24px",
    backgroundColor: "transparent",
    color: "#d4a574",
    border: "1px solid #d4a574",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  link: {
    display: "inline-block",
    fontSize: 13,
    color: "#737373",
    textDecoration: "none",
    marginTop: 24,
  },
};
