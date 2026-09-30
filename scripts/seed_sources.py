"""Loads config/sites.json into the configured database.

The SQLite fallback seeds itself on first use, but Supabase does not, so a
freshly migrated production database starts with an empty sources table and the
crawler has nothing to crawl. This closes that gap for any fresh deployment.

Safe to re-run: sources are upserted on base_url, so re-running applies catalogue
edits rather than creating duplicates.

Usage:
    python scripts/seed_sources.py            # apply
    python scripts/seed_sources.py --dry-run  # report what would change
"""

import os
import sys
import json
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from db.repository import Repository

CONFIG = pathlib.Path(__file__).parent.parent / "config" / "sites.json"


def load_catalogue() -> list:
    if not CONFIG.exists():
        sys.exit(f"Source catalogue not found: {CONFIG}")
    with open(CONFIG, encoding="utf-8") as fh:
        sources = json.load(fh)
    if not isinstance(sources, list) or not sources:
        sys.exit(f"{CONFIG} did not contain a non-empty list of sources.")
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written without writing it")
    args = parser.parse_args()

    sources = load_catalogue()
    repo = Repository()
    backend = "Supabase" if repo.is_using_supabase() else "SQLite"

    existing = {s.get("base_url") for s in repo.get_all_sources()}
    new = [s for s in sources if s.get("base_url") not in existing]

    print(f"Backend        : {backend}")
    print(f"Catalogue      : {len(sources)} sources")
    print(f"Already stored : {len(existing)}")
    print(f"New            : {len(new)}")

    if args.dry_run:
        for s in new[:10]:
            print(f"  + {s['id']}")
        if len(new) > 10:
            print(f"  ... and {len(new) - 10} more")
        print("\nDry run - nothing written.")
        return

    written, failed = 0, []
    for s in sources:
        try:
            repo.upsert_source({
                "id": s["id"],
                "name": s["name"],
                "state": s.get("state"),
                "county": s.get("county"),
                "base_url": s["base_url"],
                "adapter_type": s.get("adapter_type", "custom"),
                "selectors_config": s.get("selectors_config", {}),
                "is_active": s.get("is_active", True),
                "health_status": s.get("health_status", "operational"),
                "status_detail": s.get("status_detail"),
            })
            written += 1
        except Exception as exc:
            failed.append((s.get("id"), str(exc)[:100]))

    print(f"\nUpserted {written} of {len(sources)} sources into {backend}.")
    if failed:
        print(f"{len(failed)} failed:")
        for sid, err in failed[:10]:
            print(f"  {sid}: {err}")
        sys.exit(1)

    stored = repo.get_all_sources()
    active = sum(1 for s in stored if s.get("health_status") == "operational")
    print(f"Now stored: {len(stored)} sources, {active} operational.")


if __name__ == "__main__":
    main()
