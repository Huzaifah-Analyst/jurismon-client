"""Keeps the test suite off any real database.

Repository() calls DatabaseClient.get_supabase() regardless of the db_path it is
given, so once a developer's .env holds production Supabase credentials every
test that writes a source or a subscription writes them to production. That is
exactly what happened the first time the production credentials landed in .env:
the suite created a "test-austin" source in the live database.

Clearing the credentials for the duration of the session forces every test down
the SQLite path, which is what they were always written to exercise. Tests that
want to cover the Supabase branch inject a fake client themselves, so they are
unaffected.
"""

import os

import pytest

SUPABASE_VARS = ("SUPABASE_URL", "SUPABASE_KEY", "DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def _isolate_from_real_databases():
    saved = {name: os.environ.get(name) for name in SUPABASE_VARS}
    for name in SUPABASE_VARS:
        os.environ.pop(name, None)

    # db.client reads these at import time and caches the client, so a client
    # built before this fixture ran has to be discarded too.
    import db.client as client_module
    client_module.SUPABASE_URL = None
    client_module.SUPABASE_KEY = None
    client_module.DATABASE_URL = None
    client_module.DatabaseClient._supabase_instance = None

    import sys
    if "api.main" in sys.modules:
        import api.main as api_main
        api_main.repo.supabase = None

    yield

    for name, value in saved.items():
        if value is not None:
            os.environ[name] = value
