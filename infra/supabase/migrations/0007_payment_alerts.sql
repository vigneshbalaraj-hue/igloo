-- Payment failure alerts.
-- Inserted by processPayment when all retries exhaust on a step
-- that follows a successful Razorpay capture — i.e. the customer
-- has been charged but we failed to record it.

CREATE TABLE IF NOT EXISTS public.payment_alerts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  razorpay_payment_id TEXT NOT NULL,
  razorpay_order_id   TEXT,
  email               TEXT,
  clerk_user_id       TEXT,
  step                TEXT NOT NULL,       -- e.g. 'user_create_failed', 'payment_upsert_failed'
  error_message       TEXT,
  source              TEXT,                -- 'client' | 'webhook'
  resolved            BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX payment_alerts_resolved_idx ON public.payment_alerts (resolved) WHERE NOT resolved;
CREATE INDEX payment_alerts_created_at_idx ON public.payment_alerts (created_at DESC);
