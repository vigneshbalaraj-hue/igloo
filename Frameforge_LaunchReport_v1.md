# Frameforge — Launch-Today Report

> Goal: get Frameforge live on your domain with 30 paying beta users (FCFS, $5 = 1 reel) by end of day.
> Date: 2026-04-07
> Author: Claude (working session)

---

## 0. TL;DR — the day in one paragraph

You will ship **Vercel (landing) + Modal (pipeline + queue) + Clerk (auth) + Supabase (Postgres) + Razorpay Payment Links (payments)**. Each of these has a free tier or pay-as-you-go and zero long contracts. Total new code is small: a credits table, a Razorpay webhook, a Clerk-protected "Create Reel" page that calls a Modal endpoint, and a manual-review queue you watch from a private admin page. Math: 30 users × $5 (~₹420) = **~$150 revenue**, 30 reels × $3.19 cost = **$95.70 COGS**, leaving **~$54 gross margin** before fees and your time. The point of this beta is not the margin — it is to validate willingness-to-pay, harden the pipeline under real users, and collect 30 finished reels you can show in the next sales conversation.

> **Why not Stripe:** Stripe Netherlands now requires a KvK (Chamber of Commerce) registration as of 2026 — no more individual accounts. Registering an eenmanszaak takes an in-person KvK appointment (typically booked 1-2 weeks out), so Stripe is off the critical path for today. We'll migrate to Stripe later once the KvK is in place. **Razorpay is the launch-day choice** because Express Activation can put a live account in your hands within ~1 business hour if you have Indian PAN + Aadhaar + Indian bank account ready.

---

## 1. The full architecture you are launching

```
┌──────────────────────────────────────────────────────────────┐
│  yourdomain.com                                              │
│  Vercel  →  React landing page (existing landing/ folder)    │
│             "Sign up" / "Buy 1 reel for $5" CTAs             │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ Clerk handles signup/login
               ▼
┌──────────────────────────────────────────────────────────────┐
│  app.yourdomain.com                                          │
│  Vercel  →  authenticated wizard (new minimal Next.js page)  │
│             - Buy credits  →  Razorpay Payment Link          │
│             - Create reel  →  POST to Modal endpoint         │
│             - View status  →  poll Supabase                  │
│             - Download mp4 →  signed URL when approved       │
└──────────────┬───────────────────────────────────────────────┘
               │
               ├──── Razorpay webhook ──► Supabase: increment credits
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  Modal                                                       │
│  - HTTP endpoint: POST /create_reel  (decrements credit,    │
│      enqueues job, returns run_id)                           │
│  - Worker function: runs the existing run_pipeline.py        │
│      end-to-end on a Modal container (ffmpeg pre-installed). │
│  - Writes intermediates to a Modal Volume (persistent FS).   │
│  - On completion, uploads final mp4 to Supabase Storage,     │
│      flips Supabase row to status='awaiting_review'.         │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  Supabase                                                    │
│  - Postgres tables: users (mirrors Clerk), credits, runs,    │
│      assets, payments                                        │
│  - Storage bucket: reels/{user_id}/{run_id}.mp4              │
│  - Row-level security so users only see their own runs       │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  admin.yourdomain.com  (Clerk-gated, your email only)        │
│  - Lists all 'awaiting_review' reels                         │
│  - Inline mp4 player                                         │
│  - Buttons: Approve (notify user) / Reject + Regenerate      │
└──────────────────────────────────────────────────────────────┘
```

Five vendors, all free-tier-friendly, all signup-with-GitHub or signup-with-email. None lock you in.

---

## 2. Accounts you need to create today (in order, with timing)

| # | Account | Why | Time | Blocker risk |
|---|---|---|---|---|
| 1 | **Razorpay (India)** | Payments. Sole proprietor account, payouts to Indian bank. | ~1 business hour with Express Activation | Needs PAN + Aadhaar + Indian bank account + a working website with Privacy / Terms / Refund / Contact / Pricing pages live before submission. **Start this first** so KYC processes while everything else is being built. Rejected applications cost a full day, so get the policy pages right on the first submission. |
| 2 | **Vercel** | Hosts landing + app frontend. Free Hobby tier. | 2 min | None — GitHub login. |
| 3 | **Modal** | Runs the pipeline. $30 free credits on signup, then pay-per-second. | 5 min | None — GitHub login. |
| 4 | **Clerk** | Auth + user management. Free up to 10K MAU. | 5 min | None — GitHub login. |
| 5 | **Supabase** | Postgres + file storage + signed URLs. Free up to 500MB DB / 1GB storage. | 5 min | None — GitHub login. |
| 6 | **Cloudflare (optional)** | Move DNS off Namecheap for faster propagation + free SSL fallback. | 15 min | Optional. Skip if you want to keep Namecheap DNS. |
| 7 | **GitHub repo (private)** | Vercel and Modal both deploy from GitHub. Push the existing Reel_engine repo. | 5 min | If the repo isn't on GitHub yet, do this first. |

