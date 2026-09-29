-- ====================================================================
-- JurisMon Schema Migration 003: Subscriber detail fields
--
-- The admin dashboard shows each subscriber's name and next billing date.
-- PayPal sends both on the ACTIVATED webhook, but they had nowhere to go.
-- ====================================================================

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS subscriber_name VARCHAR(255);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS next_billing_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- The dashboard filters by status and sorts by signup date.
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_created ON subscriptions(created_at DESC);
