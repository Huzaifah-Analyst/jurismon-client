"""Comprehensive Unit & API Integration Tests for Day 4: DB, Search API & PayPal."""

import os
import shutil
import tempfile
import unittest
import json
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from db.repository import Repository
from api.main import app
from api.payments.paypal_provider import PayPalProvider


class TestDatabaseRepository(unittest.TestCase):

    def setUp(self):
        # Temp dir keeps scratch databases out of the repository root.
        self._tmpdir = tempfile.mkdtemp(prefix="jurismon_test_")
        self.test_db = os.path.join(self._tmpdir, "test_jurismon.db")
        self.repo = Repository(db_path=self.test_db)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_upsert_source_and_retrieve(self):
        source_data = {
            "id": "test-austin",
            "name": "City of Austin Zoning",
            "base_url": "https://austin.gov/zoning",
            "adapter_type": "custom",
        }
        res = self.repo.upsert_source(source_data)
        self.assertIsNotNone(res)

        sources = self.repo.get_active_sources()
        self.assertTrue(any(s["name"] == "City of Austin Zoning" for s in sources))

    def test_create_snapshot_and_search(self):
        # Create document
        doc = self.repo.get_or_create_document(
            source_id="test-austin",
            title="Ordinance No. 2026-99: Setback Requirements",
            pdf_url="https://austin.gov/docs/ord99.pdf"
        )
        self.assertIsNotNone(doc)

        # Create snapshot
        snap = self.repo.create_snapshot(
            document_id=doc["id"],
            version=1,
            content_hash="hash123",
            raw_text="Raw text",
            cleaned_text="§ 12-4. Front yard setback shall be a minimum of 30 feet in R-1 districts."
        )
        self.assertIsNotNone(snap)

        # Create diff
        diff_payload = {
            "strategy_used": "section",
            "total_added": 1,
            "total_removed": 0,
            "total_modified": 1,
            "summary": "1 clause(s) modified",
            "modified": [{"identifier": "§ 12-4", "old_text": "25 feet", "new_text": "30 feet"}]
        }
        self.repo.save_diff(
            document_id=doc["id"],
            previous_snapshot_id=None,
            current_snapshot_id=snap["id"],
            diff_payload=diff_payload
        )

        # Search for "setback"
        results = self.repo.search_snapshots_and_diffs(query="setback")
        self.assertGreater(len(results["snapshots"]), 0)
        self.assertIn("30 feet", results["snapshots"][0]["cleaned_text"])

    def test_search_empty_query_returns_recent_rows(self):
        """search_snapshots_and_diffs('') returns the most recent rows, not an empty list, with rows present."""
        doc = self.repo.get_or_create_document(
            source_id="test-empty-q",
            title="Ordinance Empty Q",
            pdf_url="https://austin.gov/docs/empty_q.pdf"
        )
        self.repo.create_snapshot(
            document_id=doc["id"],
            version=1,
            content_hash="hash_empty_1",
            raw_text="Raw text",
            cleaned_text="Zoning amendment text for empty query test."
        )
        results = self.repo.search_snapshots_and_diffs(query="")
        self.assertGreater(len(results["snapshots"]), 0)
        self.assertIn("Zoning amendment", results["snapshots"][0]["cleaned_text"])

    def test_search_whitespace_query_returns_recent_rows(self):
        """search_snapshots_and_diffs('   ') behaves identically to empty query."""
        doc = self.repo.get_or_create_document(
            source_id="test-ws-q",
            title="Ordinance WS Q",
            pdf_url="https://austin.gov/docs/ws_q.pdf"
        )
        self.repo.create_snapshot(
            document_id=doc["id"],
            version=1,
            content_hash="hash_ws_1",
            raw_text="Raw text",
            cleaned_text="Zoning amendment text for whitespace query test."
        )
        results = self.repo.search_snapshots_and_diffs(query="   ")
        self.assertGreater(len(results["snapshots"]), 0)

    def test_record_and_list_subscriptions(self):
        sub = self.repo.record_subscription(
            external_sub_id="I-BW452GLLEP1G",
            plan_id="P-MONTHLY-2026",
            status="active",
            user_email="subscriber@example.com"
        )
        self.assertEqual(sub["status"], "active")

        subs = self.repo.list_subscriptions()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["user_email"], "subscriber@example.com")

    def test_crawl_run_recording_and_counts_stored(self):
        """A run is recorded and the counts/status are properly stored."""
        run_id = self.repo.start_crawl_run()
        self.assertIsNotNone(run_id)

        with self.repo._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status, started_at FROM crawl_runs WHERE id=?", (run_id,))
            row = cur.fetchone()
            self.assertEqual(row[0], "running")
            self.assertIsNotNone(row[1])

        self.repo.finish_crawl_run(
            run_id=run_id,
            status="completed",
            total_sources=41,
            sources_succeeded=40,
            sources_failed=1,
            documents_found=120,
            diffs_created=3,
            error_logs=[{"source": "test", "error": "timeout"}],
        )

        with self.repo._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, total_sources, sources_succeeded, sources_failed, documents_found, diffs_created, error_logs, finished_at FROM crawl_runs WHERE id=?",
                (run_id,),
            )
            row = cur.fetchone()
            self.assertEqual(row[0], "completed")
            self.assertEqual(row[1], 41)
            self.assertEqual(row[2], 40)
            self.assertEqual(row[3], 1)
            self.assertEqual(row[4], 120)
            self.assertEqual(row[5], 3)
            self.assertIn("timeout", row[6])
            self.assertIsNotNone(row[7])

    def test_run_crawler_records_run_and_stores_counts(self):
        """scripts.run_crawler.main records a crawl run and stores counts."""
        from scripts import run_crawler

        fake_sources = [
            {"id": "s1", "name": "Source 1", "base_url": "https://s1.test", "adapter_type": "custom", "is_active": True},
            {"id": "s2", "name": "Source 2", "base_url": "https://s2.test", "adapter_type": "custom", "is_active": False},
        ]
        mock_result = MagicMock(success=True, documents=[])
        mock_adapter = MagicMock()
        mock_adapter.crawl.return_value = mock_result

        with patch("scripts.run_crawler.load_sites_config", return_value=fake_sources), \
             patch("scripts.run_crawler.Repository", return_value=self.repo), \
             patch("scripts.run_crawler.get_adapter", return_value=mock_adapter), \
             patch("scripts.run_crawler.send_crawl_report"):
            run_crawler.main()

        with self.repo._connect() as conn:
            row = conn.execute("SELECT status, total_sources, sources_succeeded, sources_failed FROM crawl_runs").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "completed")
            self.assertEqual(row[1], 1)
            self.assertEqual(row[2], 1)
            self.assertEqual(row[3], 0)

    def test_run_crawler_crash_records_run_as_failed(self):
        """A crash during run_crawler still closes the run with status='failed'."""
        from scripts import run_crawler

        fake_sources = [
            {"id": "s1", "name": "Source 1", "base_url": "https://s1.test", "adapter_type": "custom", "is_active": True},
        ]

        def crashing_crawl(*args, **kwargs):
            raise KeyboardInterrupt("Simulated crash")

        with patch("scripts.run_crawler.load_sites_config", return_value=fake_sources), \
             patch("scripts.run_crawler.Repository", return_value=self.repo), \
             patch("scripts.run_crawler.get_adapter", side_effect=crashing_crawl), \
             patch("scripts.run_crawler.send_crawl_report"):
            with self.assertRaises(KeyboardInterrupt):
                run_crawler.main()

        with self.repo._connect() as conn:
            row = conn.execute("SELECT status, total_sources, sources_failed FROM crawl_runs").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "failed")
            self.assertEqual(row[1], 1)


