// Shared HTML shell for all drip emails.
// Hand-coded, no React Email — keeps zero new deps.
// Renders a 600px container with hero band, body slot, optional offer
// card, optional reply prompt, signature, and footer.
//
// Brand: dark (#050505) + warm gold accent (#d4a574). Mirrors the
// landing palette in app/src/styles/landing.css.

import "server-only";

export type OfferCard = {
  /** e.g. "IGLOO50" */
  code: string;
  /** e.g. 50 (for 50%) */
  discountPct: number;
  /** Original price label, e.g. "₹999" */
  originalPriceLabel: string;
  /** Discounted price label, e.g. "₹499" */
  discountedPriceLabel: string;
  /** "Make my reel — ₹499" */
  ctaText: string;
  /** Where the CTA goes */
  ctaUrl: string;
  /** Tag line above the price, e.g. "YOUR REEL, HALF OFF" */
  eyebrow: string;
  /** "Code IGLOO50 · expires in 14 days · first reel only" */
  fineprint: string;
};

export type ShellInput = {
  /** Hidden inbox-preview text (shown next to the subject line in inbox lists) */
  preheader: string;
  /** Big headline rendered in the hero band, e.g. "A reel for you, on me." */
  heroHeadline: string;
  /** First-name greeting, e.g. "Hey Adnan," */
  greeting: string;
  /** HTML body paragraphs (raw — caller controls markup). Goes between greeting and offer/reply. */
  bodyHtml: string;
  /** Optional offer card. Omit for non-offer emails (welcome, etc.) */
  offer?: OfferCard;
  /** Optional reply prompt above signature, e.g. "What stopped you? Just hit reply." */
  replyPrompt?: string;
  /** Where the demo video is hosted */
  demoUrl?: string;
  /** Per-user unsubscribe URL */
  unsubscribeUrl: string;
};

const BRAND = {
  bg:        "#050505",
  surface:   "#0a0a0a",
  card:      "#1a1208",
  border:    "rgba(212, 165, 116, 0.3)",
  text:      "#ededed",
  textMuted: "#a3a3a3",
  textDim:   "#737373",
  accent:    "#d4a574",
  heroBg:    "#1a0f06",
};

const FONT_STACK =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

const FOOTER_ADDRESS = "Igloo · Bangalore, India · support@igloo.video";

const HERO_IMG = "https://igloo.video/hero-poster.jpg";
const LOGO_IMG = "https://igloo.video/logo.png";
const DEFAULT_DEMO_URL = "https://www.youtube.com/shorts/aLBgr5Ky5wg";
const YT_CHANNEL = "https://www.youtube.com/@IglooYourvideocreationpartner";
const IG_PROFILE = "https://www.instagram.com/igloo.video/";

function renderHero(headline: string): string {
  return `
    <tr>
      <td align="center" style="background-color: ${BRAND.heroBg}; background-image: url('${HERO_IMG}'); background-size: cover; background-position: center; padding: 56px 32px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td align="center">
              <img src="${LOGO_IMG}" width="72" height="72" alt="Igloo" style="display: block; border: 0; width: 72px; height: 72px;" />
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-top: 16px; font-family: Georgia, 'Times New Roman', serif; font-size: 30px; line-height: 36px; color: ${BRAND.text}; font-weight: 400; letter-spacing: 0.5px;">
              ${headline}
            </td>
          </tr>
        </table>
      </td>
    </tr>`;
}

function renderDemoThumbnail(demoUrl: string): string {
  return `
    <tr>
      <td align="center" style="padding: 0 48px 32px 48px;">
        <a href="${demoUrl}" target="_blank" style="text-decoration: none; display: inline-block;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border: 1px solid ${BRAND.border}; border-radius: 8px; overflow: hidden;">
            <tr>
              <td style="background-color: ${BRAND.heroBg}; background-image: url('${HERO_IMG}'); background-size: cover; background-position: center; width: 504px; height: 220px;" align="center" valign="middle">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td align="center" style="background-color: rgba(212, 165, 116, 0.95); border-radius: 50%; width: 56px; height: 56px; font-family: Arial, sans-serif; font-size: 22px; color: ${BRAND.bg};">
                      &#9654;
                    </td>
                  </tr>
                  <tr>
                    <td align="center" style="padding-top: 12px; font-family: ${FONT_STACK}; font-size: 13px; color: ${BRAND.text}; text-shadow: 0 1px 2px rgba(0,0,0,0.5);">
                      Watch the demo &middot; 90 sec
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </a>
      </td>
    </tr>`;
}

function renderOfferCard(offer: OfferCard): string {
  return `
    <tr>
      <td style="padding: 0 48px 32px 48px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: ${BRAND.card}; border: 1px solid ${BRAND.border}; border-radius: 8px;">
          <tr>
            <td style="padding: 28px 32px; font-family: ${FONT_STACK}; color: ${BRAND.text};">
              <p style="margin: 0 0 8px 0; font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase; color: ${BRAND.accent};">${offer.eyebrow}</p>
              <p style="margin: 0 0 4px 0; font-size: 22px; line-height: 28px; font-weight: 600; color: ${BRAND.text};">
                <span style="text-decoration: line-through; color: ${BRAND.textDim}; font-weight: 400;">${offer.originalPriceLabel}</span>&nbsp;&nbsp;${offer.discountedPriceLabel}
              </p>
              <p style="margin: 0 0 20px 0; font-size: 14px; color: ${BRAND.textMuted};">
                ${offer.fineprint}
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" style="background-color: ${BRAND.accent}; border-radius: 6px;">
                    <a href="${offer.ctaUrl}" target="_blank" style="display: inline-block; padding: 16px 32px; font-family: ${FONT_STACK}; font-size: 16px; font-weight: 600; color: ${BRAND.bg}; text-decoration: none; border-radius: 6px;">
                      ${offer.ctaText} &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>`;
}

