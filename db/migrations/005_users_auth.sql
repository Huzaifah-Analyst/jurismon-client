-- ====================================================================
-- JurisMon Schema Migration 005: User Authentication & Trial Fields
--
-- Migration 002 created the users table with basic subscriber columns,
-- but the email-verification auth flow requires password hashing, email
-- confirmation tracking, and 14-day trial timestamps.
-- This migration adds the missing columns, reconciles is_active to SMALLINT
-- to prevent integer-vs-boolean coercion errors during API registration,
-- and indexes email for fast authentication lookups.
-- ====================================================================

-- 1. Reconcile is_active from BOOLEAN to SMALLINT (1 = active, 0 = inactive)
--    Guarded by information_schema type check so subsequent runs are a no-op.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'is_active'
          AND data_type = 'boolean'
    ) THEN
        ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT;
        ALTER TABLE users ALTER COLUMN is_active TYPE SMALLINT USING (CASE WHEN is_active THEN 1 ELSE 0 END);
        ALTER TABLE users ALTER COLUMN is_active SET DEFAULT 1;
    END IF;
END $$;

-- 2. Add authentication and trial management columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified SMALLINT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code_expires_at TIMESTAMP WITH TIME ZONE;

-- 3. Add index on email for lookup performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_lower_email ON users(LOWER(email));
