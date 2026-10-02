"""Tests for Customer Authentication, Email Confirmation Code, 14-Day Free Trial, Search Gating, and PayPal Auto-Verification."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as main
from db.repository import Repository


class TestCustomerAuthAndGating(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jurismon_customer_test_")
        self.test_db = os.path.join(self._tmp, "test_customer.db")
        self._saved_repo = main.repo
        self.repo = Repository(db_path=self.test_db)
        main.repo = self.repo
        self.client = TestClient(main.app)

        # Seed a test source, document, and snapshot
        self.repo.upsert_source({
            "id": "city-austin",
            "name": "City of Austin Zoning",
            "base_url": "https://austin.gov/zoning",
            "adapter_type": "custom",
            "is_active": 1,
            "health_status": "operational",
        })
        doc = self.repo.get_or_create_document(
            source_id="city-austin",
            title="Zoning Ordinance 2026",
            pdf_url="https://austin.gov/ordinance.pdf",
        )
        self.repo.create_snapshot(
            document_id=doc["id"],
            version=1,
            content_hash="hash999",
            raw_text="Raw statutory text",
            cleaned_text="§ 25-2-492. Commercial zoning setback requirements: 25 feet minimum front yard.",
        )

    def tearDown(self):
        main.repo = self._saved_repo
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _get_code(self, email: str) -> str:
        u = self.repo.get_user_by_email(email)
        return u["verification_code"] if u else ""

    def test_customer_registration_sends_code_and_verifies_trial(self):
        # Step 1: Register sends verification code
        res = self.client.post("/api/auth/register", json={
            "email": "client@jurisexample.com",
            "password": "SecurePassword123!",
            "full_name": "Test Counsel",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "verification_required")
        self.assertEqual(data["email"], "client@jurisexample.com")
        self.assertNotIn("dev_code", data)
        code = self._get_code("client@jurisexample.com")
        self.assertEqual(len(code), 6)

        # Step 2: Unverified user cannot log in
        login_unverified = self.client.post("/api/auth/login", json={
            "email": "client@jurisexample.com",
            "password": "SecurePassword123!",
        })
        self.assertEqual(login_unverified.status_code, 403)
        self.assertIn("not confirmed", login_unverified.json()["detail"])

        # Step 3: Verify code activates 14-day trial
        res_verify = self.client.post("/api/auth/verify-code", json={
            "email": "client@jurisexample.com",
            "code": code,
        })
        self.assertEqual(res_verify.status_code, 200)
        verify_data = res_verify.json()
        self.assertEqual(verify_data["status"], "verified")
        self.assertIn("access_token", verify_data)
        user = verify_data["user"]
        self.assertEqual(user["email"], "client@jurisexample.com")

        # Verify 14-day trial timestamp
        trial_ends_str = user["trial_ends_at"]
        trial_ends = datetime.fromisoformat(trial_ends_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        remaining_days = (trial_ends - now).days
        self.assertTrue(13 <= remaining_days <= 14)
        self.assertTrue(user["access"]["has_access"])
        self.assertEqual(user["access"]["reason"], "trial")

        # Step 4: Now login succeeds
        res_login = self.client.post("/api/auth/login", json={
            "email": "client@jurisexample.com",
            "password": "SecurePassword123!",
        })
        self.assertEqual(res_login.status_code, 200)
        self.assertIn("access_token", res_login.json())

    def test_customer_registration_validation(self):
        # Short password
        res = self.client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "short",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("at least 8 characters", res.json()["detail"])

        # Invalid email
        res = self.client.post("/api/auth/register", json={
            "email": "notanemail",
            "password": "ValidPassword123!",
        })
        self.assertEqual(res.status_code, 400)

        # Duplicate email on verified account
        self.client.post("/api/auth/register", json={
            "email": "dupe@example.com",
            "password": "ValidPassword123!",
        })
        self.client.post("/api/auth/verify-code", json={
            "email": "dupe@example.com",
            "code": self._get_code("dupe@example.com"),
        })
        res_dupe = self.client.post("/api/auth/register", json={
            "email": "dupe@example.com",
            "password": "ValidPassword123!",
        })
        self.assertEqual(res_dupe.status_code, 400)
        self.assertIn("already exists", res_dupe.json()["detail"])

    def test_verify_code_invalid_and_expired(self):
        self.client.post("/api/auth/register", json={
            "email": "invalidcode@test.com",
            "password": "Password123!",
        })
        code = self._get_code("invalidcode@test.com")

        # Wrong code
        res_wrong = self.client.post("/api/auth/verify-code", json={
            "email": "invalidcode@test.com",
            "code": "000000",
        })
        self.assertEqual(res_wrong.status_code, 400)
        self.assertIn("Invalid confirmation code", res_wrong.json()["detail"])

        # Expired code in DB
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        self.repo.set_verification_code("invalidcode@test.com", code, past_iso)
        res_expired = self.client.post("/api/auth/verify-code", json={
            "email": "invalidcode@test.com",
            "code": code,
        })
        self.assertEqual(res_expired.status_code, 400)
        self.assertIn("expired", res_expired.json()["detail"])

    def test_resend_code(self):
        self.client.post("/api/auth/register", json={
            "email": "resend@test.com",
            "password": "Password123!",
        })
        old_code = self._get_code("resend@test.com")
        self.assertTrue(len(old_code) == 6)

        res = self.client.post("/api/auth/resend-code", json={
            "email": "resend@test.com",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "code_resent")
        self.assertNotIn("dev_code", data)

        new_code = self._get_code("resend@test.com")
        self.assertTrue(len(new_code) == 6)
        self.assertNotEqual(old_code, new_code)

        # Old code must now be rejected
        old_res = self.client.post("/api/auth/verify-code", json={
            "email": "resend@test.com",
            "code": old_code,
        })
        self.assertEqual(old_res.status_code, 400)
        self.assertIn("Invalid confirmation code", old_res.json()["detail"])

        # New code must verify successfully
        new_res = self.client.post("/api/auth/verify-code", json={
            "email": "resend@test.com",
            "code": new_code,
        })
        self.assertEqual(new_res.status_code, 200)
        self.assertEqual(new_res.json()["status"], "verified")

    def test_get_current_customer_profile(self):
        self.client.post("/api/auth/register", json={
            "email": "profile@test.com",
            "password": "ProfilePassword123!",
            "full_name": "Profile User",
        })
        ver = self.client.post("/api/auth/verify-code", json={
            "email": "profile@test.com",
            "code": self._get_code("profile@test.com"),
        }).json()
        token = ver["access_token"]

        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["email"], "profile@test.com")
        self.assertTrue(data["access"]["has_access"])
        self.assertEqual(data["access"]["reason"], "trial")

        # Unauthorized when no token provided
        res_anon = self.client.get("/api/auth/me")
        self.assertEqual(res_anon.status_code, 401)

    def test_search_gating_unauthenticated_teaser(self):
        # Public visitor search
        res = self.client.get("/api/search?q=setback")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_gated"])
        self.assertEqual(data["gate_reason"], "unauthenticated")
        self.assertGreater(len(data["items"]), 0)
        # Teaser item has masked full text
        self.assertTrue(data["items"][0].get("is_locked"))
        self.assertIn("locked", data["items"][0]["full"].lower())

    def test_search_gating_active_trial_full_access(self):
        self.client.post("/api/auth/register", json={
            "email": "active_trial@test.com",
            "password": "TrialPassword123!",
        })
        ver = self.client.post("/api/auth/verify-code", json={
            "email": "active_trial@test.com",
            "code": self._get_code("active_trial@test.com"),
        }).json()
        token = ver["access_token"]

        res = self.client.get("/api/search?q=setback", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["is_gated"])
        self.assertEqual(data["access"]["reason"], "trial")
        # Full text is NOT locked
        self.assertFalse(data["items"][0].get("is_locked", False))
        self.assertIn("25 feet minimum front yard", data["items"][0]["full"])

    def test_search_gating_expired_trial_blocked(self):
        self.client.post("/api/auth/register", json={
            "email": "expired@test.com",
            "password": "ExpiredPassword123!",
        })
        ver = self.client.post("/api/auth/verify-code", json={
            "email": "expired@test.com",
            "code": self._get_code("expired@test.com"),
        }).json()
        token = ver["access_token"]
        user_id = ver["user"]["id"]

        # Fast-forward trial expiration in DB to the past
        past_iso = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        with self.repo._connect() as conn:
            conn.execute("UPDATE users SET trial_ends_at = ? WHERE id = ?", (past_iso, user_id))

        # Search should now be blocked
        res = self.client.get("/api/search?q=setback", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_gated"])
        self.assertEqual(data["gate_reason"], "trial_expired")
        self.assertTrue(data["items"][0].get("is_locked"))

    def test_paypal_webhook_auto_unblocks_expired_user(self):
        self.client.post("/api/auth/register", json={
            "email": "subscriber@test.com",
            "password": "SubscriberPass123!",
        })
        ver = self.client.post("/api/auth/verify-code", json={
            "email": "subscriber@test.com",
            "code": self._get_code("subscriber@test.com"),
        }).json()
        token = ver["access_token"]
        user_id = ver["user"]["id"]

        # Expire user trial
        past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with self.repo._connect() as conn:
            conn.execute("UPDATE users SET trial_ends_at = ? WHERE id = ?", (past_iso, user_id))

        # Confirm user is currently gated
        res_gated = self.client.get("/api/search?q=setback", headers={"Authorization": f"Bearer {token}"})
        self.assertTrue(res_gated.json()["is_gated"])

        # PayPal webhook arrives confirming payment
        webhook_payload = {
            "id": "WH-AUTO-UNBLOCK-TEST",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-PAYPAL-SUB-999",
                "plan_id": "P-755622228P129234DNK55PJI",  # JurisMon Professional $49/mo
                "subscriber": {
                    "email_address": "subscriber@test.com",
                    "name": {"given_name": "Subscriber", "surname": "Counsel"},
                },
                "billing_info": {
                    "next_billing_time": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                },
            },
        }

        with patch("api.main.paypal_provider.verify_webhook", return_value=True):
            webhook_res = self.client.post("/api/webhooks/paypal", json=webhook_payload)
        self.assertEqual(webhook_res.status_code, 200)

        # Immediate automated verification: customer searches again without any manual intervention
        res_unlocked = self.client.get("/api/search?q=setback", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_unlocked.status_code, 200)
        data = res_unlocked.json()
        self.assertFalse(data["is_gated"])
        self.assertEqual(data["access"]["reason"], "active_subscription")
        self.assertFalse(data["items"][0].get("is_locked", False))
        self.assertIn("25 feet minimum front yard", data["items"][0]["full"])

    def test_favicon_endpoint(self):
        res = self.client.get("/favicon.ico")
        self.assertEqual(res.status_code, 200)
        self.assertIn("image", res.headers.get("content-type", ""))