**Critical path:** Razorpay KYC + the 5 mandatory policy pages on the landing site are the only things that can block your launch. Submit Express Activation in the first 30 minutes of the day, but **only after** Privacy / Terms / Refund / Contact / Pricing pages are visible on the live domain — Razorpay reviewers will reject the application otherwise. I've drafted these as part of section 4d.

---

## 3. Domain setup (Namecheap → Vercel)

"Pointing" a domain means adding **DNS records** at the registrar that tell the world "when someone types frameforge.com, send them to this server." For Vercel, you do one of two things:

**Option A — Keep DNS at Namecheap (simplest):**
1. In Vercel, add your domain to the project. Vercel will show you 2 records to add.
2. In Namecheap → Domain List → Manage → Advanced DNS, add:
   - Type `A`, Host `@`, Value `76.76.21.21` (Vercel's apex IP)
   - Type `CNAME`, Host `www`, Value `cname.vercel-dns.com.`
   - Type `CNAME`, Host `app`, Value `cname.vercel-dns.com.`
   - Type `CNAME`, Host `admin`, Value `cname.vercel-dns.com.`
3. Wait 5–30 min for DNS propagation. SSL is automatic.

**Option B — Move DNS to Cloudflare (faster propagation, free WAF, better long-term):**
1. Sign up at Cloudflare, add your domain, copy the 2 nameservers it gives you.
2. In Namecheap → Domain List → Manage → Nameservers → Custom DNS → paste the Cloudflare ones.
3. In Cloudflare DNS, add the same records as Option A.
4. Set SSL/TLS mode to "Full (strict)" so Cloudflare doesn't double-terminate Vercel's cert.

**Recommendation: Option A for today.** Don't introduce Cloudflare on launch day. Move later.

You will need three subdomains:
- `frameforge.com` → marketing landing
- `app.frameforge.com` → the wizard (Clerk-protected)
- `admin.frameforge.com` → manual review queue (your email only)

Modal exposes its own `*.modal.run` URL — you do not need to point a subdomain at Modal; the frontend just calls it directly.

---

## 4. The minimum new code you have to write today

Your existing pipeline (`execution/run_pipeline.py` and the 9 step scripts) does not change. What you add:

### 4a. Modal wrapper (~100 lines, one file)

Create `execution/modal_app.py`:

```python
import modal

image = (
    modal.Image.debian_slim(python_version="3.14")
    .apt_install("ffmpeg")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("execution", "/app/execution")
    .add_local_dir("directives", "/app/directives")
)

app = modal.App("frameforge")
volume = modal.Volume.from_name("frameforge-tmp", create_if_missing=True)
secrets = [modal.Secret.from_name("frameforge-keys")]  # holds GEMINI/ELEVENLABS/KLING/SUPABASE keys

@app.function(image=image, volumes={"/tmp_runs": volume}, secrets=secrets, timeout=3600)
def run_reel(run_id: str, user_id: str, theme: str, topic: str):
    # 1. shell out to existing run_pipeline.py with --auto-go
    # 2. on success, upload final_reel_optionc.mp4 to Supabase Storage
    # 3. update Supabase runs row to status='awaiting_review'
    # 4. on failure, status='failed', refund credit
    ...

@app.function(image=image, secrets=secrets)
@modal.fastapi_endpoint(method="POST")
def create_reel(payload: dict):
    # 1. verify Clerk JWT in payload
    # 2. check Supabase: does this user have >=1 credit?
    # 3. decrement credit, insert runs row with status='queued'
    # 4. spawn run_reel.spawn(run_id, user_id, theme, topic)
    # 5. return {run_id}
    ...
```

That is the entire Modal layer. The existing pipeline is called as a subprocess inside `run_reel`, unmodified.

### 4b. Supabase schema (one SQL migration)

```sql
create table users (
  id text primary key,                  -- Clerk user id
  email text not null,
  created_at timestamptz default now()
);

create table credits (
  user_id text references users(id),
  balance int not null default 0,
  updated_at timestamptz default now(),
  primary key (user_id)
);

create table runs (
  id uuid primary key default gen_random_uuid(),
  user_id text references users(id),
  theme text,
  topic text,
  status text not null,                 -- queued | running | awaiting_review | delivered | failed
  cost_usd numeric,
  mp4_path text,                        -- supabase storage key
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table payments (
  id uuid primary key default gen_random_uuid(),
  user_id text references users(id),
  stripe_session_id text unique,
  amount_cents int,
  credits_added int,
  created_at timestamptz default now()
);

-- enable row level security
alter table runs enable row level security;
create policy "users see own runs" on runs for select using (user_id = auth.jwt()->>'sub');
```

### 4c. Razorpay Payment Link + webhook (one Vercel serverless function)

`api/razorpay_webhook.ts`:

```typescript
// On 'payment_link.paid':
//   - verify HMAC SHA256 signature with the webhook secret (mandatory)
//   - extract notes.user_id from the payload
//   - insert into payments (stripe_session_id column repurposed as razorpay_payment_id)
//   - upsert credits set balance = balance + 1
//   - return 200
```

A single Razorpay **Payment Link** for "1 Frameforge Reel" at ₹420 (~$5). On the `/app` page, the Buy button calls Razorpay's API to create a per-user Payment Link with `notes.user_id = <clerk_id>`, then opens it in a new tab. No checkout UI to build today — Razorpay's hosted page handles cards, UPI, netbanking, and wallets out of the box.

> **Currency note:** Razorpay merchant accounts settle in INR. International cards are accepted; the buyer is shown the equivalent in their local currency at checkout. Price the link in INR (₹420) so Indian buyers don't see FX surprises and so payouts land cleanly in your Indian bank account.

### 4d. Frontend (Next.js, ~3 small pages on Vercel)

- `/` — your existing landing page (move it from Vite to a Next.js `pages/` route, or keep Vite and host it on a separate Vercel project; either works).
- `/app` (Clerk-protected) — credit balance, "Buy 1 reel" button (→ Razorpay Payment Link), "Create reel" form (theme + topic), list of past runs with status badges and download buttons.
- `/privacy`, `/terms`, `/refund`, `/contact`, `/pricing` — five static pages required by Razorpay KYC. ~50 lines each, plain prose. I'll draft these.
- `/admin` (Clerk role-gated to your email only) — list of `awaiting_review` runs, mp4 player, Approve / Reject buttons.

Total new code: roughly **400-600 lines** across Modal wrapper, Stripe webhook, schema, and three thin pages. Everything else is the existing pipeline, untouched.

---

## 5. Hour-by-hour plan for today

| Hour | What | Who/What |
|---|---|---|
| **H+0** | Create Vercel, Modal, Clerk, Supabase, GitHub-private accounts. Push `Reel_engine` repo to private GitHub. | You |
| **H+1** | Wire DNS at Namecheap (3 records: apex, www, app). Start the propagation clock immediately. | You |
| H+1 | Draft + deploy the 5 mandatory policy pages (Privacy, Terms, Refund, Contact, Pricing) on the apex domain. They MUST be live before Razorpay KYC. | Claude |
| **H+2** | **Submit Razorpay Express Activation** with PAN, Aadhaar, bank, and the live website URL. | You |
| H+2 | Run Supabase SQL migration (4b). Create Storage bucket `reels` with private access. | You |
| **H+3** | Write `execution/modal_app.py` (4a). `modal deploy`. Smoke-test with one cheap reel via `run_reel.local()`. | You + Claude |
| **H+4** | Scaffold Next.js app. Wire Clerk. Deploy to Vercel. Implement `/app` page (balance + create form + run list). | Claude |
| **H+5** | Razorpay activation should be done by now. Create the ₹420 Payment Link. Copy webhook secret. | You |
| H+5 | Implement Razorpay webhook serverless function on Vercel. Test by triggering a real ₹420 payment with your own card. | Claude |
| **H+6** | Implement `/admin` review queue. Hardcode allowed email. | Claude |
| **H+7** | End-to-end test #1: signup → buy 1 credit → submit topic → wait ~40 min → review → approve → user downloads. **Use a real ₹420 charge with your own card.** | You |
| **H+8** | Fix whatever broke. Run a second end-to-end test with a different topic. | You |
| **H+9** | Cap at 30 signups via a Supabase trigger that disables the Payment Link after the 30th payment. | Claude |
| **H+10** | Soft-launch announcement to your first list. | You |

**If Razorpay KYC stalls past H+5:** the manual fallback is to publish the Razorpay Payment Link's URL by hand once it's ready, and grant credits to the first 30 buyers via a SQL update in Supabase. The webhook can be wired in the morning. The pipeline still works without a fully automated billing loop on day one.

**If Razorpay KYC is rejected:** drop to **LemonSqueezy** (~1 hour, no PAN/no KvK, merchant of record). All other infra stays the same — only the webhook handler and the buy button URL change. Budget half a day for the migration.

---

## 6. The 30-user concurrency reality check

Your existing Flask wizard is single-threaded and single-pipeline (one global `pipeline_state` dict). **Modal solves this**: each call to `run_reel.spawn()` gets its own container, so 30 users can all be running in parallel without code changes. You will pay for 30× concurrent Kling jobs, but Kling's API is the actual bottleneck, not your server.

**Realistic launch-day load:** 30 users will not all click "create" in the first hour. Spread is more like 5 in hour 1, 10 over the next 6 hours, the rest over 2-3 days. Modal's auto-scaling handles this trivially.

**Hard cap recommendation:** put a Supabase row count check in `create_reel` — if `count(runs where status in ('queued','running')) > 5`, return 503 and tell the user to try again in 30 min. This protects you from 30 simultaneous Kling jobs draining credits before you can react.

---

## 7. Money: what each thing costs today

| Vendor | Free tier covers you? | Beyond free |
|---|---|---|
| Vercel | Yes (Hobby) | $20/mo Pro if traffic spikes |
| Modal | Yes ($30 free credit ≈ ~10 reels of compute alone, not counting Kling) | ~$0.10–$0.30 of compute per reel |
| Clerk | Yes (10K MAU free) | $25/mo Pro |
| Supabase | Yes (500MB DB, 1GB storage) | $25/mo Pro |
| Razorpay | Free signup. 2% per domestic card / UPI, 3% per international card. No fixed fee. GST extra (~18% on the fee). | Same |
| Kling / Gemini / ElevenLabs | Pay per call (your existing keys) | ~$3.19 / reel |

**Out-of-pocket today (excluding the per-reel API cost):** ~₹0. You only start paying for SaaS tiers when you outgrow free.

**Per-reel marginal cost on launch day:** ~$3.19 (Kling/Gemini/ElevenLabs) + ~$0.20 (Modal compute) = **~$3.39**. At ₹420 (~$5) revenue, Razorpay fee ≈ ₹10 (2% domestic) or ₹15 (3% international) + 18% GST on the fee. Gross margin per reel ≈ **$1.45**. 30 reels → **~$43 net margin**.

---

## 8. What you are deliberately *not* building today (and that's OK)

- **No automated lip-sync QA gate.** You watch every reel. 30 reels × ~40s viewing = 20 min of your time, total.
- **No content moderation.** You review topics manually before approving. If a beta user submits something off-brand, you decline and refund.
- **No retry/regen UX.** If a reel fails, you regenerate it from your admin page and message the user. Manual.
- **No self-serve refunds.** Refund manually in Stripe dashboard if needed.
- **No marketing site polish.** The existing landing is enough for 30 invitees.
- **No analytics.** Add PostHog tomorrow.
- **No email transactional flow.** Use Clerk's built-in emails + a single "your reel is ready" email via Resend (5-min setup), or skip and just use Clerk's notification.
- **No mobile-responsive admin page.** You will use desktop.
- **No multi-region deploy.** Single Vercel + single Modal region is fine for 30 users.
- **No backups.** Supabase auto-backups are on by default for free tier.

Each of these is in **Phase 2** of the PRODUCT_OVERVIEW roadmap. Do not let any of them block today.

---

## 9. The risks I want you to know about before you commit

1. **Razorpay KYC may be rejected** if any of the 5 policy pages are missing, the website is not loading, or any document scan is unclear. Mitigation: deploy the policy pages BEFORE submitting Razorpay (H+1 in the timeline). Don't promise a "live now" tweet until you have a successful test charge end-to-end. LemonSqueezy is the documented fallback.
2. **Kling rate limits at 30 concurrent jobs are unknown to you.** Mitigation: the 5-job concurrency cap in `create_reel` (section 6).
3. **A bad reel out the door = a bad first impression with a paying user.** Mitigation: you said you'll manually approve every reel. Hold the line on that.
4. **Modal cold-start is ~30s** the first time after deploy. Mitigation: warm the function once before announcing.
5. **Domain DNS propagation can take up to a few hours on Namecheap.** Mitigation: wire DNS in H+0, not H+7. Move it earlier in the timeline if you can.
6. **Your existing pipeline writes to local `.tmp/`.** On Modal each container has ephemeral disk; you must mount the Modal Volume at `/tmp_runs` and patch `run_pipeline.py` to accept `--workdir` (already supported via env var, verify before deploying).
7. **Voice ID is in `.env`.** Per the PRODUCT_OVERVIEW, this is process-global. For 30 users sharing the same anchor character that's fine — but **do not** let users pick voices in the beta or you'll hit a race condition on the env var.
8. **The 9 directive scripts assume `print()` does not crash on Unicode.** Modal containers are Linux/utf-8, so the Windows cp1252 issue from PRODUCT_OVERVIEW disappears — but verify by running one full reel in Modal before announcing.
9. **Razorpay webhook signature verification is non-negotiable.** Compute HMAC-SHA256 of the raw request body with your webhook secret and compare against the `X-Razorpay-Signature` header. Never grant credits without verifying — anyone can hit a public webhook URL.
10. **Refunds + regenerations cost you real money.** Budget for ~10% failure rate = 3 reels × $3.19 ≈ $10 of "burnt" cost across 30 users.

---

## 10. Decisions still open (need from you in the first hour)

1. **App subdomain name** — `app.frameforge.com`? `make.frameforge.com`? `studio.frameforge.com`? Pick one before DNS step.
2. **Admin email** — which email is the only one allowed to access `/admin`? (Probably `vignesh.balaraj@gmail.com`, confirm.)
3. **Razorpay business name** — what name do you want on the Payment Link and the buyer's card statement? Can be your personal name (sole proprietor) or a "doing business as" like "Frameforge by Vignesh".
4. **Beta invite mechanism** — open buy button on the landing, or invite-only via a code field? FCFS says "open until 30 sold," which is an open buy button + Supabase trigger that disables the Razorpay Payment Link after the 30th payment.
5. **What happens after 30 sold?** Waitlist form, or just "sold out"?
6. **Refund policy text** — Razorpay requires a published refund policy URL during KYC. Need a 1-paragraph "beta terms" + a refund stance (suggested: "100% refund within 24h if reel is not delivered or fails our quality check").
7. **Second video model contingency** — not for today, but write down which one you'd switch to if Kling goes down mid-beta. (Hedra is the closest analogue.)

---

## 11. What I need from you to start executing right now

If you say "go," I will:
1. Draft `execution/modal_app.py` against your existing `run_pipeline.py` interface.
2. Draft the Supabase SQL migration.
3. Draft the Razorpay webhook serverless function (with HMAC-SHA256 signature verification).
4. Draft the three Next.js pages (/, /app, /admin) with Clerk + Supabase wired.
5. Draft the 5 mandatory policy pages (Privacy, Terms, Refund, Contact, Pricing) — Razorpay KYC will not proceed without them.
6. Draft a one-page "Beta Terms" doc.
7. Hand you a checklist of every credential to paste into Modal + Vercel + Supabase.

Before I do, I need you to:
- Answer the 7 open decisions in section 10.
- Confirm the GitHub repo URL (or that I should help you push it).
- Confirm the exact domain so I can write the right Vercel/DNS instructions.
- Confirm you have **Indian PAN + Aadhaar + Indian bank account** ready for Razorpay KYC. If any one is missing, we drop to LemonSqueezy and I'll rewrite section 4c accordingly.

---

*This report is a snapshot of the launch path as of 2026-04-07. Update it as decisions are made.*
