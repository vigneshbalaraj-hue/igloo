# Session 13 Integration Guide — Legal Pages + Pricing Update

> **Purpose:** Step-by-step guide for a developer pulling Session 13 changes into their working directory. Covers what changed, what to verify, and how to confirm nothing broke.

---

## What This Session Did

1. **Converted 4 static HTML policy pages to Next.js routes** — Privacy, Terms, Refund, Contact moved from `public/*.html` to `(marketing)/*/page.tsx` Server Components.
2. **Matched legal page design to the landing page** — Same Inter font, `#050505` background, `#d4a574` amber accent, mesh gradient, noise overlay, glass Navbar.
3. **Updated pricing display** — Bundle-first psychology: `$14.99 for 2 videos` (hero number) with `$9.99 for one` as the anchor/decoy. "Save 25%" eyebrow badge.
4. **Added public routes to Clerk middleware** — `/privacy`, `/terms`, `/refund`, `/contact` added to `proxy.ts` `isPublicRoute` matcher.

---

## Files Changed (Exact List)

### Created (6 files)
| File | Type | Purpose |
|------|------|---------|
| `src/app/(marketing)/layout.tsx` | Server Component | Shared layout: Navbar + mesh gradient + noise + policy wrapper + inline footer (no anchor links) |
| `src/app/(marketing)/privacy/page.tsx` | Server Component | Privacy policy at `/privacy` |
| `src/app/(marketing)/terms/page.tsx` | Server Component | Terms of service at `/terms` |
| `src/app/(marketing)/refund/page.tsx` | Server Component | Refund policy at `/refund` |
| `src/app/(marketing)/contact/page.tsx` | Server Component | Contact page at `/contact` |

### Modified (4 files)
| File | What Changed | Lines Affected |
|------|-------------|----------------|
| `src/app/globals.css` | Added `.policy-content` scoped CSS block (lines 274–362) | Appended at end, no existing lines modified |
| `src/components/Footer.tsx` | Links changed: `/privacy.html` → `/privacy`, etc. | Lines 28–31 (4 href values only) |
| `src/proxy.ts` | Added 4 routes to `isPublicRoute` array | Lines 8–11 (inserted, no existing lines modified) |
| `src/components/Hero.tsx` | Pricing text: "2 videos for $14.99 · or $9.99 each" | Line 89–91 |
| `src/components/Pricing.tsx` | Bundle-first layout: $14.99 hero, "Save 25%" badge, "$9.99 for one" anchor | Lines 125–136 |

### Deleted (5 files)
| File | Reason |
|------|--------|
| `public/privacy.html` | Replaced by Next.js route |
| `public/terms.html` | Replaced by Next.js route |
| `public/refund.html` | Replaced by Next.js route |
| `public/contact.html` | Replaced by Next.js route |
| `public/policy.css` | Old stylesheet, no longer needed |

### NOT Modified (confirmed)
| File | Status |
|------|--------|
| `layout.tsx` | Untouched — ClerkProvider, fonts, body classes intact |
| `page.tsx` | Untouched — landing page structure intact |
| `lib/*` | Untouched — Supabase, Razorpay, admin, payment logic |
| `api/**` | Untouched — all 6 API routes |
| `create/page.tsx` | Untouched — Razorpay checkout flow |
| `runs/[id]/page.tsx` | Untouched — polling + download |
| `admin/**` | Untouched — review queue |
| `sign-in/`, `sign-up/` | Untouched — Clerk catch-all routes |
| `package.json` | Untouched — zero new dependencies |
| `next.config.ts`, `tsconfig.json` | Untouched — build config |

---

## Integration Steps

### 1. Pull the changes
```bash
git pull origin landing-redesign
```

### 2. Verify proxy.ts
Open `src/proxy.ts` and confirm lines 8–11 contain:
```ts
"/privacy",
"/terms",
"/refund",
"/contact",
```
These routes MUST be in `isPublicRoute` or visitors will be redirected to sign-in.

### 3. Verify no route conflicts
```bash
ls src/app/ | grep -E "privacy|terms|refund|contact"
```
Should return nothing at the top level. The routes live inside `(marketing)/` route group.

### 4. Build check
```bash
cd app
./node_modules/.bin/tsc --noEmit   # Must pass with 0 errors
npm run build                       # Must succeed, all 4 routes should appear as static
```

Expected build output should include:
```
├ ○ /contact
├ ○ /privacy
├ ○ /refund
└ ○ /terms
```

### 5. Manual verification
Start dev server (`npm run dev`) and check:

| URL | Expected |
|-----|----------|
| `http://localhost:3000/` | Landing page renders, footer links point to `/privacy`, `/terms`, `/refund`, `/contact` |
| `http://localhost:3000/privacy` | Privacy policy with landing page design (Navbar, mesh gradient, amber accent) |
| `http://localhost:3000/terms` | Terms page, link to `/refund` in sections 5 and 8 works |
| `http://localhost:3000/refund` | Refund page, callout box visible, link to `/terms` works |
| `http://localhost:3000/contact` | Contact page, callout box with email, links to `/refund` and `/privacy` work |
| `http://localhost:3000/create` | Unchanged — Razorpay checkout flow still works |
| `http://localhost:3000/admin` | Unchanged — requires auth, review queue intact |

### 6. Auth verification
- **Signed out:** All 4 legal pages load without redirect. Landing page CTA shows "Get started" → `/sign-up`.
- **Signed in:** All 4 legal pages still load. Landing page CTA shows "Create a video" → `/create`.

---

## What Could Go Wrong (and How to Fix It)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Legal pages redirect to sign-in | `proxy.ts` missing the 4 public routes | Add `/privacy`, `/terms`, `/refund`, `/contact` to `isPublicRoute` array |
| Legal pages show unstyled content | `globals.css` missing `.policy-content` block | Verify lines 274–362 in `globals.css` |
| Footer links 404 | Old `.html` links still in Footer.tsx | Change hrefs to `/privacy`, `/terms`, `/refund`, `/contact` |
| Old `.html` pages still accessible | Static HTML files not deleted from `public/` | Delete `public/privacy.html`, `terms.html`, `refund.html`, `contact.html`, `policy.css` |
| CSS leaks to other pages | `.policy-content` rules not scoped | All rules use `.policy-content` descendant selectors — verify no bare `h1`, `h2`, `p` rules were added |
| Route conflict | Top-level `/privacy` folder in `src/app/` | Legal pages must be inside `(marketing)/` route group only |

---

## Pricing Change Summary

| Location | Before | After |
|----------|--------|-------|
| Hero (line 89–91) | "First video for $14.99 ~~$19.99~~" | "2 videos for **$14.99** · or $9.99 each" |
| Pricing card (lines 125–136) | $14.99 big / ~~$19.99~~ strikethrough | "Save 25%" badge → $14.99 big "for 2 videos" → "or $9.99 for one" small |

**Psychology:** Bundle ($14.99/2) is the hero number. Single ($9.99) serves as anchor/decoy making the bundle feel like a steal ($7.50/video vs $9.99). "Save 25%" badge makes the math instant.

**Backend note:** `lib/razorpay.ts` still has `REEL_PRICE_PAISE = 42000` (INR). This file is off-limits per LANDING_AGENT.md. The developer/human must update backend pricing separately when ready.
