"""JurisMon Data Access Repository.

Sub-Task 4.2:
Provides unified data persistence supporting Supabase PostgreSQL with
fallback to SQLite for local development and standalone testing.
Handles snapshots, statutory diffs, crawl runs, and subscriber payments.
"""

import os
import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from db.client import DatabaseClient

logger = logging.getLogger("jurismon.repository")


class Repository:
    """Production data access repository with Supabase and SQLite fallback."""

    def __init__(self, db_path: str = "jurismon_local.db"):
        self.supabase = DatabaseClient.get_supabase()
        self.db_path = db_path
        self._init_sqlite_schema()

    @contextmanager
    def _connect(self):
        """Yields a SQLite connection that is committed and then closed.

        `with sqlite3.connect(...)` only manages the transaction - it leaves the
        connection open, which keeps a file handle (and on Windows a file lock)
        alive until garbage collection runs.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def is_connected(self) -> bool:
        """Returns True if connected to Supabase or SQLite."""
        return True

    def is_using_supabase(self) -> bool:
        return self.supabase is not None

    def _init_sqlite_schema(self):
        """Initializes local SQLite tables for offline/local standalone mode."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    state TEXT,
                    county TEXT,
                    base_url TEXT UNIQUE NOT NULL,
                    adapter_type TEXT DEFAULT 'custom',
                    selectors_config TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    source_id TEXT,
                    title TEXT NOT NULL,
                    document_type TEXT DEFAULT 'notice',
                    pdf_url TEXT NOT NULL,
                    current_content_hash TEXT,
                    created_at TEXT,
                    UNIQUE(source_id, pdf_url)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    content_hash TEXT NOT NULL,
                    raw_text TEXT,
                    cleaned_text TEXT NOT NULL,
                    ocr_applied INTEGER DEFAULT 0,
                    crawled_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS diffs (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    previous_snapshot_id TEXT,
                    current_snapshot_id TEXT NOT NULL,
                    diff_payload TEXT NOT NULL,
                    added_clauses_count INTEGER DEFAULT 0,
                    removed_clauses_count INTEGER DEFAULT 0,
                    generated_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    user_email TEXT,
                    provider TEXT DEFAULT 'paypal',
                    external_subscription_id TEXT UNIQUE,
                    plan_id TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT
                )
            """)
            conn.commit()

            # Auto-seed sources if table is empty
            cur.execute("SELECT COUNT(*) FROM sources")
            count = cur.fetchone()[0]
            if count == 0:
                sites_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "sites.json")
                if os.path.exists(sites_cfg_path):
                    try:
                        with open(sites_cfg_path, "r", encoding="utf-8") as f:
                            sites = json.load(f)
                        for s in sites:
                            s_id = s.get("id")
                            s_name = s.get("name", "Unnamed")
                            s_state = s.get("state")
                            s_county = s.get("county")
                            s_url = s.get("base_url")
                            s_adapter = s.get("adapter_type", "custom")
                            s_selectors = json.dumps(s.get("selectors_config", {}))
                            s_active = 1 if s.get("is_active", True) else 0
                            s_created = datetime.now(timezone.utc).isoformat()
                            cur.execute("""
                                INSERT OR IGNORE INTO sources (id, name, state, county, base_url, adapter_type, selectors_config, is_active, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (s_id, s_name, s_state, s_county, s_url, s_adapter, s_selectors, s_active, s_created))
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Failed to auto-seed sources: {e}")


    def upsert_source(self, source_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Inserts or updates a municipal source."""
        if self.supabase:
            try:
                res = self.supabase.table("sources").upsert(source_data, on_conflict="base_url").execute()
                return res.data[0] if res.data else None
            except Exception as e:
                logger.error(f"Supabase upsert source error: {e}")

        # SQLite Fallback
        import uuid
        source_id = str(source_data.get("id") or uuid.uuid4())
        name = source_data.get("name", "Unnamed")
        base_url = source_data.get("base_url")
        adapter_type = source_data.get("adapter_type", "custom")
        selectors_cfg = json.dumps(source_data.get("selectors_config", {}))

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sources (id, name, base_url, adapter_type, selectors_config, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(base_url) DO UPDATE SET
                    name=excluded.name,
                    adapter_type=excluded.adapter_type,
                    selectors_config=excluded.selectors_config
            """, (source_id, name, base_url, adapter_type, selectors_cfg, datetime.now(timezone.utc).isoformat()))
            conn.commit()

        return {"id": source_id, "name": name, "base_url": base_url}

    def get_active_sources(self) -> List[Dict[str, Any]]:
        """Retrieves active (operational) monitored municipal sources."""
        if self.supabase:
            try:
                res = self.supabase.table("sources").select("*").eq("is_active", True).execute()
                return res.data or []
            except Exception as e:
                logger.error(f"Supabase get sources error: {e}")

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sources WHERE is_active=1 ORDER BY name ASC")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Retrieves all 51 target municipal sources with their audit health categorization."""
        if self.supabase:
            try:
                res = self.supabase.table("sources").select("*").order("name").execute()
                return res.data or []
            except Exception as e:
                logger.error(f"Supabase get all sources error: {e}")

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sources ORDER BY is_active DESC, name ASC")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_or_create_document(
        self, source_id: str, title: str, pdf_url: str, document_type: str = "notice"
    ) -> Optional[Dict[str, Any]]:
        """Finds or creates a tracked document record."""
        if self.supabase:
            try:
                res = self.supabase.table("documents").select("*").eq("source_id", source_id).eq("pdf_url", pdf_url).execute()
                if res.data:
                    return res.data[0]
                insert_res = self.supabase.table("documents").insert({
                    "source_id": source_id,
                    "title": title,
                    "pdf_url": pdf_url,
                    "document_type": document_type,
                }).execute()
                return insert_res.data[0] if insert_res.data else None
            except Exception as e:
                logger.error(f"Supabase get/create document error: {e}")

        # SQLite Fallback
        import uuid
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE source_id=? AND pdf_url=?", (source_id, pdf_url))
            row = cur.fetchone()
            if row:
                return dict(row)

            doc_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute("""
                INSERT INTO documents (id, source_id, title, document_type, pdf_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doc_id, source_id, title, document_type, pdf_url, now_iso))
            conn.commit()
            return {"id": doc_id, "source_id": source_id, "title": title, "pdf_url": pdf_url}

    def get_latest_snapshot(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the newest version snapshot for a document."""
        if self.supabase:
            try:
                res = self.supabase.table("snapshots").select("*").eq("document_id", document_id).order("version", desc=True).limit(1).execute()
                return res.data[0] if res.data else None
            except Exception as e:
                logger.error(f"Supabase get latest snapshot error: {e}")

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM snapshots WHERE document_id=? ORDER BY version DESC LIMIT 1", (document_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def create_snapshot(
        self, document_id: str, version: int, content_hash: str, raw_text: str, cleaned_text: str, ocr_applied: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Saves a new versioned text snapshot."""
        if self.supabase:
            try:
                res = self.supabase.table("snapshots").insert({
                    "document_id": document_id,
                    "version": version,
                    "content_hash": content_hash,
                    "raw_text": raw_text,
                    "cleaned_text": cleaned_text,
                    "ocr_applied": ocr_applied,
                }).execute()
                return res.data[0] if res.data else None
            except Exception as e:
                logger.error(f"Supabase create snapshot error: {e}")

        import uuid
        snap_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO snapshots (id, document_id, version, content_hash, raw_text, cleaned_text, ocr_applied, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (snap_id, document_id, version, content_hash, raw_text, cleaned_text, 1 if ocr_applied else 0, now_iso))
            conn.commit()
        return {"id": snap_id, "document_id": document_id, "version": version, "cleaned_text": cleaned_text}

    def save_diff(
        self, document_id: str, previous_snapshot_id: Optional[str], current_snapshot_id: str, diff_payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Persists a calculated statutory diff."""
        if self.supabase:
            try:
                res = self.supabase.table("diffs").insert({
                    "document_id": document_id,
                    "previous_snapshot_id": previous_snapshot_id,
                    "current_snapshot_id": current_snapshot_id,
                    "diff_payload": diff_payload,
                    "added_clauses_count": diff_payload.get("total_added", 0),
                    "removed_clauses_count": diff_payload.get("total_removed", 0),
                }).execute()
                return res.data[0] if res.data else None
            except Exception as e:
                logger.error(f"Supabase save diff error: {e}")

        import uuid
        diff_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(diff_payload)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO diffs (id, document_id, previous_snapshot_id, current_snapshot_id, diff_payload, added_clauses_count, removed_clauses_count, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (diff_id, document_id, previous_snapshot_id, current_snapshot_id, payload_str, diff_payload.get("total_added", 0), diff_payload.get("total_removed", 0), now_iso))
            conn.commit()
        return {"id": diff_id, "document_id": document_id, "diff_payload": diff_payload}

    def search_snapshots_and_diffs(self, query: str, limit: int = 30) -> Dict[str, Any]:
        """Executes full-text ranked queries across snapshots and statutory diff deltas."""
        if self.supabase:
            try:
                snapshots_res = self.supabase.table("snapshots").select(
                    "id, document_id, version, cleaned_text, crawled_at, documents(title, pdf_url, source_id, sources(name, state))"
                ).text_search("search_vector", query).limit(limit).execute()

                diffs_res = self.supabase.table("diffs").select(
                    "id, document_id, diff_payload, added_clauses_count, removed_clauses_count, generated_at, documents(title, pdf_url, sources(name, state))"
                ).text_search("diff_vector", query).limit(limit).execute()

                return {
                    "snapshots": snapshots_res.data or [],
                    "diffs": diffs_res.data or [],
                }
            except Exception as e:
                logger.error(f"Supabase search error: {e}")

        # SQLite Search Implementation (LIKE query across text and diff payloads)
        clean_q = f"%{query.strip()}%"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Search Snapshots
            cur.execute("""
                SELECT s.id, s.document_id, s.version, s.cleaned_text, s.crawled_at, s.ocr_applied,
                       d.title as doc_title, d.pdf_url as doc_url,
                       src.name as source_name, src.state as source_state, src.county as source_county
                FROM snapshots s
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN sources src ON d.source_id = src.id
                WHERE s.cleaned_text LIKE ?
                ORDER BY s.crawled_at DESC
                LIMIT ?
            """, (clean_q, limit))
            snap_rows = cur.fetchall()

            # Search Diffs
            cur.execute("""
                SELECT df.id, df.document_id, df.diff_payload, df.added_clauses_count, df.removed_clauses_count, df.generated_at,
                       d.title as doc_title, d.pdf_url as doc_url,
                       src.name as source_name, src.state as source_state, src.county as source_county
                FROM diffs df
                JOIN documents d ON df.document_id = d.id
                LEFT JOIN sources src ON d.source_id = src.id
                WHERE df.diff_payload LIKE ?
                ORDER BY df.generated_at DESC
                LIMIT ?
            """, (clean_q, limit))
            diff_rows = cur.fetchall()

            formatted_snaps = []
            for r in snap_rows:
                formatted_snaps.append({
                    "id": r["id"],
                    "document_id": r["document_id"],
                    "version": r["version"],
                    "cleaned_text": r["cleaned_text"],
                    "crawled_at": r["crawled_at"],
                    "ocr_applied": bool(r["ocr_applied"]),
                    "documents": {
                        "title": r["doc_title"],
                        "pdf_url": r["doc_url"],
                        "source_name": r["source_name"],
                        "source_state": r["source_state"],
                        "source_county": r["source_county"],
                    },
                })

            formatted_diffs = []
            for r in diff_rows:
                formatted_diffs.append({
                    "id": r["id"],
                    "document_id": r["document_id"],
                    "diff_payload": json.loads(r["diff_payload"]),
                    "added_clauses_count": r["added_clauses_count"],
                    "removed_clauses_count": r["removed_clauses_count"],
                    "generated_at": r["generated_at"],
                    "documents": {
                        "title": r["doc_title"],
                        "pdf_url": r["doc_url"],
                        "source_name": r["source_name"],
                        "source_state": r["source_state"],
                        "source_county": r["source_county"],
                    },
                })

            return {"snapshots": formatted_snaps, "diffs": formatted_diffs}

    def record_subscription(
        self, external_sub_id: str, plan_id: str, status: str = "active", user_email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Records or updates a user subscription from PayPal/Stripe."""
        import uuid
        sub_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO subscriptions (id, user_email, external_subscription_id, plan_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_subscription_id) DO UPDATE SET
                    status=excluded.status
            """, (sub_id, user_email, external_sub_id, plan_id, status, now_iso))
            conn.commit()

        return {"id": sub_id, "external_subscription_id": external_sub_id, "status": status}

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """Returns all registered subscribers for admin dashboard."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM subscriptions ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [dict(r) for r in rows]