class TestPayPalProvider(unittest.TestCase):

    def test_process_webhook_event_activated(self):
        provider = PayPalProvider()
        fake_payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-TEST12345",
                "plan_id": "P-PRO-PLAN",
                "subscriber": {
                    "email_address": "client_buyer@test.com"
                }
            }
        }
        event = provider.process_webhook_event(fake_payload)
        self.assertEqual(event["status"], "active")
        self.assertEqual(event["subscription_id"], "I-TEST12345")
        self.assertEqual(event["email"], "client_buyer@test.com")

    def test_process_webhook_event_cancelled(self):
        provider = PayPalProvider()
        fake_payload = {
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {
                "id": "I-TEST12345",
            }
        }
        event = provider.process_webhook_event(fake_payload)
        self.assertEqual(event["status"], "cancelled")

    def test_process_webhook_event_extracts_custom_id(self):
        provider = PayPalProvider()
        fake_payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-TEST-CID",
                "custom_id": "user-uuid-1234",
                "subscriber": {"email_address": "buyer@test.com"}
            }
        }
        event = provider.process_webhook_event(fake_payload)
        self.assertEqual(event["custom_id"], "user-uuid-1234")
        self.assertEqual(event["subscription_id"], "I-TEST-CID")

    def test_create_subscription_payload_includes_custom_id(self):
        provider = PayPalProvider(client_id="cid", client_secret="sec")
        with patch.object(provider, "_get_access_token", return_value="fake_token"), \
             patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": "I-SUB-123",
                "status": "APPROVAL_PENDING",
                "links": [{"rel": "approve", "href": "https://paypal.com/checkout?id=123"}],
            }
            res = provider.create_subscription(
                plan_id="P-TEST-PLAN",
                return_url="https://site.test/return",
                cancel_url="https://site.test/cancel",
                subscriber_email="work@firm.com",
                custom_id="user-uuid-999",
            )
            self.assertIsNotNone(res)
            self.assertEqual(res.id, "I-SUB-123")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            self.assertEqual(payload["custom_id"], "user-uuid-999")
            self.assertEqual(payload["subscriber"]["email_address"], "work@firm.com")


