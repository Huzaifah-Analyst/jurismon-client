-- ====================================================================
-- JurisMon Schema Migration 007: Subscription Controls (Pause, Resume, Cancel)
--
-- Supports self-service customer subscription lifecycle controls:
-- - paused_at: timestamp when billing was suspended
-- - resumed_at: timestamp when billing was reactivated
-- - cancelled_at: timestamp when subscription was cancelled
-- - access_until: timestamp until which access is retained (end of paid period)
-- - cancel_reason: client or customer reason for cancellation
-- ====================================================================

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS paused_at TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS resumed_at TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancelled_at TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS access_until TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_reason TEXT;
