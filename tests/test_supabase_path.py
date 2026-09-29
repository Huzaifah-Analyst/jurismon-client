"""Tests for the Supabase branch of the repository.

Every repository method is written as `if self.supabase: <postgrest> else:
<sqlite>`. Without credentials the client is None, so the whole Supabase half -
the code that actually runs in production - was never executed by any test.

These tests drive that half with a fake PostgREST client, and pin down the
silent-degradation behaviour: when Supabase raises, the method falls through to
SQLite rather than surfacing the error.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from db.repository import Repository


class FakeQuery:
    """Records the PostgREST chain and returns canned rows on execute()."""

    def __init__(self, table, log, data, raises=False):
        self.table = table
        self.log = log
        self._data = data
        self._raises = raises
        self.payload = None

    def _record(self, op, *args, **kwargs):
        self.log.append((self.table, op, args, kwargs))
        return self

    def select(self, *a, **k):
        return self._record("select", *a, **k)

    def eq(self, *a, **k):
        return self._record("eq", *a, **k)

    def order(self, *a, **k):
        return self._record("order", *a, **k)

    def limit(self, *a, **k):
        return self._record("limit", *a, **k)

    def text_search(self, *a, **k):
        return self._record("text_search", *a, **k)

    def insert(self, payload, *a, **k):
        self.payload = payload
        return self._record("insert", payload, **k)

    def upsert(self, payload, *a, **k):
        self.payload = payload
        return self._record("upsert", payload, **k)

    def execute(self):
        self.log.append((self.table, "execute", (), {}))
        if self._raises:
            raise RuntimeError("Supabase unavailable")
        return MagicMock(data=self._data)


class FakeSupabase:
    def __init__(self, rows_by_table=None, raises=False):
        self.rows = rows_by_table or {}
        self.calls = []
        self.raises = raises

    def table(self, name):
        return FakeQuery(name, self.calls, self.rows.get(name, []), self.raises)

    def ops(self, table=None):
        return [c[1] for c in self.calls if table is None or c[0] == table]


class SupabaseRepositoryTestCase(unittest.TestCase):
    """Builds a Repository whose Supabase client is the fake above."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jurismon_sb_")
        self.db_path = os.path.join(self._tmp, "fallback.db")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _repo(self, rows=None, raises=False):
        fake = FakeSupabase(rows, raises=raises)
        with patch("db.repository.DatabaseClient.get_supabase", return_value=fake):
            repo = Repository(db_path=self.db_path)
        return repo, fake


class TestSupabaseIsPreferred(SupabaseRepositoryTestCase):

    def test_repository_reports_supabase_in_use(self):
        repo, _ = self._repo()
        self.assertTrue(repo.is_using_supabase())

    def test_get_active_sources_queries_supabase(self):
        rows = [{"id": "site-01", "name": "NYC", "is_active": True}]
        repo, fake = self._repo({"sources": rows})

        result = repo.get_active_sources()

        self.assertEqual(result, rows)
        self.assertIn("select", fake.ops("sources"))
        self.assertIn(("sources", "eq", ("is_active", True), {}), fake.calls)

    def test_get_all_sources_orders_by_name(self):
        rows = [{"id": "site-01", "name": "Austin"}]
        repo, fake = self._repo({"sources": rows})

        self.assertEqual(repo.get_all_sources(), rows)
        self.assertIn(("sources", "order", ("name",), {}), fake.calls)

    def test_upsert_source_uses_base_url_conflict_key(self):
        repo, fake = self._repo({"sources": [{"id": "site-99"}]})

        repo.upsert_source({
            "id": "site-99", "name": "Test City",
            "base_url": "https://test.gov", "adapter_type": "custom",
        })

        upserts = [c for c in fake.calls if c[1] == "upsert"]
        self.assertEqual(len(upserts), 1)
        self.assertEqual(upserts[0][3].get("on_conflict"), "base_url")

    def test_get_or_create_document_returns_existing_without_inserting(self):
        existing = [{"id": "doc-1", "title": "Zoning Ordinance"}]
        repo, fake = self._repo({"documents": existing})

        result = repo.get_or_create_document("site-01", "Zoning Ordinance", "https://a.gov/z.pdf")

        self.assertEqual(result, existing[0])
        self.assertNotIn("insert", fake.ops("documents"))

    def test_get_or_create_document_inserts_when_absent(self):
        """An empty select must be followed by an insert on the same table."""
        fake = FakeSupabase({"documents": []})
        inserted = {}

        original_table = fake.table
        state = {"calls": 0}

        def table(name):
            q = original_table(name)
            if name == "documents":
                state["calls"] += 1
                if state["calls"] > 1:      # the insert call
                    q._data = [{"id": "doc-new"}]
                    inserted["q"] = q
            return q

        fake.table = table
        with patch("db.repository.DatabaseClient.get_supabase", return_value=fake):
            repo = Repository(db_path=self.db_path)

        result = repo.get_or_create_document("site-01", "New Notice", "https://a.gov/n.pdf")

        self.assertEqual(result, {"id": "doc-new"})
        self.assertIn("insert", fake.ops("documents"))
        self.assertEqual(inserted["q"].payload["pdf_url"], "https://a.gov/n.pdf")
        self.assertEqual(inserted["q"].payload["title"], "New Notice")


