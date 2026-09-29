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


if __name__ == "__main__":
    unittest.main()
