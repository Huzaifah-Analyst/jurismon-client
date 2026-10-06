-- ====================================================================
-- JurisMon Schema Migration 008: Plan change log
--
-- Phase 2 Part 2 promised the client "a record of every price change,
-- with dates". Until now that record was a single logger.info line in
-- the systemd journal: not queryable, not visible in the admin panel,
-- and rotated away by journald after a few weeks. A record that
-- disappears is not a record.
--
-- One row per changed field, not one row per request, so the history
-- can answer "when did the price go up" rather than only "something
-- about this plan changed".
--
-- plan_id is NULL for catalogue-level changes (trial_days, currency),
-- which belong to the catalogue rather than to any one plan.
-- ====================================================================

CREATE TABLE IF NOT EXISTS plan_changes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(255),
    plan_id TEXT,
    field VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    paypal_plan_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_plan_changes_changed_at ON plan_changes(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_plan_changes_plan_id ON plan_changes(plan_id);