class TestSupabaseFullTextSearch(SupabaseRepositoryTestCase):
    """Search is the one place the Postgres tsvector/GIN indexes are used."""

    def test_search_uses_text_search_on_both_vectors(self):
        repo, fake = self._repo({
            "snapshots": [{"id": "s1", "cleaned_text": "setback requirements"}],
            "diffs": [{"id": "d1", "diff_payload": "{}"}],
        })

        result = repo.search_snapshots_and_diffs("setback")

        searches = [c for c in fake.calls if c[1] == "text_search"]
        self.assertEqual(len(searches), 2)
        columns = {c[2][0] for c in searches}
        self.assertEqual(columns, {"search_vector", "diff_vector"})
        for c in searches:
            self.assertEqual(c[2][1], "setback")

        self.assertEqual(len(result["snapshots"]), 1)
        self.assertEqual(len(result["diffs"]), 1)

    def test_search_applies_the_requested_limit(self):
        repo, fake = self._repo({"snapshots": [], "diffs": []})
        repo.search_snapshots_and_diffs("zoning", limit=7)

        limits = [c[2][0] for c in fake.calls if c[1] == "limit"]
        self.assertTrue(limits)
        self.assertTrue(all(v == 7 for v in limits))


class TestSupabaseDegradation(SupabaseRepositoryTestCase):
    """What happens when Supabase is configured but failing.

    Each method logs and then continues into the SQLite branch. That keeps a
    crawl alive during an outage, but it also means production writes land in a
    local file instead, with only a log line to say so.
    """

    def test_read_falls_back_to_sqlite_instead_of_raising(self):
        repo, _ = self._repo({"sources": [{"id": "supabase-only-row"}]}, raises=True)

        result = repo.get_active_sources()

        # No exception, and the rows came from the local store that the schema
        # seeds from config/sites.json - not from the (failing) Supabase client.
        self.assertIsInstance(result, list)
        self.assertNotIn("supabase-only-row", [r.get("id") for r in result])
        self.assertTrue(os.path.exists(self.db_path))

    def test_search_falls_back_to_sqlite_like_query(self):
        repo, _ = self._repo(raises=True)

        result = repo.search_snapshots_and_diffs("ordinance")

        self.assertIn("snapshots", result)
        self.assertIn("diffs", result)

    def test_outage_is_logged_rather_than_silently_swallowed(self):
        repo, _ = self._repo(raises=True)

        with self.assertLogs("jurismon.repository", level="ERROR") as captured:
            repo.get_active_sources()

        self.assertTrue(any("Supabase" in line for line in captured.output))

    def test_write_during_outage_lands_in_sqlite(self):
        """Documents the risk: an outage silently redirects writes to local disk."""
        repo, _ = self._repo(raises=True)

        repo.upsert_source({
            "id": "site-77", "name": "Outage City",
            "base_url": "https://outage.gov", "adapter_type": "custom",
        })

        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT id FROM sources WHERE id='site-77'").fetchall()
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
