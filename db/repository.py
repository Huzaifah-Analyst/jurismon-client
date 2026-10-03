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
                    health_status TEXT DEFAULT 'operational',
                    status_detail TEXT,
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
                    subscriber_name TEXT,
                    provider TEXT DEFAULT 'paypal',
                    external_subscription_id TEXT UNIQUE,
                    plan_id TEXT,
                    status TEXT DEFAULT 'active',
                    next_billing_at TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id TEXT PRIMARY KEY,
                    event_id TEXT UNIQUE,
                    event_type TEXT,
                    subscription_id TEXT,
                    subscriber_name TEXT,
                    amount REAL,
                    currency TEXT,
                    result TEXT DEFAULT 'processed',
                    error_detail TEXT,
                    payload TEXT,
                    received_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT DEFAULT 'running',
                    total_sources INTEGER DEFAULT 0,
                    sources_succeeded INTEGER DEFAULT 0,
                    sources_failed INTEGER DEFAULT 0,
                    sources_skipped INTEGER DEFAULT 0,
                    documents_found INTEGER DEFAULT 0,
                    diffs_created INTEGER DEFAULT 0,
                    error_logs TEXT DEFAULT '[]'
                )
            """)
            try:
                cur.execute("ALTER TABLE crawl_runs ADD COLUMN sources_skipped INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE subscriptions ADD COLUMN user_id TEXT")
            except Exception:
                pass
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    trial_started_at TEXT,
                    trial_ends_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    is_verified INTEGER DEFAULT 0,
                    verification_code TEXT,
                    verification_code_expires_at TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cur.execute("PRAGMA table_info(users)")
            existing_user_cols = {row[1] for row in cur.fetchall()}
            if "is_verified" not in existing_user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
            if "verification_code" not in existing_user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN verification_code TEXT")
            if "verification_code_expires_at" not in existing_user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN verification_code_expires_at TEXT")
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
                            # Without these the column default marks every parked
                            # source 'operational', so the health grid reads 65/65.
                            s_health = s.get("health_status") or ("operational" if s_active else "unknown")
                            s_detail = s.get("status_detail")
                            s_created = datetime.now(timezone.utc).isoformat()
                            cur.execute("""
                                INSERT OR IGNORE INTO sources (id, name, state, county, base_url, adapter_type, selectors_config, is_active, health_status, status_detail, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (s_id, s_name, s_state, s_county, s_url, s_adapter, s_selectors, s_active, s_health, s_detail, s_created))
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
        clean_q = (query or "").strip()
        if self.supabase:
            try:
                if not clean_q:
                    # When query is empty or whitespace-only, return most recent rows
                    snapshots_res = self.supabase.table("snapshots").select(
                        "id, document_id, version, cleaned_text, crawled_at, documents(title, pdf_url, source_id, sources(name, state))",
                        count="exact"
                    ).order("crawled_at", desc=True).limit(limit).execute()

                    diffs_res = self.supabase.table("diffs").select(
                        "id, document_id, diff_payload, added_clauses_count, removed_clauses_count, generated_at, documents(title, pdf_url, sources(name, state))",
                        count="exact"
                    ).order("generated_at", desc=True).limit(limit).execute()
                else:
                    # limit() must precede text_search(): the builder returned by
                    # text_search has no limit(), and the resulting AttributeError
                    # was being swallowed into the SQLite fallback, so search
                    # silently returned nothing in production.
                    # type=plain uses plainto_tsquery, which accepts arbitrary user
                    # input; to_tsquery rejects a phrase like "off street parking".
                    snapshots_res = self.supabase.table("snapshots").select(
                        "id, document_id, version, cleaned_text, crawled_at, documents(title, pdf_url, source_id, sources(name, state))",
                        count="exact"
                    ).limit(limit).text_search(
                        "search_vector", clean_q, options={"type": "plain"}
                    ).execute()

                    diffs_res = self.supabase.table("diffs").select(
                        "id, document_id, diff_payload, added_clauses_count, removed_clauses_count, generated_at, documents(title, pdf_url, sources(name, state))",
                        count="exact"
                    ).limit(limit).text_search(
                        "diff_vector", clean_q, options={"type": "plain"}
                    ).execute()

                total_snaps = snapshots_res.count if snapshots_res.count is not None else len(snapshots_res.data or [])
                total_diffs = diffs_res.count if diffs_res.count is not None else len(diffs_res.data or [])
                return {
                    "snapshots": snapshots_res.data or [],
                    "diffs": diffs_res.data or [],
                    "total_snapshots": total_snaps,
                    "total_diffs": total_diffs,
                }
            except Exception as e:
                logger.error(f"Supabase search error: {e}")

        # SQLite Search Implementation
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            if not clean_q:
                # Search Snapshots - most recent without text filter
                cur.execute("""
                    SELECT s.id, s.document_id, s.version, s.cleaned_text, s.crawled_at, s.ocr_applied,
                           d.title as doc_title, d.pdf_url as doc_url,
                           src.name as source_name, src.state as source_state, src.county as source_county
                    FROM snapshots s
                    JOIN documents d ON s.document_id = d.id
                    LEFT JOIN sources src ON d.source_id = src.id
                    ORDER BY s.crawled_at DESC
                    LIMIT ?
                """, (limit,))
                snap_rows = cur.fetchall()

                # Search Diffs - most recent without text filter
                cur.execute("""
                    SELECT df.id, df.document_id, df.diff_payload, df.added_clauses_count, df.removed_clauses_count, df.generated_at,
                           d.title as doc_title, d.pdf_url as doc_url,
                           src.name as source_name, src.state as source_state, src.county as source_county
                    FROM diffs df
                    JOIN documents d ON df.document_id = d.id
                    LEFT JOIN sources src ON d.source_id = src.id
                    ORDER BY df.generated_at DESC
                    LIMIT ?
                """, (limit,))
                diff_rows = cur.fetchall()
            else:
                like_q = f"%{clean_q}%"
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
                """, (like_q, limit))
                snap_rows = cur.fetchall()

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
                """, (like_q, limit))
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

            if not clean_q:
                cur.execute("SELECT COUNT(*) FROM snapshots")
                total_snapshots_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM diffs")
                total_diffs_count = cur.fetchone()[0]
            else:
                total_snapshots_count = len(formatted_snaps)
                total_diffs_count = len(formatted_diffs)

            return {
                "snapshots": formatted_snaps,
                "diffs": formatted_diffs,
                "total_snapshots": total_snapshots_count,
                "total_diffs": total_diffs_count,
            }

    def record_subscription(
        self,
        external_sub_id: str,
        plan_id: str,
        status: str = "active",
        user_email: Optional[str] = None,
        subscriber_name: Optional[str] = None,
        next_billing_at: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Records or updates a user subscription from PayPal/Stripe.

        Webhooks arrive out of order and later events (a cancellation, say) carry
        less detail than the activation did, so a NULL in an update must not wipe
        a name, user ID, or billing date we already know.
        """
        import uuid
        sub_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO subscriptions (
                    id, user_id, user_email, subscriber_name, external_subscription_id,
                    plan_id, status, next_billing_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_subscription_id) DO UPDATE SET
                    status          = excluded.status,
                    user_id         = COALESCE(excluded.user_id, subscriptions.user_id),
                    user_email      = COALESCE(excluded.user_email, subscriptions.user_email),
                    subscriber_name = COALESCE(excluded.subscriber_name, subscriptions.subscriber_name),
                    plan_id         = COALESCE(excluded.plan_id, subscriptions.plan_id),
                    next_billing_at = COALESCE(excluded.next_billing_at, subscriptions.next_billing_at),
                    updated_at      = excluded.updated_at
            """, (sub_id, user_id, user_email, subscriber_name, external_sub_id,
                  plan_id, status, next_billing_at, now_iso, now_iso))
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

    def record_webhook_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        result: str = "processed",
        event_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        subscriber_name: Optional[str] = None,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """Stores a received PayPal webhook, processed or rejected.

        Rejected deliveries are recorded too - when live webhooks start failing,
        the stored payload and reason are the only way to see why.
        """
        import uuid
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO webhook_events (
                    id, event_id, event_type, subscription_id, subscriber_name,
                    amount, currency, result, error_detail, payload, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    result       = excluded.result,
                    error_detail = excluded.error_detail
            """, (
                str(uuid.uuid4()),
                event_id or str(uuid.uuid4()),
                event_type,
                subscription_id,
                subscriber_name,
                amount,
                currency,
                result,
                error_detail,
                json.dumps(payload)[:20000],
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

    def list_webhook_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent webhook deliveries, newest first."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT ?", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def start_crawl_run(self) -> str:
        """Inserts a row with status='running' and started_at=now. Returns the run id."""
        import uuid
        run_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        if self.supabase:
            try:
                res = self.supabase.table("crawl_runs").insert({
                    "id": run_id,
                    "started_at": now_iso,
                    "status": "running",
                }).execute()
                if res.data:
                    return str(res.data[0].get("id", run_id))
                return run_id
            except Exception as e:
                logger.error(f"Supabase start crawl run error: {e}")

        # SQLite Fallback
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO crawl_runs (id, started_at, status)
                VALUES (?, ?, ?)
            """, (run_id, now_iso, "running"))
            conn.commit()

        return run_id

    def finish_crawl_run(
        self,
        run_id: str,
        status: str,
        total_sources: int = 0,
        sources_succeeded: int = 0,
        sources_failed: int = 0,
        documents_found: int = 0,
        diffs_created: int = 0,
        error_logs: Optional[Any] = None,
        sources_skipped: int = 0,
        skipped_sources: Optional[Any] = None,
    ) -> None:
        """Updates a crawl run row with finished_at=now and the given counts.

        Status must be 'completed', 'failed', or 'partial_failure'.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_errors = error_logs if error_logs is not None else []
        json_errors = json.dumps(payload_errors) if not isinstance(payload_errors, str) else payload_errors

        if self.supabase:
            try:
                logs_payload = payload_errors if not isinstance(payload_errors, str) else json.loads(payload_errors)
                self.supabase.table("crawl_runs").update({
                    "finished_at": now_iso,
                    "status": status,
                    "total_sources": total_sources,
                    "sources_succeeded": sources_succeeded,
                    "sources_failed": sources_failed,
                    "sources_skipped": sources_skipped,
                    "documents_found": documents_found,
                    "diffs_created": diffs_created,
                    "error_logs": logs_payload,
                }).eq("id", run_id).execute()
                return
            except Exception as e:
                logger.error(f"Supabase finish crawl run error: {e}")

        # SQLite Fallback
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE crawl_runs SET
                    finished_at = ?,
                    status = ?,
                    total_sources = ?,
                    sources_succeeded = ?,
                    sources_failed = ?,
                    sources_skipped = ?,
                    documents_found = ?,
                    diffs_created = ?,
                    error_logs = ?
                WHERE id = ?
            """, (
                now_iso,
                status,
                total_sources,
                sources_succeeded,
                sources_failed,
                sources_skipped,
                documents_found,
                diffs_created,
                json_errors,
                run_id,
            ))
            conn.commit()

    def get_active_crawl_run(self, max_age_hours: float = 2.0) -> Optional[Dict[str, Any]]:
        """Returns the currently active crawl run with status='running', if any.

        If a running crawl is older than max_age_hours (default 2.0 hours), it is treated
        as dead/abandoned and automatically marked as 'failed' so it does not permanently
        block subsequent runs with 409.
        """
        now = datetime.now(timezone.utc)
        candidate: Optional[Dict[str, Any]] = None

        if self.supabase:
            try:
                res = self.supabase.table("crawl_runs").select("*").eq("status", "running").order("started_at", desc=True).limit(1).execute()
                if res.data:
                    candidate = res.data[0]
            except Exception as e:
                logger.error(f"Supabase get_active_crawl_run error: {e}")

        if candidate is None:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM crawl_runs WHERE status = 'running' ORDER BY started_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    candidate = dict(row)

        if not candidate:
            return None

        # Check for stale / abandoned run
        started_at_str = candidate.get("started_at")
        if started_at_str:
            try:
                started_dt = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
                age_seconds = (now - started_dt).total_seconds()
                if age_seconds > max_age_hours * 3600:
                    age_h = round(age_seconds / 3600, 2)
                    logger.warning(
                        f"Active crawl run {candidate.get('id')} has been running for {age_h}h "
                        f"(threshold {max_age_hours}h). Marking as abandoned/failed."
                    )
                    self.finish_crawl_run(
                        run_id=candidate["id"],
                        status="failed",
                        total_sources=candidate.get("total_sources") or 0,
                        sources_succeeded=candidate.get("sources_succeeded") or 0,
                        sources_failed=candidate.get("sources_failed") or 0,
                        documents_found=candidate.get("documents_found") or 0,
                        diffs_created=candidate.get("diffs_created") or 0,
                        error_logs=[{"error": f"Crawl abandoned: process did not complete within {max_age_hours} hours."}],
                    )
                    return None
            except Exception as parse_err:
                logger.warning(f"Error parsing started_at '{started_at_str}' for crawl run: {parse_err}")

        return candidate

    def get_latest_crawl_run(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent crawl run."""
        row_dict = None
        if self.supabase:
            try:
                res = self.supabase.table("crawl_runs").select("*").order("started_at", desc=True).limit(1).execute()
                if res.data:
                    row_dict = res.data[0]
            except Exception as e:
                logger.error(f"Supabase get_latest_crawl_run error: {e}")

        if not row_dict:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    row_dict = dict(row)

        if row_dict:
            if "sources_skipped" not in row_dict or row_dict["sources_skipped"] is None:
                total = row_dict.get("total_sources") or 41
                row_dict["sources_skipped"] = max(0, 65 - total)
        return row_dict

    def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: Optional[str] = None,
        trial_days: int = 14,
        is_verified: int = 0,
        verification_code: Optional[str] = None,
        verification_code_expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a new customer user with email verification status."""
        import uuid
        from datetime import datetime, timezone, timedelta

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        trial_started_at = now.isoformat() if is_verified else None
        trial_ends_at = (now + timedelta(days=trial_days)).isoformat() if is_verified else None
        now_iso = now.isoformat()
        norm_email = (email or "").strip().lower()

        if self.supabase:
            try:
                res = self.supabase.table("users").insert({
                    "id": user_id,
                    "email": norm_email,
                    "password_hash": password_hash,
                    "full_name": full_name,
                    "trial_started_at": trial_started_at,
                    "trial_ends_at": trial_ends_at,
                    "is_active": 1,
                    "is_verified": is_verified,
                    "verification_code": verification_code,
                    "verification_code_expires_at": verification_code_expires_at,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Supabase create user error: {e}")

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (
                    id, email, password_hash, full_name,
                    trial_started_at, trial_ends_at, is_active,
                    is_verified, verification_code, verification_code_expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, norm_email, password_hash, full_name,
                trial_started_at, trial_ends_at, 1,
                is_verified, verification_code, verification_code_expires_at,
                now_iso, now_iso
            ))
            conn.commit()

        return {
            "id": user_id,
            "email": norm_email,
            "full_name": full_name,
            "trial_started_at": trial_started_at,
            "trial_ends_at": trial_ends_at,
            "is_active": 1,
            "is_verified": is_verified,
            "verification_code": verification_code,
            "verification_code_expires_at": verification_code_expires_at,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    def set_verification_code(self, email: str, code: str, expires_at: str) -> bool:
        """Updates user's confirmation code and expiration."""
        from datetime import datetime, timezone
        norm_email = (email or "").strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()

        if self.supabase:
            try:
                res = self.supabase.table("users").update({
                    "verification_code": code,
                    "verification_code_expires_at": expires_at,
                    "updated_at": now_iso,
                }).eq("email", norm_email).execute()
                if res.data:
                    return True
            except Exception as e:
                logger.error(f"Supabase set_verification_code error: {e}")

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE users SET
                    verification_code = ?,
                    verification_code_expires_at = ?,
                    updated_at = ?
                WHERE LOWER(email) = LOWER(?)
            """, (code, expires_at, now_iso, norm_email))
            conn.commit()
            return cur.rowcount > 0

    def verify_user_email(self, email: str, code: str, trial_days: int = 14) -> Dict[str, Any]:
        """Validates confirmation code and activates 14-day free trial upon confirmation."""
        from datetime import datetime, timezone, timedelta
        norm_email = (email or "").strip().lower()
        user = self.get_user_by_email(norm_email)
        if not user:
            return {"success": False, "error": "user_not_found"}

        if user.get("is_verified", 0) == 1:
            return {"success": True, "already_verified": True, "user": user}

        stored_code = (user.get("verification_code") or "").strip()
        input_code = (code or "").strip()

        if not stored_code or stored_code != input_code:
            return {"success": False, "error": "invalid_code"}

        now = datetime.now(timezone.utc)
        expires_str = user.get("verification_code_expires_at")
        if expires_str:
            try:
                expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                if now > expires_at:
                    return {"success": False, "error": "code_expired"}
            except Exception:
                pass

        now_iso = now.isoformat()
        trial_ends_iso = (now + timedelta(days=trial_days)).isoformat()

        if self.supabase:
            try:
                self.supabase.table("users").update({
                    "is_verified": 1,
                    "verification_code": None,
                    "verification_code_expires_at": None,
                    "trial_started_at": now_iso,
                    "trial_ends_at": trial_ends_iso,
                    "updated_at": now_iso,
                }).eq("email", norm_email).execute()
                updated_user = self.get_user_by_email(norm_email)
                return {"success": True, "user": updated_user}
            except Exception as e:
                logger.error(f"Supabase verify_user_email error: {e}")
                return {"success": False, "error": str(e)}

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE users SET
                    is_verified = 1,
                    verification_code = NULL,
                    verification_code_expires_at = NULL,
                    trial_started_at = ?,
                    trial_ends_at = ?,
                    updated_at = ?
                WHERE LOWER(email) = LOWER(?)
            """, (now_iso, trial_ends_iso, now_iso, norm_email))
            conn.commit()

        updated_user = self.get_user_by_email(norm_email)
        return {"success": True, "user": updated_user}

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves a customer user by email address."""
        norm_email = (email or "").strip().lower()
        if not norm_email:
            return None

        if self.supabase:
            try:
                res = self.supabase.table("users").select("*").eq("email", norm_email).limit(1).execute()
                if res.data:
                    return res.data[0]
                return None
            except Exception as e:
                logger.error(f"Supabase get_user_by_email error: {e}")

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?) LIMIT 1", (norm_email,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a customer user by UUID."""
        if not user_id:
            return None

        if self.supabase:
            try:
                res = self.supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
                if res.data:
                    return res.data[0]
                return None
            except Exception as e:
                logger.error(f"Supabase get_user_by_id error: {e}")

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_user_access_status(self, email_or_user_id: str) -> Dict[str, Any]:
        """Calculates customer access entitlement (active trial vs paid subscription)."""
        import math
        from datetime import datetime, timezone

        if not email_or_user_id:
            return {"has_access": False, "reason": "unauthenticated"}

        user = self.get_user_by_email(email_or_user_id)
        if not user:
            user = self.get_user_by_id(email_or_user_id)

        if not user:
            return {"has_access": False, "reason": "user_not_found"}

        if not user.get("is_active", 1):
            return {"has_access": False, "reason": "account_disabled"}

        if not user.get("is_verified", 0):
            return {"has_access": False, "reason": "unverified", "user_email": user.get("email"), "user_id": user.get("id")}

        now = datetime.now(timezone.utc)
        trial_ends_str = user.get("trial_ends_at")
        trial_active = False
        days_remaining = 0

        if trial_ends_str:
            try:
                trial_ends = datetime.fromisoformat(trial_ends_str.replace("Z", "+00:00"))
                if trial_ends > now:
                    trial_active = True
                    delta = trial_ends - now
                    days_remaining = max(0, math.ceil(delta.total_seconds() / 86400))
            except Exception as e:
                logger.warning(f"Error parsing trial_ends_at for user {user.get('email')}: {e}")

        if trial_active:
            return {
                "has_access": True,
                "reason": "trial",
                "trial_active": True,
                "trial_days_remaining": days_remaining,
                "trial_ends_at": trial_ends_str,
                "user_email": user.get("email"),
                "user_id": user.get("id"),
            }

        # Check active subscriptions in DB
        norm_email = user.get("email", "").strip().lower()
        sub = None

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM subscriptions
                WHERE (LOWER(user_email) = LOWER(?) OR (user_id IS NOT NULL AND user_id = ?))
                  AND status IN ('active', 'completed')
                ORDER BY updated_at DESC LIMIT 1
            """, (norm_email, str(user.get("id"))))
            row = cur.fetchone()
            if row:
                sub = dict(row)

        if sub:
            next_bill_str = sub.get("next_billing_at")
            sub_active = True
            if next_bill_str:
                try:
                    next_bill = datetime.fromisoformat(next_bill_str.replace("Z", "+00:00"))
                    # If current time is after next billing, consider grace period
                    if now > next_bill and (now - next_bill).total_seconds() > 172800:
                        sub_active = False
                except Exception as e:
                    logger.warning(f"Error parsing next_billing_at for {norm_email}: {e}")

            if sub_active:
                return {
                    "has_access": True,
                    "reason": "active_subscription",
                    "plan_id": sub.get("plan_id"),
                    "external_subscription_id": sub.get("external_subscription_id"),
                    "next_billing_at": next_bill_str,
                    "user_email": user.get("email"),
                    "user_id": user.get("id"),
                }

        return {
            "has_access": False,
            "reason": "trial_expired",
            "trial_ends_at": trial_ends_str,
            "user_email": user.get("email"),
            "user_id": user.get("id"),
        }

