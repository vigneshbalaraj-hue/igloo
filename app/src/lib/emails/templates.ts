// All seven drip-email templates as functions returning { subject, html, text }.
// Each takes the user's first name + a per-user unsubscribe URL.
// Copy is first-draft and meant to be reviewed; tone follows the
// anti-AI-writing directive (concrete, conversational, no marketing voice).

import "server-only";
import { renderShell, renderPlaintext, type ShellInput, type OfferCard } from "./shell";

export type EmailType =
  | "winback_d0"
  | "winback_d3"
  | "winback_d7"
  | "welcome_t0"
  | "onboard_t1"
  | "onboard_t3"
  | "onboard_t7";

export type RenderedEmail = {
  subject: string;
  html: string;
  text: string;
};

export type TemplateInput = {
  firstName: string;
  unsubscribeUrl: string;
};

const APP_URL = "https://igloo.video";
const CREATE_URL_PLAIN = `${APP_URL}/create`;
const CREATE_URL_IGLOO50 = `${APP_URL}/create?promo=IGLOO50`;
const CREATE_URL_WELCOME25 = `${APP_URL}/create?promo=WELCOME25`;

const IGLOO50_OFFER: OfferCard = {
  code: "IGLOO50",
  discountPct: 50,
  originalPriceLabel: "&#8377;999",
  discountedPriceLabel: "&#8377;499",
  ctaText: "Make my reel",
  ctaUrl: CREATE_URL_IGLOO50,
  eyebrow: "Your reel, half off",
  fineprint:
    "Code <strong style=\"color:#d4a574;font-family:monospace;\">IGLOO50</strong> &middot; expires in 14 days &middot; first reel only",
};

const WELCOME25_OFFER: OfferCard = {
  code: "WELCOME25",
  discountPct: 25,
  originalPriceLabel: "&#8377;999",
  discountedPriceLabel: "&#8377;749",
  ctaText: "Make my reel",
  ctaUrl: CREATE_URL_WELCOME25,
  eyebrow: "25% off your first reel",
  fineprint:
    "Code <strong style=\"color:#d4a574;font-family:monospace;\">WELCOME25</strong> &middot; expires in 7 days &middot; first reel only",
};

function build(input: ShellInput, subject: string): RenderedEmail {
  return {
    subject,
    html: renderShell(input),
    text: renderPlaintext(input),
  };
}

// ============================================================
// WIN-BACK DRIP — for the existing 60 signups (D+0, D+3, D+7)
// All three carry the IGLOO50 50%-off code.
// ============================================================

