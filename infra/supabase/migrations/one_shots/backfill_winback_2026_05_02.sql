-- One-shot backfill: enqueue the winback_d0 email for every existing
-- non-paying signup. Run this AFTER:
--   1. Migration 0010 (promo_codes + IGLOO50 seed) is applied
--   2. Migration 0011 (sent_emails + WELCOME25 seed) is applied
--   3. Vercel env has RESEND_API_KEY + INTERNAL_DRIP_SECRET set
--   4. The latest code is deployed
--
-- After running, manually trigger the sweep endpoint to fire the
-- winback_d0 sends immediately (no need to wait for the next pg_cron tick):
--
--   curl -X POST https://igloo.video/api/internal/send-drip \
--     -H "X-Internal-Secret: <your-INTERNAL_DRIP_SECRET>"
--
-- Or PowerShell:
--   Invoke-RestMethod -Uri https://igloo.video/api/internal/send-drip `
--     -Method POST `
--     -Headers @{ "X-Internal-Secret" = "<your-INTERNAL_DRIP_SECRET>" }
--
-- Idempotent: re-runnable without dupes (sent_emails has UNIQUE on
-- user_id + email_type).
--
-- Edit the disposable_domains list below if new spam patterns surface.

INSERT INTO public.sent_emails (user_id, email_type, status)
SELECT u.id, 'winback_d0', 'pending'
FROM public.users u
WHERE
  -- Skip paying customers — they're getting onboarding/transactional flow
  NOT EXISTS (
    SELECT 1 FROM public.payments p
    WHERE p.user_id = u.id AND p.status = 'captured'
  )
  -- Skip people who already have a winback_d0 row
  AND NOT EXISTS (
    SELECT 1 FROM public.sent_emails se
    WHERE se.user_id = u.id AND se.email_type = 'winback_d0'
  )
  -- Skip unsubscribed (defensive — fresh table, none exist yet)
  AND u.email_unsubscribed = false
  -- Skip disposable / spam-pattern domains. Add to this list if more surface.
  AND lower(split_part(u.email, '@', 2)) NOT IN (
    'mailinator.com',
    'hacknapp.com',
    'ryzid.com',
    '4heats.com',
    'deltajohnsons.com',
    'mugstock.com',
    '163.com',
    'duck.com'
  )
  -- Specific manual prunes
  AND lower(u.email) NOT IN (
    'ntazanasimwizye4@gmail.com'
  )
ON CONFLICT (user_id, email_type) DO NOTHING;

-- Verify how many were enqueued:
SELECT
  count(*) FILTER (WHERE status = 'pending') AS pending_to_send,
  count(*) AS total_winback_d0_rows
FROM public.sent_emails
WHERE email_type = 'winback_d0';
