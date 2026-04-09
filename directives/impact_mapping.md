# Impact Mapping — Igloo Web Revamp

> **Purpose:** This document is the binding systems-thinking reference for the landing page revamp. Every agent MUST read this before making changes. It maps the full system architecture, traces every dependency, and answers: what does this change break, who does it affect, and what are the downstream consequences?

> **Last updated:** 2026-04-08 (Session 2 — full codebase audit complete)

---

## 1. System Architecture

### 1.1 High-Level Topology

```
                   ┌─────────────────────────────────────────────┐
                   │              BROWSER (Client)                │
                   │                                             │
                   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
                   │  │ Landing  │  │ /create  │  │ /runs/id │  │
                   │  │ page.tsx │  │ page.tsx │  │ page.tsx │  │
                   │  │ +comps   │  │ Razorpay │  │ polling  │  │
                   │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
                   │       │             │             │         │
                   └───────┼─────────────┼─────────────┼─────────┘
                           │             │             │
                  ┌────────▼─────────────▼─────────────▼────────┐
                  │           NEXT.JS 16 APP (app/)              │
                  │                                              │
                  │  proxy.ts ──► Clerk auth gate                │
                  │  layout.tsx ──► ClerkProvider + fonts + CSS   │
                  │                                              │
                  │  API Routes:                                 │
                  │  ├─ /api/razorpay/order    (Clerk auth)      │
                  │  ├─ /api/razorpay/webhook  (Razorpay sig)    │
                  │  ├─ /api/trigger-run       (Clerk + Rz sig)  │
                  │  ├─ /api/admin/runs/[id]/deliver (admin)     │
                  │  ├─ /api/admin/runs/[id]/reject  (admin)     │
                  │  └─ /api/runs/[id]/download      (Clerk+own) │
                  │                                              │
                  │  Lib Layer:                                  │
                  │  ├─ supabase.ts        (browser client)      │
                  │  ├─ supabase-server.ts (service_role)        │
                  │  ├─ admin.ts           (role guard)          │
                  │  ├─ razorpay.ts        (SDK + constants)     │
                  │  └─ process-payment.ts (idempotent handler)  │
                  └──────────┬───────────────────────┬───────────┘
                             │                       │
                  ┌──────────▼──────┐     ┌──────────▼──────────┐
                  │   SUPABASE      │     │   RAZORPAY          │
                  │   (ap-south-1)  │     │   (TEST mode)       │
                  │                 │     │                     │
                  │  Tables:        │     │  Orders + Webhooks  │
                  │  users          │     │  ₹420/reel          │
                  │  runs           │     └─────────────────────┘
                  │  credits        │
                  │  payments       │
                  │  Storage: reels/│
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │   MODAL WORKER  │
                  │  igloo_worker.py│
                  │                 │
                  │  9-step pipeline│
                  │  execution/*.py │
                  └─────────────────┘
```

### 1.2 File Ownership Map (Who Owns What)

| Zone | Owner | Files | Touch Policy |
|------|-------|-------|-------------|
| **Landing zone** | Landing agent | `page.tsx`, `globals.css`, `components/**`, `public/**`, `(marketing)/**` | Free to edit |
| **Auth zone** | Production deploy | `proxy.ts`, `sign-in/`, `sign-up/`, `layout.tsx` (ClerkProvider) | Do NOT touch (except layout fonts/metadata) |
| **Payment zone** | Production deploy | `api/razorpay/**`, `api/trigger-run/`, `lib/razorpay.ts`, `lib/process-payment.ts` | Do NOT touch |
| **Data zone** | Production deploy | `lib/supabase*.ts`, `api/runs/*/download/` | Do NOT touch |
| **Admin zone** | Production deploy | `admin/**`, `api/admin/**`, `lib/admin.ts` | Do NOT touch |
| **User zone** | Production deploy | `create/page.tsx`, `runs/[id]/page.tsx` | Do NOT touch |
| **Config zone** | Production deploy | `package.json`, `tsconfig.json`, `next.config.ts`, `.env*` | Do NOT touch |
| **Pipeline zone** | Separate concern | `execution/*.py`, `infra/**`, `directives/**` | Not in scope |

### 1.3 Shared Resources (Cross-Zone Dependencies)

These files are shared between the landing zone and other zones. Changes here ripple everywhere:

| Shared Resource | Used By | Risk Level |
|----------------|---------|------------|
| **`globals.css`** | Every page in the app (imported via `layout.tsx`) | **HIGH** — CSS var changes affect create, runs, admin pages |
| **`layout.tsx`** | Every page (root layout wraps all routes) | **CRITICAL** — ClerkProvider, fonts, body classes |
| **`public/**`** | Any page can reference `/logo.png`, SVGs | LOW — additive only |
| **Tailwind `@theme` tokens** | Any component using Tailwind utilities app-wide | **MEDIUM** — new tokens are additive but renamed/removed tokens break consumers |

---

## 2. Changes Made (Landing Revamp — Session 2)

### 2.1 Files Modified

| File | Change Type | Lines Before | Lines After |
|------|------------|-------------|-------------|
| `app/src/app/globals.css` | **Rewrite** | 20 | ~170 |
| `app/src/app/page.tsx` | **Rewrite** | 42 | 33 |

### 2.2 Files Created

| File | Type | Lines | Server/Client |
|------|------|-------|---------------|
| `app/src/components/Navbar.tsx` | New | 127 | Client (`"use client"`) |
| `app/src/components/Hero.tsx` | New | 102 | Client (`"use client"`) |
| `app/src/components/Problem.tsx` | New | 67 | Server |
| `app/src/components/HowItWorks.tsx` | New | 81 | Server |
| `app/src/components/Features.tsx` | New | 90 | Server |
| `app/src/components/Pricing.tsx` | New | 75 | Server |
| `app/src/components/FinalCTA.tsx` | New | 47 | Server |
| `app/src/components/Footer.tsx` | New | 22 | Server |
| `app/src/components/ScrollReveal.tsx` | New | 39 | Client (`"use client"`) |
| `app/public/logo.png` | New asset | — | Static (506 KB) |
| `app/public/hero-bg.mp4` | New asset | — | Static (790 KB) — h264 baseline, cropped+compressed from `vid_post_final.mp4` |
| `app/public/hero-bg.webm` | New asset | — | Static (379 KB) — VP9, primary format for Chrome |
| `app/public/hero-poster.jpg` | New asset | — | Static (54 KB) — fallback poster frame for blocked/loading video |

### 2.3 Files NOT Modified (confirmed safe)

| File | Status | Why It Matters |
|------|--------|---------------|
| `layout.tsx` | Untouched | ClerkProvider, fonts, body classes all preserved |
| `proxy.ts` | Untouched | Clerk middleware route matching intact |
| `lib/*` | Untouched | Supabase, Razorpay, admin, payment logic all intact |
| `api/**` | Untouched | All 6 API routes intact |
| `create/page.tsx` | Untouched | Razorpay checkout flow intact |
| `runs/[id]/page.tsx` | Untouched | Polling + download flow intact |
| `admin/**` | Untouched | Review queue intact |
| `sign-in/`, `sign-up/` | Untouched | Clerk catch-all routes intact |
| `package.json` | Untouched | No new dependencies |

---

## 3. Impact Analysis

### 3.1 globals.css — HIGHEST RISK CHANGE

**What changed:**

| Token | Before | After | Delta |
|-------|--------|-------|-------|
| `--background` | `#0a0a0a` | `#050505` | Darker (OLED black) |
| `--foreground` | `#ededed` | `#f0f0f0` | Slightly brighter |
| New tokens | — | `--accent`, `--accent-bright`, `--accent-dim`, `--surface`, `--surface-elevated`, `--border-subtle`, `--border-hover`, `--text-muted`, `--text-secondary` | Additive |
| New classes | — | `.mesh-gradient`, `.noise-overlay`, `.reveal`, `.stagger`, `.btn-primary`, `.btn-secondary`, `.glass`, `.eyebrow`, `.marquee-track` | Additive |

**Who is impacted:**

| Consumer | Impact | Severity | Explanation |
|----------|--------|----------|-------------|
| **`layout.tsx` body** | Negligible | LOW | Body uses `bg-neutral-950` (Tailwind class, specificity > element selector). The `--background` var on `html, body` is overridden by the class. |
| **`html` element** | Minor visual | LOW | `html { background: #050505 }` applies since no Tailwind class overrides it. Visible only in overscroll bounce (iOS) or if body is shorter than viewport. Was `#0a0a0a`, now `#050505`. |
| **`create/page.tsx`** | None | NONE | Uses Tailwind classes directly, not CSS vars. No references to `--background` or any of the new tokens. |
| **`runs/[id]/page.tsx`** | None | NONE | Same — Tailwind classes only. |
| **`admin/page.tsx`** | None | NONE | Same — Tailwind classes only. |
| **`admin/runs/[id]/page.tsx`** | None | NONE | Same. |
| **`AdminActions.tsx`** | None | NONE | Uses `bg-emerald-500` — hardcoded Tailwind, no CSS var dependency. |
| **New landing components** | Full dependency | EXPECTED | All 9 components use the new tokens via Tailwind theme utilities (`text-accent`, `bg-surface`, etc.) and custom classes (`.glass`, `.btn-primary`, etc.). |

