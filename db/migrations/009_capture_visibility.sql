-- Reversible quarantine preserves original text, IDs, timestamps and versions.
ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS is_searchable BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS quality_reason TEXT;
ALTER TABLE diffs ADD COLUMN IF NOT EXISTS is_searchable BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE diffs ADD COLUMN IF NOT EXISTS quality_reason TEXT;
NOTIFY pgrst, 'reload schema';
