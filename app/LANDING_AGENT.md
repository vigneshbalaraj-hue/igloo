# Landing Page Agent Brief — Igloo

> **READ THIS FIRST.** This file is the contract for any AI agent (Claude Code, Cursor, etc.) working on the Igloo landing page. The rest of the repo is being actively developed in parallel for a production deployment. Breaking any of the rules below will cause merge conflicts, broken auth, broken payments, or a failed deploy. **When in doubt, ask the human before touching anything outside the allowed zone.**

---

## 0. Context in one paragraph

Igloo is an AI short-form-video product. Customers pay ₹420, type a topic, and get a finished reel overnight. The repo has two halves: (1) a Python pipeline in `execution/` + `infra/modal/` that actually makes the videos, and (2) a Next.js 16 web app in `app/` that handles sign-up, payment, admin review, and download. **Your job is ONLY the marketing/landing page inside `app/`.** Everything else is off-limits.

---

## 1. Your scope — what you ARE allowed to touch

You may freely create, edit, and delete files inside these paths:

- `app/src/app/page.tsx` — the current landing page (rewrite as you like)
- `app/src/app/globals.css` — design tokens, base styles, Tailwind `@theme` block
- `app/src/components/**` — **create this directory.** Put all new reusable landing components here (`Hero.tsx`, `Features.tsx`, `Pricing.tsx`, etc.)
- `app/src/app/(marketing)/**` — optional: if you want a marketing route group (e.g. `/about`, `/pricing`, `/how-it-works`), create it here. **Do not create top-level routes that collide with existing ones** (see section 2).
- `app/public/**` — images, fonts, videos, favicons for the landing page
- `app/src/app/layout.tsx` — **limited edits only:** you may change fonts, `<head>` metadata, and body className. You may **NOT** remove `<ClerkProvider>` or change its position in the tree.

That's it. If a task seems to require editing anything else, **stop and ask the human.**

---

## 2. Hard boundaries — what you MUST NOT touch

These paths are owned by the production deployment work happening in parallel. Touching them will cause merge conflicts with the main branch:

| Path | Why it's off-limits |
|---|---|
| `app/src/app/api/**` | Razorpay, Clerk webhooks, Modal trigger, admin actions, download routes. Payment-critical. |
| `app/src/app/admin/**` | Internal admin review queue. Auth-gated. |
| `app/src/app/create/**` | Logged-in reel creation flow. Wired to Razorpay Checkout. |
| `app/src/app/runs/**` | Run status polling + download UI. Uses Clerk JWT + Supabase RLS. |
| `app/src/app/sign-in/**`, `app/src/app/sign-up/**` | Clerk catch-all routes. Do not rename, move, or delete. |
| `app/src/lib/**` | Shared server/client libraries (Supabase clients, Razorpay SDK, admin auth, payment processing). |
| `app/src/proxy.ts` | Clerk middleware. **Note:** this file is `proxy.ts`, NOT `middleware.ts`. Next 16 renamed it. Leave it alone. |
| `app/package.json`, `app/package-lock.json` | Do not add, remove, or upgrade dependencies without asking. See section 6. |
| `app/next.config.ts`, `app/tsconfig.json`, `app/eslint.config.mjs`, `app/postcss.config.mjs` | Build config. Do not touch. |
| `app/.env.local`, `app/.env.local.example` | Environment vars. Do not commit `.env.local`. Do not edit the example. |
| **Everything outside `app/`** — `execution/`, `infra/`, `directives/`, `landing/` (the old Frameforge landing page), root-level files. | Not your concern. Don't read them, don't edit them, don't delete them. |

**If ESLint, TypeScript, or the build fails because of a file in the off-limits list, do NOT fix it by editing that file. Report it to the human.**

---

## 3. Contracts you must preserve

These are the seams between your landing page and the rest of the live app. The production deployment depends on these exact behaviors:

### 3.1 CTA routes (sacred)
The landing page's call-to-action buttons must link to these paths and no others:

- **Signed-out user wants to start:** `/sign-up`
- **Signed-out user returning:** `/sign-in`
- **Signed-in user wants to buy a reel:** `/create`

