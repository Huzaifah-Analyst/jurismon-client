"""Comprehensive Unit & API Integration Tests for Day 4: DB, Search API & PayPal."""

import os
import shutil
import tempfile
import unittest
import json
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
        if me_res.status_code == 200:
            self.assertNotEqual(me_res.json().get("role"), "admin")
        else:
            self.assertEqual(me_res.status_code, 404)

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


if __name__ == "__main__":
    unittest.main()
