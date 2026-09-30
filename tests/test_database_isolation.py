"""Guards the boundary between the test suite and a real database.

Repository() resolves its Supabase client from the environment, ignoring the
db_path it was handed, so production credentials in .env silently redirect every
write. This suite exists because that happened: running the tests once with live
credentials present created a source row in the production database.
"""

import os
import shutil
import tempfile
import unittest

import db.client as client_module
from db.repository import Repository


class TestSupabaseIsDisabledDuringTests(unittest.TestCase):

    def test_environment_carries_no_supabase_credentials(self):
        for name in ("SUPABASE_URL", "SUPABASE_KEY", "DATABASE_URL"):
            self.assertIsNone(
                os.environ.get(name),
                f"{name} is set during tests; writes would reach a real database",
            )

    def test_module_level_credentials_are_cleared(self):
        """db.client reads them at import time, before conftest can act."""
        self.assertFalse(client_module.SUPABASE_URL)
        self.assertFalse(client_module.SUPABASE_KEY)

    def test_no_cached_client_survives(self):
        self.assertIsNone(client_module.DatabaseClient.get_supabase())

    def test_repository_uses_sqlite(self):
        tmp = tempfile.mkdtemp(prefix="jurismon_isolation_")
        try:
            repo = Repository(db_path=os.path.join(tmp, "isolation.db"))
            self.assertFalse(
                repo.is_using_supabase(),
                "Repository built a Supabase client during tests",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_writes_land_in_the_given_sqlite_file(self):
        """The regression itself: an upsert must not travel to Supabase."""
        tmp = tempfile.mkdtemp(prefix="jurismon_isolation_")
        db_path = os.path.join(tmp, "isolation.db")
        try:
            repo = Repository(db_path=db_path)
            repo.upsert_source({
                "id": "test-isolation",
                "name": "Isolation Check",
                "base_url": "https://isolation.test/zoning",
                "adapter_type": "custom",
            })

            import sqlite3
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT id FROM sources WHERE id='test-isolation'"
                ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
