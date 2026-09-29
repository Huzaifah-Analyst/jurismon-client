-- ====================================================================
-- JurisMon Schema Migration 001: Core Ingestion, Snapshots & Diffing
-- Compatible with Supabase / PostgreSQL 14+
-- ====================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 1. SOURCES TABLE (Municipal and County Zoning Entities)
-- id is the human-readable slug from config/sites.json (e.g. 'site-01-cityofnewyork'),
-- not a generated UUID, so that the file remains the source of truth and a source
-- keeps the same identity across rebuilds.
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    state VARCHAR(50),
    county VARCHAR(100),
    base_url TEXT NOT NULL UNIQUE,
    adapter_type VARCHAR(50) NOT NULL DEFAULT 'custom', -- 'rest_api', 'xml', 'atom', 'direct_document', 'municode', 'granicus', 'civicplus', 'custom'
    selectors_config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    -- Why an inactive source is parked, so nothing is silently dropped.
    health_status VARCHAR(50) DEFAULT 'operational', -- 'operational', 'dead_link', 'cloudflare_blocked', 'unreachable', 'blocked_403', 'auth_required'
    status_detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. DOCUMENTS TABLE (Tracked PDF / HTML Notice Items)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    document_type VARCHAR(100) DEFAULT 'notice', -- 'notice', 'meeting_minutes', 'ordinance', 'bylaw'
    pdf_url TEXT NOT NULL,
    current_content_hash VARCHAR(64),
    last_crawled_at TIMESTAMP WITH TIME ZONE,
    last_changed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_source_pdf UNIQUE (source_id, pdf_url)
);

-- 3. SNAPSHOTS TABLE (Timestamped Cleaned Text Versions)
CREATE TABLE IF NOT EXISTS snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    content_hash VARCHAR(64) NOT NULL,
    raw_text TEXT,
    cleaned_text TEXT NOT NULL,
    crawled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ocr_applied BOOLEAN DEFAULT FALSE,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(cleaned_text, ''))
    ) STORED
);

-- 4. DIFFS TABLE (Section & Paragraph Diffs between Snapshots)
CREATE TABLE IF NOT EXISTS diffs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    previous_snapshot_id UUID REFERENCES snapshots(id) ON DELETE SET NULL,
    current_snapshot_id UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    diff_payload JSONB NOT NULL, -- { "added": [...], "removed": [...], "modified": [...] }
    added_clauses_count INT DEFAULT 0,
    removed_clauses_count INT DEFAULT 0,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    diff_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(diff_payload::text, ''))
    ) STORED
);

-- 5. CRAWL RUNS TABLE (Execution Tracking & Health Monitoring)
CREATE TABLE IF NOT EXISTS crawl_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed', 'partial_failure'
    total_sources INT DEFAULT 0,
    sources_succeeded INT DEFAULT 0,
    sources_failed INT DEFAULT 0,
    documents_found INT DEFAULT 0,
    diffs_created INT DEFAULT 0,
    error_logs JSONB DEFAULT '[]'::jsonb
);

-- Indexes for Fast Queries and Full-Text Search
CREATE INDEX IF NOT EXISTS idx_snapshots_document_id ON snapshots(document_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_search_vector ON snapshots USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_diffs_document_id ON diffs(document_id);
CREATE INDEX IF NOT EXISTS idx_diffs_diff_vector ON diffs USING GIN(diff_vector);
CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(current_content_hash);
CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(is_active);
