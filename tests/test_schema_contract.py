"""Guards the contract between config/sites.json, the SQLite schema and the
PostgreSQL migration.

These three drift apart silently. The SQLite fallback accepts almost anything,
so a mismatch only surfaces the first time the app talks to a real Supabase
project - which, on this build, happens for the first time in production.

The concrete failure this pins down: sources are identified by slugs such as
"site-01-cityofnewyork", so sources.id cannot be a UUID column.
"""

import json
import re
import sqlite3
import tempfile
import shutil
import os
import unittest

MIGRATION = "db/migrations/001_initial_schema.sql"
SITES = "config/sites.json"

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)


def _column_block(sql: str, table: str) -> str:
    """Returns the column definitions for one CREATE TABLE statement."""
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table}\s*\((.*?)\n\);",
        sql,
        re.DOTALL | re.IGNORECASE,
    )
    assert match, f"table '{table}' not found in migration"
    return match.group(1)


class TestSourceIdentifierContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = open(MIGRATION, encoding="utf-8").read()
        cls.sites = json.load(open(SITES, encoding="utf-8"))

    def test_source_ids_are_slugs_not_uuids(self):
        for s in self.sites:
            self.assertFalse(UUID_RE.match(s["id"]),
                             f"{s['id']} looks like a UUID; the catalogue uses slugs")

    def test_postgres_sources_id_accepts_slugs(self):
        """A UUID column rejects 'site-01-cityofnewyork' on every insert."""
        block = _column_block(self.sql, "sources")
        id_line = next(l for l in block.splitlines() if l.strip().startswith("id "))
        self.assertNotIn("UUID", id_line.upper(),
                         "sources.id must be TEXT - slug ids cannot be stored in a UUID column")

    def test_documents_foreign_key_matches_sources_id_type(self):
        block = _column_block(self.sql, "documents")
        fk_line = next(l for l in block.splitlines() if "REFERENCES sources" in l)
        self.assertNotIn("UUID", fk_line.upper(),
                         "documents.source_id must match the TEXT type of sources.id")


class TestHealthFieldsArePersistable(unittest.TestCase):
    """The admin dashboard renders a health grid, so these must be storable."""

    @classmethod
    def setUpClass(cls):
        cls.sql = open(MIGRATION, encoding="utf-8").read()
        cls.sites = json.load(open(SITES, encoding="utf-8"))

    def test_catalogue_actually_uses_the_health_fields(self):
        self.assertTrue(any(s.get("health_status") for s in self.sites))
        self.assertTrue(any(s.get("status_detail") for s in self.sites))

    def test_postgres_schema_declares_them(self):
        block = _column_block(self.sql, "sources")
        self.assertIn("health_status", block)
        self.assertIn("status_detail", block)

    def test_sqlite_schema_declares_them(self):
        tmp = tempfile.mkdtemp(prefix="jurismon_schema_")
        try:
            from db.repository import Repository
            from unittest.mock import patch
            with patch("db.repository.DatabaseClient.get_supabase", return_value=None):
                Repository(db_path=os.path.join(tmp, "s.db"))
            with sqlite3.connect(os.path.join(tmp, "s.db")) as conn:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(sources)")}
            self.assertIn("health_status", cols)
            self.assertIn("status_detail", cols)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFullTextSearchColumns(unittest.TestCase):
    """repository.search_snapshots_and_diffs calls text_search on these."""

    @classmethod
    def setUpClass(cls):
        cls.sql = open(MIGRATION, encoding="utf-8").read()

    def test_search_vectors_exist_and_are_indexed(self):
        for table, column in (("snapshots", "search_vector"), ("diffs", "diff_vector")):
            self.assertIn(column, _column_block(self.sql, table),
                          f"{table}.{column} is missing")
            self.assertRegex(
                self.sql,
                rf"CREATE INDEX IF NOT EXISTS \w+ ON {table} USING GIN\({column}\)",
                f"{column} has no GIN index, so full-text search would sequential scan",
            )

    def test_columns_selected_by_the_repository_exist(self):
        """Cross-checks the PostgREST select strings against the migration."""
        expected = {
            "snapshots": ["id", "document_id", "version", "cleaned_text", "crawled_at"],
            "diffs": ["id", "document_id", "diff_payload", "added_clauses_count",
                      "removed_clauses_count", "generated_at"],
            "documents": ["title", "pdf_url", "source_id"],
            "sources": ["name", "state"],
        }
        for table, columns in expected.items():
            block = _column_block(self.sql, table)
            for col in columns:
                self.assertRegex(block, rf"\b{col}\b",
                                 f"{table}.{col} is selected in repository.py but absent from the schema")


class TestSQLitePostgresSchemaParity(unittest.TestCase):
    """Guards against adding columns to SQLite that have no corresponding Postgres migration.
    
    The pattern had failed three times:
    1. Users auth columns
    2. is_active boolean vs integer
    3. sources_skipped on crawl_runs
    
    This test verifies that every column created in SQLite across all tables
    is declared in at least one migration in db/migrations/*.sql, unless explicitly
    allow-listed with a documented reason.
    """

    SQLITE_ONLY_ALLOWLIST = {
        # subscriptions.user_email: SQLite stores user_email denormalized directly on
        # the subscriptions table for local standalone lookups and backwards compatibility,
        # whereas PostgreSQL normalizes this via subscriptions.user_id -> users.email.
        ("subscriptions", "user_email"): "Denormalized email in SQLite for local queries without joins",
    }

    def test_every_sqlite_column_has_postgres_migration(self):
        import glob
        from db.repository import Repository
        from unittest.mock import patch

        tmp_dir = tempfile.mkdtemp(prefix="jurismon_schema_parity_")
        db_path = os.path.join(tmp_dir, "parity_check.db")
        try:
            with patch("db.repository.DatabaseClient.get_supabase", return_value=None):
                Repository(db_path=db_path)

            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [r[0] for r in cur.fetchall()]
                sqlite_schema = {}
                for t in tables:
                    cur.execute(f"PRAGMA table_info({t})")
                    sqlite_schema[t] = [row[1] for row in cur.fetchall()]
        finally:
            import gc
            gc.collect()
            try:
                os.remove(db_path)
                os.rmdir(tmp_dir)
            except Exception:
                pass

        mig_dir = os.path.join(os.path.dirname(__file__), "..", "db", "migrations")
        all_sql = ""
        for f in sorted(glob.glob(os.path.join(mig_dir, "*.sql"))):
            with open(f, "r", encoding="utf-8") as fp:
                all_sql += "\n" + fp.read()

        missing = []
        for table, cols in sqlite_schema.items():
            for col in cols:
                if (table, col) in self.SQLITE_ONLY_ALLOWLIST:
                    continue
                pattern = rf"\b{col}\b"
                if not re.search(pattern, all_sql, re.IGNORECASE):
                    missing.append(f"{table}.{col}")

        self.assertEqual(
            missing,
            [],
            f"SQLite columns missing from db/migrations/*.sql: {missing}. "
            "Write a PostgreSQL migration in db/migrations/ or add to SQLITE_ONLY_ALLOWLIST if deliberately local.",
        )


if __name__ == "__main__":
    unittest.main()
