-- ====================================================================
-- JurisMon Schema Migration 004: Webhook delivery log
--
-- Every PayPal delivery is stored, including ones rejected at signature
-- verification. When live webhooks fail, the stored payload and reason are
-- the only record of what arrived.
-- ====================================================================

CREATE TABLE IF NOT EXISTS webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id TEXT UNIQUE,
    event_type VARCHAR(100),
    subscription_id TEXT,
    subscriber_name VARCHAR(255),
    amount NUMERIC(12, 2),
    currency VARCHAR(10),
    result VARCHAR(20) DEFAULT 'processed',  -- 'processed', 'rejected', 'failed'
    error_detail TEXT,
    payload JSONB,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_received ON webhook_events(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_events_result ON webhook_events(result);