You may style these buttons however you want, put them anywhere, make them look like anything — but the `href` values must match exactly. Do **not** build your own sign-up form. Do **not** link to `/register`, `/login`, `/dashboard`, or anything else. Clerk owns sign-in/sign-up; the app owns `/create`.

### 3.2 Clerk auth-aware UI
If you want to show different CTAs for signed-in vs signed-out visitors, use Clerk 7's `<Show>` component:

```tsx
import { Show } from "@clerk/nextjs";

<Show when="signed-out">
  <Link href="/sign-up">Get started</Link>
</Show>

<Show when="signed-in">
  <Link href="/create">Create a reel</Link>
</Show>
```

**Do NOT use `<SignedIn>` / `<SignedOut>`** — those were removed in Clerk 7. They will build but not render correctly.

### 3.3 ClerkProvider must stay in `layout.tsx`
The root layout wraps everything in `<ClerkProvider>`. This is required for auth to work anywhere in the app. You may restyle `<body>` and `<html>` freely, change fonts, change metadata — but do not remove, replace, or move the `<ClerkProvider>` wrapper.

### 3.4 No hardcoded `body { background }` in `globals.css`
The original `create-next-app` template hardcoded a light-mode body background via `@media (prefers-color-scheme: light)`. This was already removed once because it broke the dark-mode chrome across the rest of the app. If you re-introduce it, the admin page, the create page, and the runs page will all turn white-on-white. Use Tailwind `@theme` CSS vars or body classNames instead.

---

## 4. Brand rules

- **Product name:** Igloo (not Frameforge — that was an older name. Ignore anything in the repo that says Frameforge, especially the `landing/` folder at the repo root which is dead code.)
- **Tagline:** "Video that stops thumbs."
- **One-liner:** "Type a topic, get a finished reel overnight."
- **Price point:** ₹420 per reel (one-time, not subscription).
- **Delivery promise:** overnight / next-morning. Not real-time, not instant.
- **Tone:** confident, minimal, slightly cinematic. Not corporate. Not "AI-powered solution" speak.
- **Voice:** second person ("you type, we deliver"), active, short sentences.
- **Color:** dark-first. The current theme is near-black background with white/neutral text. You may propose a different palette, but run it by the human before committing.

---

## 5. Tech stack facts (so you don't waste time guessing)

- **Framework:** Next.js **16.2.2** (App Router). Server components by default.
- **React:** **19**. New hooks like `use()` are available.
- **Styling:** Tailwind **v4** (NOT v3). Config lives in `globals.css` via `@theme { ... }`, there is no `tailwind.config.js`. If you're used to Tailwind 3, read the v4 migration docs before editing `globals.css`.
- **TypeScript:** strict mode on.
- **Auth:** Clerk 7 (already wired). You do not need to configure anything.
- **Fonts:** Geist Sans + Geist Mono via `next/font/google`. You may swap these.
- **Animation libraries:** none installed. If you want GSAP, framer-motion, or Lenis, **ask before adding.** See section 6.
- **Middleware file is `src/proxy.ts`**, not `middleware.ts`. Next 16 renamed it. Do not create a `middleware.ts`; it will be ignored and you'll waste an hour debugging.
- **Client components need `"use client"`** at the very top of the file. Anything with hooks, event handlers, or browser-only APIs (GSAP, window, etc.) is a client component.

---

## 6. Dependencies

**Do not run `npm install <anything>` without asking the human first.** Landing pages tend to accumulate heavy dependencies (animation libs, icon packs, UI kits, analytics). Every one of these ships to the client and slows the site.

If you want a new dependency, ask the human and state:
1. What you want to install
2. Why a lighter alternative (CSS, SVG, plain React) won't work
3. The bundle size impact (check bundlephobia)

Pre-approved lightweight additions (you may install these without asking):
- `lucide-react` — icons
- `clsx` or `classnames` — conditional classnames

Everything else: ask first.

---

## 7. Running the app locally

```bash
cd app
cp .env.local.example .env.local
# You only need the Clerk publishable key for landing page work.
# Leave Supabase, Razorpay, and Modal values as placeholders.
npm install
npm run dev
```

The app will run at `http://localhost:3000`. The landing page is at `/`. You can click "Sign in" / "Sign up" to test that your CTAs hit Clerk correctly (Clerk test mode, no real accounts needed).