/** D+0 — first contact. Same copy as the original Phase 1 win-back. */
export function winbackD0({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      You signed up for Igloo a few days ago, then didn&rsquo;t come back. I&rsquo;m curious what stopped you &mdash; and I&rsquo;d like to make it easy to find out.
    </p>
    <p style="margin: 0 0 16px 0;">
      Quick refresher: you give Igloo a topic, we make you a 50-second narrated reel &mdash; voiceover, b-roll, captions, music, all of it. Like a tiny documentary, on whatever you&rsquo;re curious about.
    </p>
    <p style="margin: 0 0 16px 0;">
      Here&rsquo;s a 90-second walkthrough so you can see what you&rsquo;d actually get:
    </p>`;
  const replyPrompt = `If the offer isn&rsquo;t the thing &mdash; if you signed up and got stuck on what to make, or the wizard felt off, or you just got busy &mdash; <strong>tell me</strong>. Just hit reply. I read every one and I&rsquo;m the one building this.`;

  return build(
    {
      preheader: "A reel for you, on me. 50% off your first one — code IGLOO50.",
      heroHeadline: "A reel for you,<br />on me.",
      greeting,
      bodyHtml,
      offer: IGLOO50_OFFER,
      replyPrompt,
      unsubscribeUrl,
    },
    "A reel for you, on me — 50% off"
  );
}

/** D+3 — three days later, lighter touch but same offer. */
export function winbackD3({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      Three days ago I sent you a code for 50% off your first Igloo reel. The code is still good &mdash; <strong style="color:#d4a574;font-family:monospace;">IGLOO50</strong> &mdash; in case the first email got buried.
    </p>
    <p style="margin: 0 0 16px 0;">
      No pressure. But two minutes is all it takes to pick a topic, and you&rsquo;ll have a finished reel in your hands the next day. If something specific is in your way, hit reply &mdash; I&rsquo;d genuinely like to know.
    </p>`;
  const replyPrompt = `What&rsquo;s the one thing standing in your way?`;

  return build(
    {
      preheader: "Your IGLOO50 code is still active — 50% off your first reel.",
      heroHeadline: "Still good,<br />still 50% off.",
      greeting,
      bodyHtml,
      offer: IGLOO50_OFFER,
      replyPrompt,
      unsubscribeUrl,
    },
    "Your 50% off code is still good"
  );
}

/** D+7 — last chance, 7 days into a 14-day window. */
export function winbackD7({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      Final note from me on the 50%-off code. <strong style="color:#d4a574;font-family:monospace;">IGLOO50</strong> expires in a week &mdash; after that I&rsquo;ll stop pinging you about it.
    </p>
    <p style="margin: 0 0 16px 0;">
      If Igloo isn&rsquo;t for you, that&rsquo;s totally fine. If you were curious but never quite got around to trying it, this is the moment. The reel takes 2 minutes of your time and you have it the next day for &#8377;499 instead of &#8377;999.
    </p>`;
  const replyPrompt = `If you tried and something broke, or you have questions about whether your topic would even work &mdash; <strong>reply</strong>. I&rsquo;ll personally answer.`;

  return build(
    {
      preheader: "IGLOO50 expires in 7 days — last chance for half off.",
      heroHeadline: "Last week<br />for IGLOO50.",
      greeting,
      bodyHtml,
      offer: IGLOO50_OFFER,
      replyPrompt,
      unsubscribeUrl,
    },
    "Last chance — IGLOO50 expires in a week"
  );
}

// ============================================================
// ONBOARDING DRIP — for new signups going forward (T+0, T+1, T+3, T+7)
// T+0/T+1/T+3 = full price. T+7 = WELCOME25 25%-off.
// ============================================================

/** T+0 — fires immediately on Clerk user.created. Welcome, no offer. */
export function welcomeT0({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const welcomeDemoUrl = "https://www.youtube.com/shorts/u2-h6ZStHBE";
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      Welcome to Igloo. I&rsquo;m Vignesh &mdash; I built this thing.
    </p>
    <p style="margin: 0 0 16px 0;">
      You give Igloo a topic. We make you a 50-second narrated reel &mdash; voiceover, b-roll, captions, music. Like a tiny documentary on whatever you&rsquo;re curious about.
    </p>
    <p style="margin: 0 0 16px 0;">
      90 seconds of what that looks like:
    </p>
    <p style="margin: 0 0 16px 0;">
      <a href="${welcomeDemoUrl}" style="color:#d4a574;text-decoration:underline;">Watch a finished reel &rarr;</a>
    </p>
    <p style="margin: 0 0 16px 0;">
      Ready to make yours? Pick a topic and we&rsquo;ll have it back in 24 hours.
    </p>
    <p style="margin: 0 0 16px 0;">
      <a href="${CREATE_URL_PLAIN}" style="display:inline-block;padding:14px 28px;background:#d4a574;color:#050505;text-decoration:none;border-radius:6px;font-weight:600;">Start your first reel &rarr;</a>
    </p>`;
  const replyPrompt = `Stuck on what topic? Reply with what you&rsquo;re into and I&rsquo;ll suggest a few angles.`;

  return build(
    {
      preheader: "Welcome to Igloo. Here's how to make your first reel.",
      heroHeadline: "Welcome<br />to Igloo.",
      greeting,
      bodyHtml,
      replyPrompt,
      demoUrl: welcomeDemoUrl,
      unsubscribeUrl,
    },
    "Welcome to Igloo — here's how it works"
  );
}

/** T+1 — day after signup, only fires if user hasn't created any run yet. */
export function onboardT1({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      You signed up yesterday but haven&rsquo;t made a reel yet. The most common reason people stall? They&rsquo;re trying to pick the &ldquo;perfect&rdquo; topic.
    </p>
    <p style="margin: 0 0 16px 0;">
      Don&rsquo;t. Just pick something you find interesting and click go. The first one is the experiment &mdash; you&rsquo;ll know in 24 hours if Igloo is for you.
    </p>
    <p style="margin: 0 0 16px 0;">
      Some prompts that worked great recently:
    </p>
    <ul style="margin: 0 0 16px 0; padding-left: 20px; color:#ededed;">
      <li style="margin-bottom: 6px;">&ldquo;What actually happens during a Formula 1 pit stop&rdquo;</li>
      <li style="margin-bottom: 6px;">&ldquo;Why we can&rsquo;t remember being babies&rdquo;</li>
      <li style="margin-bottom: 6px;">&ldquo;How Mumbai&rsquo;s dabbawalas never lose a lunchbox&rdquo;</li>
    </ul>
    <p style="margin: 0 0 16px 0;">
      <a href="${CREATE_URL_PLAIN}" style="display:inline-block;padding:14px 28px;background:#d4a574;color:#050505;text-decoration:none;border-radius:6px;font-weight:600;">Pick a topic &rarr;</a>
    </p>`;
  const replyPrompt = `If you&rsquo;re second-guessing your topic, just reply with it &mdash; I&rsquo;ll tell you whether it&rsquo;ll work.`;

  return build(
    {
      preheader: "Don't overthink the first one. Just pick a topic.",
      heroHeadline: "The hardest part<br />is picking.",
      greeting,
      bodyHtml,
      replyPrompt,
      unsubscribeUrl,
    },
    "Don't overthink your first reel"
  );
}

/** T+3 — three days post-signup, still no payment. */
export function onboardT3({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      A handful of people made their first Igloo reel this week. A few of the topics they picked:
    </p>
    <ul style="margin: 0 0 16px 0; padding-left: 20px; color:#ededed;">
      <li style="margin-bottom: 6px;">&ldquo;Why your savings habit might be making you poorer&rdquo;</li>
      <li style="margin-bottom: 6px;">&ldquo;Penguins talking about global warming&rdquo;</li>
      <li style="margin-bottom: 6px;">&ldquo;Gray whales in San Francisco Bay&rdquo;</li>
    </ul>
    <p style="margin: 0 0 16px 0;">
      Each one is 50 seconds, narrated, with custom b-roll and captions. The point isn&rsquo;t the topic &mdash; it&rsquo;s that whatever caught your eye when you signed up is probably worth a reel.
    </p>
    <p style="margin: 0 0 16px 0;">
      Two clicks to start:
    </p>
    <p style="margin: 0 0 16px 0;">
      <a href="${CREATE_URL_PLAIN}" style="display:inline-block;padding:14px 28px;background:#d4a574;color:#050505;text-decoration:none;border-radius:6px;font-weight:600;">Make a reel &rarr;</a>
    </p>`;
  const replyPrompt = `What were you curious about when you signed up?`;

  return build(
    {
      preheader: "Three reels people made this week — and yours is next.",
      heroHeadline: "What others<br />are making.",
      greeting,
      bodyHtml,
      replyPrompt,
      unsubscribeUrl,
    },
    "What others are making this week on Igloo"
  );
}

/** T+7 — final email, includes WELCOME25 25%-off code. */
export function onboardT7({ firstName, unsubscribeUrl }: TemplateInput): RenderedEmail {
  const greeting = `Hey ${firstName},`;
  const bodyHtml = `
    <p style="margin: 0 0 16px 0;">
      It&rsquo;s been a week. You haven&rsquo;t tried Igloo yet, and I get it &mdash; new tools are easy to put off.
    </p>
    <p style="margin: 0 0 16px 0;">
      Here&rsquo;s 25% off your first reel to make it easier. Code <strong style="color:#d4a574;font-family:monospace;">WELCOME25</strong>, good for 7 days. After that I won&rsquo;t keep emailing you about this.
    </p>`;
  const replyPrompt = `If you decide Igloo isn&rsquo;t for you, no hard feelings &mdash; just reply with &ldquo;not interested&rdquo; and I&rsquo;ll take you off the list. If you tried and hit a wall, reply with what happened.`;

  return build(
    {
      preheader: "Code WELCOME25 — 25% off your first reel.",
      heroHeadline: "Make it easier.<br />25% off.",
      greeting,
      bodyHtml,
      offer: WELCOME25_OFFER,
      replyPrompt,
      unsubscribeUrl,
    },
    "25% off your first Igloo reel"
  );
}

// ============================================================
// Dispatch table — keyed by EmailType.
// ============================================================
export const TEMPLATES: Record<EmailType, (input: TemplateInput) => RenderedEmail> = {
  winback_d0: winbackD0,
  winback_d3: winbackD3,
  winback_d7: winbackD7,
  welcome_t0: welcomeT0,
  onboard_t1: onboardT1,
  onboard_t3: onboardT3,
  onboard_t7: onboardT7,
};