class TestPayPalWebhookVerification(unittest.TestCase):
    """Regression cover for the webhook signature path, which no test reached."""

    def test_verify_webhook_fails_closed_without_webhook_id(self):
        provider = PayPalProvider(webhook_id="")
        self.assertFalse(provider.verify_webhook({}, b"{}"))

    def test_verify_webhook_parses_body_and_calls_paypal(self):
        """Guards the body-parsing path; a bad json reference broke every delivery."""
        provider = PayPalProvider(
            client_id="cid", client_secret="secret", webhook_id="WH-TEST"
        )

        token_res = MagicMock()
        token_res.json.return_value = {"access_token": "fake-token"}
        token_res.raise_for_status.return_value = None

        verify_res = MagicMock()
        verify_res.json.return_value = {"verification_status": "SUCCESS"}
        verify_res.raise_for_status.return_value = None

        headers = {
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://api.paypal.com/cert",
            "paypal-transmission-id": "tx-1",
            "paypal-transmission-sig": "sig-1",
            "paypal-transmission-time": "2026-09-28T00:00:00Z",
        }
        body = json.dumps({"event_type": "BILLING.SUBSCRIPTION.ACTIVATED"}).encode()

        with patch("api.payments.paypal_provider.requests.post",
                   side_effect=[token_res, verify_res]) as mock_post:
            result = provider.verify_webhook(headers, body)

        self.assertTrue(result)
        sent = mock_post.call_args_list[1].kwargs["json"]
        self.assertEqual(sent["webhook_id"], "WH-TEST")
        self.assertEqual(
            sent["webhook_event"]["event_type"], "BILLING.SUBSCRIPTION.ACTIVATED"
        )

    def test_verify_webhook_returns_false_when_paypal_rejects(self):
        provider = PayPalProvider(
            client_id="cid", client_secret="secret", webhook_id="WH-TEST"
        )
        token_res = MagicMock()
        token_res.json.return_value = {"access_token": "fake-token"}
        token_res.raise_for_status.return_value = None

        verify_res = MagicMock()
        verify_res.json.return_value = {"verification_status": "FAILURE"}
        verify_res.raise_for_status.return_value = None

        with patch("api.payments.paypal_provider.requests.post",
                   side_effect=[token_res, verify_res]):
            self.assertFalse(provider.verify_webhook({}, b"{}"))


class TestPayPalMode(unittest.TestCase):
    """PAYPAL_MODE was previously swallowed by a truthy default argument."""

    def setUp(self):
        self._saved = os.environ.get("PAYPAL_MODE")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("PAYPAL_MODE", None)
        else:
            os.environ["PAYPAL_MODE"] = self._saved

    def test_live_mode_from_environment(self):
        os.environ["PAYPAL_MODE"] = "live"
        provider = PayPalProvider()
        self.assertEqual(provider.mode, "live")
        self.assertEqual(provider.base_url, "https://api-m.paypal.com")

    def test_sandbox_mode_from_environment(self):
        os.environ["PAYPAL_MODE"] = "sandbox"
        provider = PayPalProvider()
        self.assertEqual(provider.base_url, "https://api-m.sandbox.paypal.com")

    def test_explicit_argument_overrides_environment(self):
        os.environ["PAYPAL_MODE"] = "live"
        provider = PayPalProvider(mode="sandbox")
        self.assertEqual(provider.mode, "sandbox")


class TestAdminAuthentication(unittest.TestCase):
    """Admin login previously compared plaintext against an 'admin123' default."""

    def setUp(self):
        from api.auth import get_password_hash
        import api.auth as auth_module
        self.auth = auth_module
        self._saved_hash = auth_module.ADMIN_PASSWORD_HASH
        auth_module.ADMIN_PASSWORD_HASH = get_password_hash("s3cure-admin-pass")

    def tearDown(self):
        self.auth.ADMIN_PASSWORD_HASH = self._saved_hash

    def test_correct_credentials_accepted(self):
        self.assertTrue(
            self.auth.authenticate_admin(self.auth.ADMIN_EMAIL, "s3cure-admin-pass")
        )

    def test_wrong_password_rejected(self):
        self.assertFalse(
            self.auth.authenticate_admin(self.auth.ADMIN_EMAIL, "admin123")
        )

    def test_wrong_email_rejected(self):
        self.assertFalse(
            self.auth.authenticate_admin("attacker@evil.com", "s3cure-admin-pass")
        )

    def test_login_disabled_when_hash_not_configured(self):
        self.auth.ADMIN_PASSWORD_HASH = ""
        self.assertFalse(
            self.auth.authenticate_admin(self.auth.ADMIN_EMAIL, "admin123")
        )

    def test_password_over_bcrypt_limit_rejected(self):
        self.assertFalse(
            self.auth.authenticate_admin(self.auth.ADMIN_EMAIL, "a" * 73)
        )


class TestFastAPIEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_search_endpoint(self):
        response = self.client.get("/api/search?q=ordinance")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["query"], "ordinance")
        self.assertIn("results", data)

    def test_sources_endpoint(self):
        from api.auth import create_access_token, ADMIN_EMAIL
        token = create_access_token({"sub": ADMIN_EMAIL})
        response = self.client.get("/api/sources", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sources", data)

    def test_sources_anonymous_hides_operational_breakdown(self):
        response = self.client.get("/api/sources")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ["operational_count", "cloudflare_count", "dead_links_count", "sources"]:
            self.assertNotIn(key, data)
        self.assertEqual(data["count"], data["total_configured"])

    def test_sources_customer_hides_operational_breakdown(self):
        from api.auth import create_customer_token
        token = create_customer_token("cust_test_id", "counsel@firm.com")
        response = self.client.get("/api/sources", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ["operational_count", "cloudflare_count", "dead_links_count", "sources"]:
            self.assertNotIn(key, data)
        self.assertEqual(data["count"], data["total_configured"])

    def test_sources_admin_sees_full_breakdown(self):
        from api.auth import create_access_token, ADMIN_EMAIL
        token = create_access_token({"sub": ADMIN_EMAIL})
        response = self.client.get("/api/sources", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ["operational_count", "cloudflare_count", "dead_links_count"]:
            self.assertIn(key, data)
        self.assertIn("sources", data)
        self.assertIsInstance(data["sources"], list)
        self.assertGreater(len(data["sources"]), 0)

    def test_customer_token_at_admin_address_is_not_admin(self):
        from api.auth import create_customer_token, ADMIN_EMAIL
        token = create_customer_token("cust_admin_spoof", ADMIN_EMAIL)
        response = self.client.get("/api/sources", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("operational_count", data)

    def test_register_rejects_admin_email(self):
        from api.auth import ADMIN_EMAIL
        from api.main import repo
        res = self.client.post("/api/auth/register", json={
            "email": ADMIN_EMAIL,
            "password": "ValidPassword123!",
            "full_name": "Admin Impersonator",
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "This email address is reserved.")
        self.assertIsNone(repo.get_user_by_email(ADMIN_EMAIL))

    def test_customer_token_with_admin_email_cannot_access_admin_via_me(self):
        """A customer token created with ADMIN_EMAIL must NOT return role 'admin' on GET /api/auth/me,
        and login must reject the reserved admin email."""
        from api.auth import ADMIN_EMAIL, create_customer_token
        login_res = self.client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "Password123!",
        })
        self.assertEqual(login_res.status_code, 400)
        self.assertEqual(login_res.json()["detail"], "This email address is reserved.")

        token = create_customer_token("fake-user-id", ADMIN_EMAIL)
        me_res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_res.status_code, 404)
        self.assertEqual(me_res.json()["detail"], "User not found.")

    def test_paypal_webhook_endpoint(self):
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-PAYPAL-WEBHOOK-TEST",
                "plan_id": "P-PRO",
                "subscriber": {
                    "email_address": "paypal_user@test.com"
                }
            }
        }
        with patch("api.main.paypal_provider.verify_webhook", return_value=True):
            response = self.client.post("/api/webhooks/paypal", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_paypal_webhook_rejects_unverified_delivery(self):
        """An unsigned webhook must be rejected, not trusted."""
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {"id": "I-FORGED", "plan_id": "P-PRO"},
        }
        with patch("api.main.paypal_provider.verify_webhook", return_value=False):
            response = self.client.post("/api/webhooks/paypal", json=payload)
        self.assertEqual(response.status_code, 400)

    def test_search_with_empty_query(self):
        response = self.client.get("/api/search")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertIn("results", data)

    def test_serve_frontend_pages(self):
        # Test index search page
        idx_res = self.client.get("/")
        self.assertEqual(idx_res.status_code, 200)
        self.assertIn("JurisMon", idx_res.text)

        # Test admin dashboard page
        adm_res = self.client.get("/admin")
        self.assertEqual(adm_res.status_code, 200)
        self.assertIn("JurisMon Admin", adm_res.text)

    def test_branding_seo_and_crawlers(self):
        robots_res = self.client.get("/robots.txt")
        self.assertEqual(robots_res.status_code, 200)
        self.assertIn("Disallow: /admin", robots_res.text)
        self.assertIn("https://jurismon.com/sitemap.xml", robots_res.text)

        sitemap_res = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap_res.status_code, 200)
        self.assertIn("https://jurismon.com/", sitemap_res.text)

        idx_res = self.client.get("/")
        self.assertEqual(idx_res.status_code, 200)
        self.assertIn("og:image", idx_res.text)
        self.assertIn("canonical", idx_res.text)

        adm_res = self.client.get("/admin")
        self.assertEqual(adm_res.status_code, 200)
        self.assertIn("noindex", adm_res.text)
        self.assertNotIn("og:image", adm_res.text)

    def test_admin_crawl_endpoints(self):
        """B4: Unauthenticated POST is rejected; a second POST while one is running returns 409;
        status endpoint returns the latest run."""
        from api.auth import create_access_token, create_customer_token, ADMIN_EMAIL
        admin_token = create_access_token({"sub": ADMIN_EMAIL})
        cust_token = create_customer_token("any-user-id", "customer@test.com")

        # 1. Unauthenticated POST rejected
        res_no_auth = self.client.post("/api/admin/crawl/run")
        self.assertIn(res_no_auth.status_code, (401, 403))

        # 2. Customer token rejected (403)
        res_cust = self.client.post(
            "/api/admin/crawl/run",
            headers={"Authorization": f"Bearer {cust_token}"},
        )
        self.assertEqual(res_cust.status_code, 403)

        # 3. Status endpoint without auth rejected
        res_stat_no_auth = self.client.get("/api/admin/crawl/status")
        self.assertIn(res_stat_no_auth.status_code, (401, 403))

        # 4. First run started with admin token
        with patch("api.main._run_background_crawl"):
            res_start = self.client.post(
                "/api/admin/crawl/run",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_start.status_code, 200)
            data = res_start.json()
            self.assertEqual(data["status"], "started")
            self.assertIn("crawl_run_id", data)

            # 5. Status endpoint returns current run
            res_status = self.client.get(
                "/api/admin/crawl/status",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_status.status_code, 200)
            status_data = res_status.json()
            self.assertEqual(status_data["status"], "running")

            # 6. Second POST while one is running returns 409 Conflict
            res_second = self.client.post(
                "/api/admin/crawl/run",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_second.status_code, 409)
            self.assertIn("already running", res_second.json()["detail"])

            # Clean up test run so database is clean for subsequent runs
            from api.main import repo
            repo.finish_crawl_run(
                data["crawl_run_id"],
                status="completed",
                total_sources=0,
                sources_succeeded=0,
                sources_failed=0,
                documents_found=0,
                diffs_created=0,
            )

    def test_stale_crawl_run_auto_heals_and_allows_new_run(self):
        """B1 test: a stale 'running' row (>2 hours) does not block a new run; a fresh one returns 409."""
        from datetime import datetime, timezone, timedelta
        from api.main import repo
        from api.auth import create_access_token, ADMIN_EMAIL
        from unittest.mock import patch

        admin_token = create_access_token({"sub": ADMIN_EMAIL})

        # Insert a stale run that started 3 hours ago
        stale_started = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        stale_run_id = "test-stale-run-uuid"
        with repo._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO crawl_runs (id, started_at, status)
                VALUES (?, ?, 'running')
            """, (stale_run_id, stale_started))
            conn.commit()

        # 1. repo.get_active_crawl_run() should detect stale run, mark it failed, and return None
        active = repo.get_active_crawl_run(max_age_hours=2.0)
        self.assertIsNone(active)

        # Confirm the stale row was updated to 'failed' with abandonment error note
        with repo._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status, error_logs FROM crawl_runs WHERE id = ?", (stale_run_id,))
            row = cur.fetchone()
            self.assertEqual(row[0], "failed")
            self.assertIn("abandoned", row[1])

        # 2. Since stale run is auto-healed, /api/admin/crawl/run must NOT return 409
        with patch("api.main._run_background_crawl"):
            res_new = self.client.post(
                "/api/admin/crawl/run",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_new.status_code, 200)
            new_run_id = res_new.json()["crawl_run_id"]

            # 3. Fresh run is now active (< 2h), so a concurrent run must return 409 Conflict
            res_concurrent = self.client.post(
                "/api/admin/crawl/run",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_concurrent.status_code, 409)
            self.assertIn("already running", res_concurrent.json()["detail"])

            # Clean up new test run
            repo.finish_crawl_run(new_run_id, status="completed")

    def test_unauthenticated_checkout_refused(self):
        """B3/B5: Unauthenticated checkout request is refused with 401."""
        response = self.client.post("/api/subscriptions/create", json={"plan": "professional_monthly"})
        self.assertEqual(response.status_code, 401)

    def test_create_subscription_sends_custom_id(self):
        """B1/B5: Authenticated checkout passes user's UUID as custom_id to PayPal."""
        from api.auth import create_customer_token
        from api.payments.paypal_provider import SubscriptionRequest

        user_id = "test-customer-uuid-42"
        user_email = "lawyer@firm.com"
        token = create_customer_token(user_id=user_id, email=user_email)

        mock_sub = SubscriptionRequest(
            id="I-NEW-SUB",
            status="APPROVAL_PENDING",
            approval_url="https://www.sandbox.paypal.com/checkoutnow?token=I-NEW-SUB",
            plan_id="P-4KS041180N5953043M743TVI",
        )

        with patch("api.main.paypal_provider.client_id", "mock-cid"), \
             patch("api.main.paypal_provider.create_subscription", return_value=mock_sub) as mock_create:
            res = self.client.post(
                "/api/subscriptions/create",
                headers={"Authorization": f"Bearer {token}"},
                json={"plan": "professional_monthly"},
            )
            self.assertEqual(res.status_code, 200)
            mock_create.assert_called_once()
            kwargs = mock_create.call_args[1]
            self.assertEqual(kwargs.get("custom_id"), user_id)
            self.assertEqual(kwargs.get("subscriber_email"), user_email)

    def test_webhook_resolves_by_custom_id_first(self):
        """B2/B5: Webhook resolves user by custom_id first, even if PayPal payer email differs."""
        from api.main import repo
        target_uid = "firm-user-uuid-777"
        firm_email = "firm_lead@corporate.com"
        personal_payer_email = "personal_paypal@gmail.com"

        with patch.object(repo, "get_user_by_id", return_value={"id": target_uid, "email": firm_email}), \
             patch.object(repo, "record_subscription") as mock_record, \
             patch("api.main.paypal_provider.verify_webhook", return_value=True):

            payload = {
                "id": "WH-TEST-CUSTOMID-1",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "resource": {
                    "id": "I-SUB-DIFFERENT-EMAIL",
                    "plan_id": "P-PRO",
                    "custom_id": target_uid,
                    "subscriber": {
                        "email_address": personal_payer_email
                    }
                }
            }
            res = self.client.post("/api/webhooks/paypal", json=payload)
            self.assertEqual(res.status_code, 200)
            mock_record.assert_called_once()
            record_kwargs = mock_record.call_args[1]
            self.assertEqual(record_kwargs.get("user_id"), target_uid)
            self.assertEqual(record_kwargs.get("user_email"), firm_email)

    def test_webhook_resolves_by_email_when_custom_id_absent(self):
        """B2/B5: Webhook falls back to payer email matching when custom_id is absent."""
        from api.main import repo
        fallback_uid = "fallback-user-uuid-888"
        payer_email = "legacy_user@test.com"

        with patch.object(repo, "get_user_by_email", return_value={"id": fallback_uid, "email": payer_email}), \
             patch.object(repo, "record_subscription") as mock_record, \
             patch("api.main.paypal_provider.verify_webhook", return_value=True):

            payload = {
                "id": "WH-TEST-NOCUSTOMID-1",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "resource": {
                    "id": "I-SUB-LEGACY",
                    "plan_id": "P-PRO",
                    "subscriber": {
                        "email_address": payer_email
                    }
                }
            }
            res = self.client.post("/api/webhooks/paypal", json=payload)
            self.assertEqual(res.status_code, 200)
            mock_record.assert_called_once()
            record_kwargs = mock_record.call_args[1]
            self.assertEqual(record_kwargs.get("user_id"), fallback_uid)
            self.assertEqual(record_kwargs.get("user_email"), payer_email)

    def test_admin_crawl_status_includes_sources_skipped(self):
        """C1/C2: /api/admin/crawl/status includes sources_skipped and summary."""
        from api.auth import create_access_token, ADMIN_EMAIL
        admin_token = create_access_token({"sub": ADMIN_EMAIL})

        res = self.client.get(
            "/api/admin/crawl/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("sources_skipped", data)
        self.assertIn("summary", data)
        self.assertIn("skipped", data["summary"])


class TestForgotPasswordAndReset(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        from api.main import _forgot_password_timestamps
        _forgot_password_timestamps.clear()
        self.created_emails = []

    def tearDown(self):
        from api.main import repo
        for email in self.created_emails:
            if repo.supabase:
                try:
                    repo.supabase.table("subscriptions").delete().eq("user_email", email).execute()
                    repo.supabase.table("users").delete().eq("email", email).execute()
                except Exception:
                    pass
            with repo._connect() as conn:
                conn.cursor().execute("DELETE FROM subscriptions WHERE LOWER(user_email) = LOWER(?)", (email,))
                conn.cursor().execute("DELETE FROM users WHERE LOWER(email) = LOWER(?)", (email,))
                conn.commit()

    def _unique_email(self, prefix: str = "test") -> str:
        email = f"{prefix}_{uuid.uuid4().hex[:10]}@lawfirm.com"
        self.created_emails.append(email)
        return email

    def test_forgot_password_sends_code_and_returns_200_for_known_email(self):
        """forgot-password sends code and returns 200 for known email."""
        from api.main import repo
        test_email = self._unique_email("known")
        repo.create_user(
            email=test_email,
            password_hash="mock_hash",
            is_verified=1,
        )
        with patch("api.main.mailer.send", return_value=True) as mock_send:
            res = self.client.post("/api/auth/forgot-password", json={"email": test_email})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "success")
            mock_send.assert_called_once()
            kwargs = mock_send.call_args[1]
            subject = kwargs.get("subject", "")
            self.assertIn("Reset your JurisMon password", subject)

        user = repo.get_user_by_email(test_email)
        self.assertIsNotNone(user.get("verification_code"))

    def test_forgot_password_returns_200_for_unknown_email_no_email_sent(self):
        """forgot-password returns 200 for unknown email (no email sent)."""
        unknown_email = f"nonexistent_{uuid.uuid4().hex[:10]}@lawfirm.com"
        with patch("api.main.mailer.send", return_value=True) as mock_send:
            res = self.client.post("/api/auth/forgot-password", json={"email": unknown_email})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "success")
            mock_send.assert_not_called()

    def test_forgot_password_rejects_admin_email(self):
        """forgot-password rejects ADMIN_EMAIL with 400."""
        from api.auth import ADMIN_EMAIL
        res = self.client.post("/api/auth/forgot-password", json={"email": ADMIN_EMAIL})
        self.assertEqual(res.status_code, 400)
        self.assertIn("reserved", res.json()["detail"].lower())

    def test_reset_password_with_valid_code_updates_password_and_allows_login(self):
        """reset-password with valid code updates password and allows login."""
        from api.main import repo
        from api.auth import get_password_hash
        test_email = self._unique_email("reset_success")
        old_pw = "OldPassword123!"
        new_pw = "NewSecurePassword456!"
        repo.create_user(
            email=test_email,
            password_hash=get_password_hash(old_pw),
            is_verified=1,
            verification_code="123456",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )

        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "123456",
            "new_password": new_pw,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

        # Confirm new password allows login
        login_res = self.client.post("/api/auth/login", json={
            "email": test_email,
            "password": new_pw,
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access_token", login_res.json())

    def test_unverified_user_reset_password_activates_trial_and_allows_login(self):
        """Unverified user resets password -> is_verified becomes 1 AND trial_ends_at is set 14 days out AND login succeeds."""
        from api.main import repo
        from api.auth import get_password_hash
        from datetime import datetime, timezone, timedelta
        test_email = self._unique_email("unverified_reset")
        new_pw = "BrandNewPassword789!"
        repo.create_user(
            email=test_email,
            password_hash=get_password_hash("OldPassword123!"),
            is_verified=0,
            verification_code="234567",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )

        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "234567",
            "new_password": new_pw,
        })
        self.assertEqual(res.status_code, 200)

        user = repo.get_user_by_email(test_email)
        self.assertEqual(user.get("is_verified"), 1)
        self.assertIsNotNone(user.get("trial_started_at"))
        self.assertIsNotNone(user.get("trial_ends_at"))
        trial_end = datetime.fromisoformat(user["trial_ends_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        self.assertTrue(trial_end > now + timedelta(days=13))

        login_res = self.client.post("/api/auth/login", json={
            "email": test_email,
            "password": new_pw,
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access_token", login_res.json())

    def test_verified_user_mid_trial_reset_password_trial_ends_at_unchanged(self):
        """Verified user mid-trial resets password -> trial_ends_at is UNCHANGED (not extended, not reset)."""
        from api.main import repo
        from api.auth import get_password_hash
        test_email = self._unique_email("mid_trial")
        fixed_trial_end = "2026-10-15T12:00:00+00:00"
        fixed_trial_start = "2026-10-01T12:00:00+00:00"
        user = repo.create_user(
            email=test_email,
            password_hash=get_password_hash("InitialPass123!"),
            is_verified=1,
            verification_code="345678",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )
        # Explicitly set fixed trial start and end in DB
        with repo._connect() as conn:
            conn.cursor().execute("""
                UPDATE users SET trial_started_at = ?, trial_ends_at = ? WHERE LOWER(email) = LOWER(?)
            """, (fixed_trial_start, fixed_trial_end, test_email))
            conn.commit()
        if repo.supabase:
            try:
                repo.supabase.table("users").update({
                    "trial_started_at": fixed_trial_start,
                    "trial_ends_at": fixed_trial_end,
                }).eq("email", test_email).execute()
            except Exception:
                pass

        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "345678",
            "new_password": "NewMidTrialPass123!",
        })
        self.assertEqual(res.status_code, 200)

        updated_user = repo.get_user_by_email(test_email)
        self.assertEqual(updated_user.get("trial_ends_at"), fixed_trial_end)
        self.assertEqual(updated_user.get("trial_started_at"), fixed_trial_start)

    def test_paid_subscriber_reset_password_subscription_status_unaffected(self):
        """User with active paid subscription resets password -> subscription status unaffected."""
        from api.main import repo
        from api.auth import get_password_hash
        test_email = self._unique_email("subscriber_reset")
        user = repo.create_user(
            email=test_email,
            password_hash=get_password_hash("SubPass123!"),
            is_verified=1,
            trial_days=0,
            verification_code="456789",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )
        sub_id = f"I-SUB-{user['id'][:8]}"
        repo.record_subscription(
            external_sub_id=sub_id,
            plan_id="professional_monthly",
            status="active",
            user_email=test_email,
            user_id=user["id"],
        )

        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "456789",
            "new_password": "NewSubPass456!",
        })
        self.assertEqual(res.status_code, 200)

        access = repo.get_user_access_status(user["id"])
        self.assertTrue(access["has_access"])
        self.assertEqual(access["reason"], "active_subscription")
        self.assertEqual(access["plan_id"], "professional_monthly")

    def test_reset_password_with_expired_code_returns_400(self):
        """reset-password with expired code returns 400."""
        from api.main import repo
        test_email = self._unique_email("expired")
        repo.create_user(
            email=test_email,
            password_hash="mock_hash",
            is_verified=1,
            verification_code="654321",
            verification_code_expires_at="2020-01-01T00:00:00+00:00",
        )

        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "654321",
            "new_password": "NewValidPassword123!",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("expired", res.json()["detail"].lower())

    def test_reset_password_with_wrong_code_returns_400(self):
        """reset-password with wrong code returns 400."""
        from api.main import repo
        test_email = self._unique_email("wrong_code")
        repo.create_user(
            email=test_email,
            password_hash="mock_hash",
            is_verified=1,
            verification_code="111222",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )

        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "999888",
            "new_password": "NewValidPassword123!",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid", res.json()["detail"].lower())

    def test_reset_password_enforces_min_and_max_length(self):
        """reset-password enforces >= 8 chars and <= 72 bytes."""
        from api.main import repo
        test_email = self._unique_email("length")
        repo.create_user(
            email=test_email,
            password_hash="mock_hash",
            is_verified=1,
            verification_code="123456",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )

        # Too short (< 8 chars)
        res_short = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "123456",
            "new_password": "short",
        })
        self.assertEqual(res_short.status_code, 400)
        self.assertIn("8 characters", res_short.json()["detail"])

        # Too long (> 72 bytes)
        res_long = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "123456",
            "new_password": "a" * 73,
        })
        self.assertEqual(res_long.status_code, 400)
        self.assertIn("72 bytes", res_long.json()["detail"])

    def test_old_password_fails_after_reset(self):
        """old password fails after reset."""
        from api.main import repo
        from api.auth import get_password_hash
        test_email = self._unique_email("pw_change")
        old_pw = "OriginalPass123!"
        new_pw = "UpdatedPass456!"
        repo.create_user(
            email=test_email,
            password_hash=get_password_hash(old_pw),
            is_verified=1,
            verification_code="777888",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )

        # Reset password
        res = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "777888",
            "new_password": new_pw,
        })
        self.assertEqual(res.status_code, 200)

        # Old password must now fail
        login_fail = self.client.post("/api/auth/login", json={
            "email": test_email,
            "password": old_pw,
        })
        self.assertEqual(login_fail.status_code, 401)

    def test_code_cannot_be_reused_second_time(self):
        """code cannot be reused a second time."""
        from api.main import repo
        from api.auth import get_password_hash
        test_email = self._unique_email("single_use")
        repo.create_user(
            email=test_email,
            password_hash=get_password_hash("InitPass123!"),
            is_verified=1,
            verification_code="555666",
            verification_code_expires_at="2099-01-01T00:00:00+00:00",
        )

        # First use succeeds
        res1 = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "555666",
            "new_password": "FirstReset123!",
        })
        self.assertEqual(res1.status_code, 200)

        # Second use with same code must be rejected (400)
        res2 = self.client.post("/api/auth/reset-password", json={
            "email": test_email,
            "code": "555666",
            "new_password": "SecondReset456!",
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn("invalid", res2.json()["detail"].lower())


class TestTermsAndPrivacyPages(unittest.TestCase):
    def setUp(self):
        from api.main import app
        self.client = TestClient(app)

    def test_terms_endpoint_unauthenticated_and_contains_disclaimer(self):
        """GET /terms returns 200 without auth and contains the accuracy disclaimer."""
        res = self.client.get("/terms")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        content = res.text
        self.assertIn("NOT legal advice", content)
        self.assertIn("verify", content.lower())
        self.assertIn("accuracy", content.lower())
        self.assertIn("working draft", content.lower())
        self.assertIn("october 3, 2026", content.lower())

    def test_privacy_endpoint_unauthenticated_and_names_processors(self):
        """GET /privacy returns 200 without auth and names PayPal, Supabase, and Resend."""
        res = self.client.get("/privacy")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        content = res.text
        self.assertIn("PayPal", content)
        self.assertIn("Supabase", content)
        self.assertIn("Resend", content)
        self.assertIn("15-minute", content)
        self.assertIn("localStorage", content)
        self.assertIn("working draft", content.lower())
        self.assertIn("october 3, 2026", content.lower())

    def test_sitemap_includes_terms_and_privacy(self):
        """GET /sitemap.xml includes /terms and /privacy URLs."""
        res = self.client.get("/sitemap.xml")
        self.assertEqual(res.status_code, 200)
        self.assertIn("https://jurismon.com/terms", res.text)
        self.assertIn("https://jurismon.com/privacy", res.text)

    def test_robots_txt_allows_root_and_does_not_block_terms_privacy(self):
        """GET /robots.txt allows root and does not block terms or privacy."""
        res = self.client.get("/robots.txt")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Allow: /", res.text)
        self.assertNotIn("Disallow: /terms", res.text)
        self.assertNotIn("Disallow: /privacy", res.text)

    def test_contact_email_present_and_no_placeholder(self):
        """Official contact address is present across legal pages and home without placeholder."""
        for path in ["/", "/terms", "/privacy", "/admin"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200)
            self.assertIn("support@jurismon.com", res.text)
            self.assertNotIn("(placeholder", res.text.lower())

    def test_terms_and_privacy_render_real_logo_and_no_brand_mark(self):
        """GET /terms and GET /privacy each contain /static/assets/logo.png and do NOT contain brand-mark."""
        for path in ["/terms", "/privacy"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200)
            self.assertIn("/static/assets/logo.png", res.text)
            self.assertNotIn("brand-mark", res.text)
        logo_res = self.client.get("/static/assets/logo.png")
        self.assertEqual(logo_res.status_code, 200)
        self.assertIn("image", logo_res.headers.get("content-type", ""))

    def test_admin_html_has_no_fabricated_data_or_duplicate_elements(self):
        """admin.html contains zero fabricated source names, no hardcoded source counts, and no duplicate header elements."""
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Zero fabricated source names
        fabricated_names = [
            "Timberline", "Willow Creek", "Harlow County", "Redwater County",
            "Brookhaven", "Marlow Township", "Easton Falls", "Cedar Hollow",
            "Dunmore Township", "Alder Springs"
        ]
        for name in fabricated_names:
            self.assertNotIn(name, html, f"Fabricated name '{name}' found in admin.html")

        # No hardcoded source counts or Cloudflare string
        self.assertNotIn("7 Cloudflare protected", html)
        self.assertNotIn("47/50", html)

        # No duplicate brand wordmark in header
        self.assertNotIn('<span class="brand-name">JurisMon</span>', html)

        # Exactly one logout button
        self.assertEqual(html.count('id="btn-logout"'), 1)

        # Default PayPal badge is unknown/dash, not Sandbox
        self.assertIn('id="paypal-mode">—', html)

        # Header status starts with loading indicator
        self.assertIn('id="sys-text">Loading portal status...<', html)

    def test_admin_html_auth_gate_precedes_script(self):
        """admin.html defines id='auth-gate' before the opening <script> tag."""
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        html = res.text
        gate_pos = html.find('id="auth-gate"')
        script_pos = html.find("<script")
        self.assertNotEqual(gate_pos, -1, "id='auth-gate' must exist in admin.html")
        self.assertNotEqual(script_pos, -1, "<script> tag must exist in admin.html")
        self.assertLess(gate_pos, script_pos, "id='auth-gate' must appear earlier in the document than <script>")

    def test_pages_contain_no_sample_or_fictional_data_indicators(self):
        """Assert no page served by the app contains forbidden sample or fictional data indicators."""
        forbidden_strings = ["sample data", "fictional", "dummy data", "demo data"]
        pages = ["/", "/admin", "/terms", "/privacy"]
        for page in pages:
            res = self.client.get(page)
            self.assertEqual(res.status_code, 200, f"Page {page} returned status {res.status_code}")
            page_text = res.text.lower()
            for forbidden in forbidden_strings:
                self.assertNotIn(
                    forbidden,
                    page_text,
                    f"Forbidden string '{forbidden}' found in response from '{page}'"
                )


if __name__ == "__main__":
    unittest.main()


