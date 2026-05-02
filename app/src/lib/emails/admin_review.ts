// Internal admin notification — fires when a reel hits awaiting_review.
// Plain-styled (no hero band, no marketing copy) so admins can scan
// quickly. Recipients come from ADMIN_NOTIFICATION_EMAILS env var.

import "server-only";

export type AdminReviewInput = {
  runId: string;
  topic: string;
  userEmail: string;
  userFirstName: string | null;
  durationSeconds: number | null;
  finishedAt: string | null;
  appUrl: string;
};

export type RenderedAdminEmail = {
  subject: string;
  html: string;
  text: string;
};

const FONT_STACK =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

function truncate(s: string, n: number): string {
  if (!s) return "";
  if (s.length <= n) return s;
  return s.slice(0, n - 1).trimEnd() + "…";
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "(unknown)";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function renderAdminReview(input: AdminReviewInput): RenderedAdminEmail {
  const topicShort = truncate(input.topic, 80);
  const subject = `[Igloo] Review needed: ${topicShort}`;
  const reviewUrl = `${input.appUrl}/admin`;
  const runUrl = `${input.appUrl}/runs/${input.runId}`;
  const senderLabel = input.userFirstName
    ? `${input.userFirstName} (${input.userEmail})`
    : input.userEmail;
  const duration = input.durationSeconds != null
    ? `${input.durationSeconds.toFixed(1)}s`
    : "(unknown)";

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(subject)}</title>
</head>
<body style="margin:0;padding:0;background:#f6f6f6;font-family:${FONT_STACK};color:#1a1a1a;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f6f6f6;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;">
          <tr>
            <td style="padding:24px 28px 8px 28px;">
              <p style="margin:0;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#737373;">Igloo &middot; admin notification</p>
              <h1 style="margin:8px 0 0 0;font-size:20px;line-height:26px;font-weight:600;color:#1a1a1a;">A reel is waiting for review</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 28px 24px 28px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="font-size:14px;line-height:22px;color:#1a1a1a;">
                <tr><td style="padding:8px 0;width:140px;color:#737373;vertical-align:top;">Topic</td><td style="padding:8px 0;font-weight:500;">${escapeHtml(input.topic)}</td></tr>
                <tr><td style="padding:8px 0;color:#737373;vertical-align:top;">From</td><td style="padding:8px 0;">${escapeHtml(senderLabel)}</td></tr>
                <tr><td style="padding:8px 0;color:#737373;vertical-align:top;">Duration</td><td style="padding:8px 0;">${escapeHtml(duration)}</td></tr>
                <tr><td style="padding:8px 0;color:#737373;vertical-align:top;">Finished</td><td style="padding:8px 0;">${escapeHtml(formatTimestamp(input.finishedAt))}</td></tr>
                <tr><td style="padding:8px 0;color:#737373;vertical-align:top;">Run ID</td><td style="padding:8px 0;font-family:monospace;font-size:12px;color:#737373;">${escapeHtml(input.runId)}</td></tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px 28px 28px;">
              <a href="${escapeHtml(reviewUrl)}" style="display:inline-block;padding:12px 24px;background:#1a1a1a;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">Open admin queue &rarr;</a>
              &nbsp;
              <a href="${escapeHtml(runUrl)}" style="display:inline-block;padding:12px 24px;background:#ffffff;color:#1a1a1a;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;border:1px solid #e0e0e0;">View this run</a>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 28px 24px 28px;border-top:1px solid #f0f0f0;font-size:12px;color:#a3a3a3;">
              Sent automatically when status flips to awaiting_review. Edit the recipient list via the <code style="background:#f4f4f4;padding:1px 4px;border-radius:3px;">ADMIN_NOTIFICATION_EMAILS</code> env var on Vercel.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;

  const text = [
    "[Igloo] A reel is waiting for review",
    "",
    `Topic:    ${input.topic}`,
    `From:     ${senderLabel}`,
    `Duration: ${duration}`,
    `Finished: ${formatTimestamp(input.finishedAt)}`,
    `Run ID:   ${input.runId}`,
    "",
    `Open admin queue: ${reviewUrl}`,
    `View this run:    ${runUrl}`,
    "",
    "---",
    "Sent automatically when status flips to awaiting_review.",
    "Edit recipients via ADMIN_NOTIFICATION_EMAILS env var on Vercel.",
  ].join("\n");

  return { subject, html, text };
}