**Do NOT click through to `/create` or `/runs/[id]`** — those need real Supabase + Razorpay keys and will error out. That's expected; it's not a bug you need to fix.

### Type checking
Use the local tsc binary, not npx:
```bash
./node_modules/.bin/tsc --noEmit
```
`npx tsc` grabs the wrong package (an unrelated `tsc@2`). This is a known gotcha.

### Build check before committing
```bash
npm run build
```
If this fails, fix it before committing. If it fails in a file you're not allowed to touch (see section 2), stop and ask the human.

---

## 8. Git workflow

1. **Work on a dedicated branch**, never directly on `main`:
   ```bash
   git checkout -b landing-redesign
   ```
2. Commit often with clear messages. Conventional prefixes welcome: `feat(landing): add hero section`, `style(landing): update tagline typography`.
3. **Never force-push.** Never `git reset --hard` on shared branches. Never amend commits you've already pushed.
4. **Do not merge to `main` yourself.** Open a pull request and let the human review + merge.
5. Before pushing, run:
   ```bash
   cd app && npm run build && ./node_modules/.bin/tsc --noEmit
   ```
   Both must pass.

---

## 9. What "done" looks like for the landing page

A landing page ships when all of these are true:

- [ ] `/` renders without errors on desktop, tablet, mobile (test at 375px, 768px, 1440px)
- [ ] Signed-out CTAs link to `/sign-up` and `/sign-in`; signed-in CTA links to `/create`
- [ ] `npm run build` succeeds with zero errors and zero new warnings
- [ ] `./node_modules/.bin/tsc --noEmit` is clean
- [ ] No new dependencies added without human approval
- [ ] No files touched outside the allowed zone in section 1
- [ ] Clerk `<Show>` gates work: sign out and sign in to verify both states render
- [ ] Dark-first theme respected (no white flash, no hardcoded body background)
- [ ] Page weight < 500KB on first load (check `npm run build` output)
- [ ] Lighthouse performance score > 90 on mobile (optional but strongly encouraged)

---

## 10. When to stop and ask

Stop working and ask the human if any of these happen:

- A task seems to require editing a file outside section 1's allowed list
- You want to add a dependency not in section 6's pre-approved list
- The build breaks in an off-limits file
- You find a bug outside the landing page (write it down, don't fix it)
- The design brief conflicts with a rule in this document
- You're unsure whether a change would conflict with production deployment work
- You want to change brand rules (tagline, price, color, tone)

**Asking is cheap. Merge conflicts with production deploy work are expensive.**

---

## 11. Things that will get you in trouble

In decreasing order of severity:

1. **Committing `.env.local`** — contains real API keys. It's gitignored. Don't force-add it.
2. **Editing anything in `app/src/app/api/**`** — will cause merge conflict with payment/webhook work in progress.
3. **Renaming or deleting `sign-in`, `sign-up`, `create`, `runs`, `admin` routes** — will break the live app.
4. **Removing `<ClerkProvider>` from `layout.tsx`** — will break auth across the entire app.
5. **Creating a file called `middleware.ts`** — Next 16 uses `proxy.ts`. You'll think your middleware is running when it isn't.
6. **Running `npm install` with version bumps** — lockfile churn causes merge conflicts and sometimes breaks the build.
7. **Using `<SignedIn>` / `<SignedOut>`** — Clerk 7 removed these. Use `<Show when="signed-in">`.
8. **Hardcoding a light-mode body background** — will break dark theme across the rest of the app.
9. **Merging to `main` yourself** — always go through a PR.
10. **"Cleaning up" unrelated files** — not your scope. Leave them alone.

---

## 12. TL;DR

- You own `app/src/app/page.tsx`, `app/src/components/**`, `app/src/app/globals.css`, and `app/public/**`.
- CTAs must link to `/sign-up`, `/sign-in`, `/create`. Exact paths.
- Use Clerk 7's `<Show>`, not `<SignedIn>`.
- Tailwind v4, Next 16, React 19. `proxy.ts` not `middleware.ts`.
- No new dependencies without asking.
- Work on a branch. Open a PR. Don't merge to main yourself.
- When in doubt: **stop and ask the human.**
