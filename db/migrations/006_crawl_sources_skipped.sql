-- ====================================================================
-- JurisMon Schema Migration 006: Add sources_skipped to crawl_runs
--
-- Migration 001 created the crawl_runs table tracking total_sources,
-- sources_succeeded, and sources_failed, but did not track intentionally
-- skipped inactive sources (e.g. Cloudflare protected or dead municipal
-- portals). This migration adds sources_skipped so run records accurately
-- report complete execution coverage (crawled, succeeded, failed, skipped)
-- in PostgreSQL / Supabase.
-- ====================================================================

ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS sources_skipped INTEGER DEFAULT 0;