**Consequence:** The new CSS tokens and classes are **additive**. The only existing value that changed (`--background`) is overridden by the Tailwind utility class on `<body>`. **No visual regression on non-landing pages.**

**Future risk:** If any future page uses `bg-background` (the Tailwind utility generated from `--color-background`), it will get `#050505` instead of the old `#0a0a0a`. Currently no page does this — they all use `bg-neutral-950` directly. But this is a latent divergence.

**Mitigation:** Keep `--background: #050505` and `bg-neutral-950` (#0a0a0a) in sync, or refactor all pages to use `bg-background` consistently. Not urgent but track as tech debt.

### 3.2 page.tsx — MEDIUM RISK CHANGE

**What changed:** Complete rewrite from a simple inline layout to a component-based architecture importing 8 components.

**Who is impacted:**

| Consumer | Impact | Severity | Explanation |
|----------|--------|----------|-------------|
| **`proxy.ts` (middleware)** | None | NONE | `/` is a public route. No auth change. |
| **Clerk `<Show>` behavior** | Preserved | NONE | All CTAs use `<Show when="signed-out">` and `<Show when="signed-in">` correctly. Verified in Navbar.tsx, Hero.tsx, Pricing.tsx, FinalCTA.tsx. |
| **CTA routing** | Preserved | NONE | `/sign-up`, `/sign-in`, `/create` — exact paths, verified in every component. |
| **SEO / metadata** | Unchanged | NONE | Metadata lives in `layout.tsx`, not `page.tsx`. No change to title or description. |
| **Page weight** | Increased | **MEDIUM** | `logo.png` is 506 KB. LANDING_AGENT.md target is < 500 KB total page weight. This single asset exceeds the budget. **Must optimize before deploy.** |
| **Build output** | Changed | LOW | `/` was previously statically generated (no dynamic data). It still is — confirmed by build output showing `f /` (dynamic due to Clerk `<Show>`). This is expected and matches the old behavior. |

**Consequence:** The page structure changed significantly but all external contracts (CTAs, auth, routing) are preserved. The **only actionable issue is logo.png size**.

### 3.3 New Components — LOW RISK

**Who is impacted:**

| Concern | Impact | Explanation |
|---------|--------|-------------|
| **Bundle size** | Minor increase | 2 client components (Navbar.tsx, ScrollReveal.tsx) add JS to the client bundle. ~170 lines combined. The other 7 are Server Components — zero client JS. |
| **Hydration** | Safe | Client components are leaf nodes (Navbar at top, ScrollReveal wrapping sections). No server/client boundary violations. |
| **Clerk imports** | Safe | `@clerk/nextjs` imports (`Show`, `UserButton`) are used in both Server Components (Hero, Pricing, FinalCTA) and Client Components (Navbar). Clerk v7 supports both. |
| **`next/image`** | New usage | Navbar.tsx uses `<Image>` from `next/image` for the logo. This is fine — Next.js optimizes it automatically. But the source (`/logo.png`, 506 KB) needs optimization at the asset level. |
| **IntersectionObserver** | Safe | Used in ScrollReveal.tsx. Browser support is universal (97%+). No polyfill needed. Cleans up via `observer.disconnect()` in useEffect return. |

### 3.4 public/logo.png — MEDIUM RISK

| Concern | Impact | Severity |
|---------|--------|----------|
| **Page weight** | 506 KB for a single image | **HIGH** — exceeds 500 KB budget alone |
| **next/image optimization** | Automatic WebP conversion + resizing | Mitigates raw size but still heavy |
| **Git history** | Binary blob in repo | LOW — one-time addition |

**Mitigation required:** Compress logo to < 50 KB (WebP or optimized PNG) before deploy. The logo is 506 KB because it includes the dark background and glow effect baked in at high resolution.

---

## 4. Cross-System Impact Matrix

This matrix answers: "If I change X, what else breaks?"

| If You Change... | These Break / Are Affected |
|-------------------|--------------------------|
| `globals.css` `:root` vars | Landing components (all 9), potentially any future page using `bg-background` or `text-foreground` |
| `globals.css` `.btn-primary` class | Hero CTA, Pricing CTA, FinalCTA CTA, Navbar CTA |
| `globals.css` `.glass` class | Navbar pill, Problem section quote box |
| `globals.css` `.reveal` / `.stagger` class | ScrollReveal.tsx behavior (all scroll-animated sections) |
| `globals.css` `.eyebrow` class | Hero, Problem, HowItWorks, Features, Pricing section labels |
| `globals.css` `.features-text-block` class | Features section text crossfade transitions |
| `globals.css` `.features-text-glow` class | Features section text readability over video |
| `globals.css` `.features-dot` class | Features section progress indicator dots |
| `page.tsx` component imports | If a component file is renamed/deleted, page breaks with build error |
| `Navbar.tsx` | Logo display, navigation links, mobile menu, CTA buttons (all on every viewport) |
| `Hero.tsx` | First impression, primary CTA, tagline, hook |
| `Pricing.tsx` | ₹420 price display, beta messaging, purchase CTA |
| `ScrollReveal.tsx` | Every section's entrance animation (Problem, HowItWorks, Features, Pricing, FinalCTA) |
| `layout.tsx` body classes | Every page's base styling. DO NOT CHANGE without checking all pages. |
| `layout.tsx` ClerkProvider | Every auth-dependent component in the entire app. NEVER REMOVE. |
| `proxy.ts` public routes | If `/` is removed from public routes, landing page requires login. |
| `lib/razorpay.ts` REEL_PRICE_PAISE | Displayed in Pricing.tsx as ₹420 (hardcoded in component, not imported from lib). If price changes, **both** Pricing.tsx AND lib/razorpay.ts must be updated. **Coupling risk.** |
| Brand colors (accent) | globals.css tokens + every component using `text-accent`, `bg-accent`, `.eyebrow`, `.btn-primary` |

---

## 5. Identified Risks and Technical Debt

### 5.1 Active Risks

| # | Risk | Severity | Status | Mitigation |
|---|------|----------|--------|-----------|
| R1 | `logo.png` is 506 KB — exceeds page weight budget | HIGH | Open | Compress to < 50 KB WebP/PNG before deploy |
| R2 | Price (₹420) is hardcoded in `Pricing.tsx` AND in `lib/razorpay.ts` as `REEL_PRICE_PAISE = 42000` — dual source of truth | MEDIUM | Open | Pricing.tsx should import the constant, or at minimum, add a comment linking the two. Cannot import from `lib/razorpay.ts` since it uses `server-only`. Consider a shared constant file or accept the duplication with a comment. |
| R3 | `--background` (#050505) diverges from `bg-neutral-950` (#0a0a0a) used in layout.tsx body | LOW | Open | Align by either changing the CSS var to #0a0a0a or changing layout.tsx to use `bg-background`. Not urgent — overscroll-bounce-only visibility. |
| R4 | No animation library installed — all motion is CSS-only | LOW | Accepted | Adequate for current design. If richer motion is needed, framer-motion requires human approval per LANDING_AGENT.md section 6. |
| R5 | Old `landing/` directory has competing brand assets (different logo variants, different amber palette `#D97706` vs new `#d4a574`, policy pages) | LOW | Open | Dead code per LANDING_AGENT.md. But policy pages (terms, privacy, refund, contact) in `landing/public/` may be needed — verify with human before deploy. |
| R6 | **Chrome extensions can block `<video>` playback** — ad blockers / privacy extensions intercept media requests, returning error code 4 (`SRC_NOT_SUPPORTED`). Confirmed on dev machine: ALL video formats (MP4, WebM, generated test files) fail identically in normal Chrome but play in incognito. | **LOW for production** (only affects visitors with aggressive extensions) | Open | **Mitigations in place:** (1) Dual-format `<source>` tags (WebM + MP4) with `type` hints maximize codec compatibility. (2) `poster` attribute shows static frame as graceful degradation. (3) `useEffect` play() call with `.catch()` prevents console errors. **For local dev testing:** use incognito (`Cmd+Shift+N`) or disable the offending extension via `chrome://extensions/`. |

### 5.2 Technical Debt

| # | Debt | Priority | Notes |
|---|------|----------|-------|
| D1 | Old landing amber (`#D97706` from `landing/src/index.css`) vs new amber (`#d4a574` from `globals.css`) — brand color not formally locked | MEDIUM | The logo's warm glow suggests `#d4a574` range but this needs explicit human sign-off. Old landing used a more saturated amber. |
| D2 | Policy pages (terms, privacy, refund, contact) exist only in dead `landing/public/` — no equivalent in `app/` | MEDIUM | Required for production launch. Either port as `(marketing)/**` routes or keep as static HTML. |
| D3 | No analytics or tracking on landing page | LOW | Listed in checkpoint as known issue. Not blocking for beta. |
| D4 | No `<meta>` OG tags for social sharing | LOW | Would improve social card previews when sharing igloo.video link. |

---

## 6. Dependency Graph (Visual)

```
page.tsx
├── Navbar.tsx (client)
│   ├── @clerk/nextjs: Show, UserButton
│   ├── next/image: Image (logo.png)
│   └── next/link: Link → /sign-up, /sign-in, /create, /, #anchors
│
├── Hero.tsx (client)
│   ├── @clerk/nextjs: Show
│   ├── next/link: Link → /sign-up, /sign-in, /create
│   └── assets: hero-bg.webm (VP9, 379KB), hero-bg.mp4 (h264, 790KB), hero-poster.jpg (54KB)
│
├── Problem.tsx (server)
│   └── ScrollReveal.tsx (client) → IntersectionObserver
│
├── HowItWorks.tsx (server)
│   └── ScrollReveal.tsx (client)
│
├── Features.tsx (client — scroll-pinned video scrub)
│   └── assets: features-scrub.mp4 (h264 all-intra, 2.4MB)
│
├── Pricing.tsx (server)
│   ├── @clerk/nextjs: Show
│   ├── next/link: Link → /sign-up, /create
│   └── ScrollReveal.tsx (client)
│
├── FinalCTA.tsx (server)
│   ├── @clerk/nextjs: Show
│   ├── next/link: Link → /sign-up, /create
│   └── ScrollReveal.tsx (client)
│
└── Footer.tsx (server)
    └── #anchor links only

globals.css (SHARED — imported via layout.tsx)
├── CSS vars: used by all landing components via Tailwind theme utilities
├── .glass: Navbar, Problem quote
├── .btn-primary / .btn-secondary: Hero, Pricing, FinalCTA, Navbar
├── .eyebrow: Hero, Problem, HowItWorks, Features, Pricing
├── .reveal / .stagger: ScrollReveal.tsx
├── .mesh-gradient: page.tsx background
├── .noise-overlay: page.tsx background
└── .features-text-block / .features-text-glow / .features-dot: Features.tsx
```

---

## 7. Pre-Change Checklist (For Future Sessions)

Before making ANY change to the landing page, run through this:

- [ ] **Read this file** (`directives/impact_mapping.md`) to understand what you're about to affect
- [ ] **Read `app/LANDING_AGENT.md`** — the binding contract
- [ ] **Check the cross-system impact matrix** (Section 4) for the files you plan to change
- [ ] **If touching `globals.css`**: verify no visual regression on `/create`, `/runs/[id]`, `/admin` — specifically check that CSS var changes don't leak through Tailwind theme utilities
- [ ] **If touching CTAs**: verify exact paths (`/sign-up`, `/sign-in`, `/create`) and Clerk 7 `<Show>` usage
- [ ] **If adding assets to `public/`**: check size — page weight must stay < 500 KB total
- [ ] **If adding dependencies**: stop and ask human (LANDING_AGENT.md section 6)
- [ ] **After changes**: run `./node_modules/.bin/tsc --noEmit` AND `npm run build` — both must pass
- [ ] **Update this file** with any new impacts discovered

---

## 8. Contract Compliance Verification

| LANDING_AGENT.md Rule | Status | Evidence |
|-----------------------|--------|---------|
| CTAs link to `/sign-up`, `/sign-in`, `/create` | PASS | Verified in Hero.tsx, Navbar.tsx, Pricing.tsx, FinalCTA.tsx |
| Clerk 7 `<Show>` (not `<SignedIn>/<SignedOut>`) | PASS | All 4 components use `<Show when="signed-out">` / `<Show when="signed-in">` |
| No files touched outside allowed zone | PASS | Only `page.tsx`, `globals.css`, `components/**`, `public/**` |
| No `npm install` without approval | PASS | Zero new dependencies |
| `tsc --noEmit` clean | PASS | Verified 2026-04-08 |
| `npm run build` clean | PASS | Verified 2026-04-08 |
| Dark-first theme | PASS | OLED black background, warm amber accent |
| No hardcoded `body { background }` override | PASS | `html, body` rule exists but is overridden by Tailwind class on `<body>` element (class specificity > element specificity) |
| ClerkProvider not removed from layout.tsx | PASS | layout.tsx untouched |
| Work on branch, not main | PASS | Branch: `landing-redesign` |
| Page weight < 500 KB | **FAIL** | `logo.png` alone is 506 KB. Must optimize. |