function renderReplyPrompt(prompt: string): string {
  return `
    <tr>
      <td style="padding: 0 48px 32px 48px; font-family: ${FONT_STACK}; color: ${BRAND.text}; font-size: 16px; line-height: 24px;">
        <p style="margin: 0 0 16px 0;">${prompt}</p>
        <p style="margin: 0;">
          &mdash; Vignesh<br />
          <span style="color: ${BRAND.textMuted}; font-size: 14px;">Founder, Igloo</span>
        </p>
      </td>
    </tr>`;
}

function renderFooter(unsubscribeUrl: string, demoUrl: string): string {
  return `
    <tr>
      <td style="padding: 0 48px;">
        <div style="border-top: 1px solid rgba(255, 255, 255, 0.06); height: 1px; line-height: 1px; font-size: 1px;">&nbsp;</div>
      </td>
    </tr>
    <tr>
      <td align="center" style="padding: 24px 48px 16px 48px; font-family: ${FONT_STACK}; font-size: 12px; line-height: 18px; color: ${BRAND.textDim};">
        <p style="margin: 0 0 12px 0;">
          <a href="https://igloo.video" style="color: ${BRAND.textMuted}; text-decoration: none;">igloo.video</a>
          &nbsp;&middot;&nbsp;
          <a href="${demoUrl}" style="color: ${BRAND.textMuted}; text-decoration: none;">Watch the demo</a>
        </p>
        <p style="margin: 0 0 16px 0;">
          <a href="${YT_CHANNEL}" style="color: ${BRAND.textMuted}; text-decoration: none;">YouTube</a>
          &nbsp;&middot;&nbsp;
          <a href="${IG_PROFILE}" style="color: ${BRAND.textMuted}; text-decoration: none;">Instagram</a>
        </p>
        <p style="margin: 0 0 12px 0;">
          ${FOOTER_ADDRESS}
        </p>
        <p style="margin: 0;">
          You&rsquo;re getting this because you signed up at igloo.video.<br />
          <a href="${unsubscribeUrl}" style="color: ${BRAND.textMuted};">Unsubscribe</a>
        </p>
      </td>
    </tr>`;
}

export function renderShell(input: ShellInput): string {
  const demoUrl = input.demoUrl ?? DEFAULT_DEMO_URL;

  return `<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="x-apple-disable-message-reformatting" />
  <title>Igloo</title>
  <style type="text/css">
    @media only screen and (max-width: 620px) {
      .container { width: 100% !important; }
      .px-32 { padding-left: 20px !important; padding-right: 20px !important; }
    }
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: ${BRAND.bg}; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%;">

  <!-- Preheader (hidden, shows next to subject in inbox) -->
  <div style="display: none; max-height: 0; overflow: hidden; mso-hide: all; font-size: 1px; line-height: 1px; color: ${BRAND.bg};">
    ${input.preheader}
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: ${BRAND.bg};">
    <tr>
      <td align="center" style="padding: 0;">
        <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="width: 600px; max-width: 600px; background-color: ${BRAND.surface};">

          ${renderHero(input.heroHeadline)}

          <tr>
            <td class="px-32" style="padding: 36px 48px 16px 48px; font-family: ${FONT_STACK}; color: ${BRAND.text}; font-size: 16px; line-height: 24px;">
              <p style="margin: 0 0 16px 0;">${input.greeting}</p>
              ${input.bodyHtml}
            </td>
          </tr>

          ${input.offer ? renderDemoThumbnail(demoUrl) : ""}
          ${input.offer ? renderOfferCard(input.offer) : ""}
          ${input.replyPrompt ? renderReplyPrompt(input.replyPrompt) : ""}
          ${renderFooter(input.unsubscribeUrl, demoUrl)}

        </table>
      </td>
    </tr>
  </table>

</body>
</html>`;
}

/**
 * Strip the HTML shell down to a plaintext fallback. Most spam filters
 * weight against HTML-only emails — keep parity, even if the text path
 * is rarely seen.
 */
export function renderPlaintext(input: ShellInput): string {
  const stripTags = (h: string) =>
    h
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n\n")
      .replace(/<[^>]+>/g, "")
      .replace(/&nbsp;/g, " ")
      .replace(/&mdash;/g, "—")
      .replace(/&middot;/g, "·")
      .replace(/&rsquo;/g, "'")
      .replace(/&#8377;/g, "₹")
      .replace(/&rarr;/g, "->")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

  const greeting = input.greeting;
  const body = stripTags(input.bodyHtml);
  const reply = input.replyPrompt ? "\n\n" + stripTags(input.replyPrompt) : "";

  let offerBlock = "";
  if (input.offer) {
    offerBlock = `\n\n${input.offer.eyebrow}\n${input.offer.originalPriceLabel} → ${input.offer.discountedPriceLabel}\n${input.offer.fineprint}\n\n${input.offer.ctaText}: ${input.offer.ctaUrl}`;
  }

  return [
    greeting,
    "",
    body,
    offerBlock,
    reply,
    "",
    "— Vignesh",
    "Founder, Igloo",
    "",
    "---",
    `igloo.video · ${input.demoUrl ?? DEFAULT_DEMO_URL}`,
    `YouTube: ${YT_CHANNEL}`,
    `Instagram: ${IG_PROFILE}`,
    "",
    FOOTER_ADDRESS,
    "",
    "You're getting this because you signed up at igloo.video.",
    `Unsubscribe: ${input.unsubscribeUrl}`,
  ]
    .join("\n")
    .replace(/\n{3,}/g, "\n\n");
}
