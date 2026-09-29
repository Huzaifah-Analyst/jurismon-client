"""Applies the SQL migrations in db/migrations to the configured PostgreSQL database.

Usage:
    python scripts/run_migrations.py              # uses DATABASE_URL from .env
    python scripts/run_migrations.py --dry-run    # show what would run
    python scripts/run_migrations.py --print      # print SQL to paste into
                                                  # the Supabase SQL editor

Applied migrations are recorded in a schema_migrations table, so re-running is
safe and only new files execute.

The connection string is the one Supabase shows under
Project Settings -> Database -> Connection string.
"""

import os
import sys
import argparse
import hashlib
import pathlib
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent / "db" / "migrations"

TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""


def migration_files() -> list:
    if not MIGRATIONS_DIR.is_dir():
        sys.exit(f"Migrations directory not found: {MIGRATIONS_DIR}")
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        sys.exit(f"No .sql files in {MIGRATIONS_DIR}")
    return files


def checksum(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def print_sql() -> None:
    """Emits every migration for manual execution in the Supabase SQL editor."""
    for path in migration_files():
        print(f"\n{'-' * 70}\n-- {path.name}\n{'-' * 70}")
        print(path.read_text(encoding="utf-8"))


def connect(database_url: str):
    try:
        import psycopg2
    except ImportError:
        sys.exit(
            "psycopg2 is not installed.\n"
            "    pip install psycopg2-binary\n"
            "Or run with --print and paste the SQL into the Supabase SQL editor."
        )
    except Exception as exc:
        sys.exit(
            f"psycopg2 could not be loaded: {exc}\n"
            "Run with --print and paste the SQL into the Supabase SQL editor instead."
        )
    return psycopg2.connect(database_url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report pending migrations without applying them")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="print the SQL instead of connecting")
    parser.add_argument("--database-url", default=None,
                        help="override DATABASE_URL")
    args = parser.parse_args()

    if args.print_only:
        print_sql()
        return

    database_url = args.database_url or os.getenv("DATABASE_URL", "").strip()
    if not database_url or database_url.startswith("postgresql://postgres:your-db-password"):
        sys.exit(
            "DATABASE_URL is not set (or still holds the .env.example placeholder).\n"
            "Find it in Supabase under Project Settings -> Database -> Connection string.\n"
            "Alternatively run with --print and paste the SQL into the SQL editor."
        )

    files = migration_files()

    conn = connect(database_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(TRACKING_TABLE)
            conn.commit()

            cur.execute("SELECT filename, checksum FROM schema_migrations")
            applied = dict(cur.fetchall())

        pending = []
        for path in files:
            digest = checksum(path)
            if path.name not in applied:
                pending.append((path, digest))
            elif applied[path.name] != digest:
                # An applied migration that changed on disk means the database
                # and the repository no longer agree about what was run.
                print(
                    f"WARNING: {path.name} has changed since it was applied "
                    f"(recorded {applied[path.name]}, now {digest}). Skipping.",
                    file=sys.stderr,
                )

        if not pending:
            print(f"Up to date - {len(applied)} migration(s) already applied.")
            return

        print(f"Pending: {', '.join(p.name for p, _ in pending)}")
        if args.dry_run:
            print("Dry run - nothing applied.")
            return

        for path, digest in pending:
            print(f"  applying {path.name} ...", end=" ", flush=True)
            with conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (filename, checksum, applied_at) "
                    "VALUES (%s, %s, %s)",
                    (path.name, digest, datetime.now(timezone.utc)),
                )
            conn.commit()
            print("ok")

        print(f"\nApplied {len(pending)} migration(s).")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
