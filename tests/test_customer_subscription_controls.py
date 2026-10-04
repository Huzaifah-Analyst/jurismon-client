"""Tests for Customer Subscription Controls: Pause, Resume, Cancel, Webhooks, Access Gating & Parity.

Validates:
- Pause subscription: calls PayPal suspend, marks status paused, sets access_until
- Resume subscription: calls PayPal activate, marks status active, sets resumed_at
- Cancel subscription: calls PayPal cancel, marks status cancelled, sets access_until
- PayPal failure: local state completely unchanged (no writes)
- Invalid transitions: 409 conflict
- Access semantics: paused inside paid period -> has_access true ('paused_access_until')
- Access semantics: cancelled after access_until -> has_access false ('cancelled_expired')
- Token isolation: another customer cannot touch or alter someone else's subscription
- Authentication enforcement: unauthenticated requests return 401
- Webhook resume disambiguation: ACTIVATED on paused subscription handled as resume, not new signup
- Webhook idempotency: repeated delivery produces consistent state
- Clean GET /api/account/subscription for users without subscriptions
"""

import os
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as main
from api.auth import create_customer_token, get_password_hash
from db.repository import Repository


class TestCustomerSubscriptionControls(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jurismon_sub_test_")
        self.test_db = os.path.join(self._tmp, "test_controls.db")
        self._saved_repo = main.repo
        self.repo = Repository(db_path=self.test_db)
        main.repo = self.repo
        self.client = TestClient(main.app)

        # Create primary customer Alice
        pw_hash = get_password_hash("Password123!")
        self.alice = self.repo.create_user(
            email="alice@example.com",
            password_hash=pw_hash,
            full_name="Alice Smith",
            is_verified=1,
        )
        self.repo.activate_user_trial("alice@example.com", trial_days=14)
        self.alice_token = create_customer_token(user_id=self.alice["id"], email=self.alice["email"])
        self.alice_headers = {"Authorization": f"Bearer {self.alice_token}"}

        # Create second customer Bob for token isolation tests
        self.bob = self.repo.create_user(
            email="bob@example.com",
            password_hash=pw_hash,
            full_name="Bob Jones",
            is_verified=1,
        )
        self.bob_token = create_customer_token(user_id=self.bob["id"], email=self.bob["email"])
        self.bob_headers = {"Authorization": f"Bearer {self.bob_token}"}

        # Seed sample searchable document
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
            title="Commercial Zoning Code",
            pdf_url="https://austin.gov/code.pdf",
        )
        self.repo.create_snapshot(
            document_id=doc["id"],
            version=1,
            content_hash="hash123",
            raw_text="Raw text",
            cleaned_text="Commercial zoning setback requirement: 25 feet minimum front yard setback.",
        )

    def tearDown(self):
        main.repo = self._saved_repo
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _setup_alice_subscription(self, status="active", next_billing_days=30):
        now = datetime.now(timezone.utc)
        next_billing = (now + timedelta(days=next_billing_days)).isoformat()
        return self.repo.record_subscription(
            external_sub_id="I-ALICE-12345",
            plan_id="professional_monthly",
            status=status,
            user_email="alice@example.com",
            subscriber_name="Alice Smith",
            next_billing_at=next_billing,
            user_id=self.alice["id"],
        )

    # 1. Pause Subscription Workflow
    def test_pause_subscription_calls_paypal_sets_status_and_access_until(self):
        self._setup_alice_subscription(status="active", next_billing_days=25)

        with patch.object(main.paypal_provider, "suspend_subscription", return_value=True) as mock_suspend:
            res = self.client.post("/api/account/subscription/pause", headers=self.alice_headers)
            self.assertEqual(res.status_code, 200)
            mock_suspend.assert_called_once_with(
                "I-ALICE-12345", reason="Customer requested pause via self-service portal"
            )

        data = res.json()
        self.assertEqual(data["status"], "paused")
        self.assertTrue(data.get("access_until"))
        self.assertTrue(data.get("paused_at"))

        # Verify database record
        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "paused")
        self.assertIsNotNone(sub["paused_at"])
        self.assertEqual(sub["access_until"], sub["next_billing_at"])

    # 2. Resume Subscription Workflow
    def test_resume_subscription_calls_paypal_sets_status_active_and_resumed_at(self):
        self._setup_alice_subscription(status="active", next_billing_days=20)
        self.repo.set_subscription_paused(
            "I-ALICE-12345",
            paused_at=datetime.now(timezone.utc).isoformat(),
            access_until=(datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
        )

        with patch.object(main.paypal_provider, "activate_subscription", return_value=True) as mock_activate:
            res = self.client.post("/api/account/subscription/resume", headers=self.alice_headers)
            self.assertEqual(res.status_code, 200)
            mock_activate.assert_called_once_with(
                "I-ALICE-12345", reason="Customer requested resume via self-service portal"
            )

        data = res.json()
        self.assertEqual(data["status"], "active")
        self.assertTrue(data.get("resumed_at"))

        # Verify database record
        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "active")
        self.assertIsNotNone(sub["resumed_at"])

    # 3. Cancel Subscription Workflow
    def test_cancel_subscription_calls_paypal_sets_status_cancelled_and_access_until(self):
        self._setup_alice_subscription(status="active", next_billing_days=15)

        with patch.object(main.paypal_provider, "cancel_subscription", return_value=True) as mock_cancel:
            res = self.client.post(
                "/api/account/subscription/cancel",
                headers=self.alice_headers,
                json={"reason": "Project completed successfully"},
            )
            self.assertEqual(res.status_code, 200)
            mock_cancel.assert_called_once_with(
                "I-ALICE-12345", reason="Project completed successfully"
            )

        data = res.json()
        self.assertEqual(data["status"], "cancelled")
        self.assertTrue(data.get("cancelled_at"))
        self.assertTrue(data.get("access_until"))

        # Verify database record
        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "cancelled")
        self.assertEqual(sub["cancel_reason"], "Project completed successfully")
        self.assertEqual(sub["access_until"], sub["next_billing_at"])

    # 4. PayPal Call Fails -> Local State Completely Unchanged
    def test_paypal_failure_leaves_local_state_completely_unchanged(self):
        self._setup_alice_subscription(status="active", next_billing_days=30)

        # 4a. Pause failure
        with patch.object(main.paypal_provider, "suspend_subscription", return_value=False):
            res = self.client.post("/api/account/subscription/pause", headers=self.alice_headers)
            self.assertEqual(res.status_code, 502)

        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "active")
        self.assertIsNone(sub.get("paused_at"))

        # 4b. Resume failure
        self.repo.set_subscription_paused(
            "I-ALICE-12345",
            paused_at=datetime.now(timezone.utc).isoformat(),
            access_until=(datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
        )
        with patch.object(main.paypal_provider, "activate_subscription", return_value=False):
            res = self.client.post("/api/account/subscription/resume", headers=self.alice_headers)
            self.assertEqual(res.status_code, 502)

        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "paused")
        self.assertIsNone(sub.get("resumed_at"))

        # 4c. Cancel failure
        self.repo.set_subscription_resumed("I-ALICE-12345", resumed_at=datetime.now(timezone.utc).isoformat())
        with patch.object(main.paypal_provider, "cancel_subscription", return_value=False):
            res = self.client.post("/api/account/subscription/cancel", headers=self.alice_headers, json={"reason": "Test"})
            self.assertEqual(res.status_code, 502)

        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "active")
        self.assertIsNone(sub.get("cancelled_at"))

    # 5. Invalid Transitions Return 409
    def test_invalid_transitions_return_409(self):
        self._setup_alice_subscription(status="active")

        # 5a. Cannot resume an already active subscription
        res = self.client.post("/api/account/subscription/resume", headers=self.alice_headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("already active", res.json()["detail"].lower())

        # Pause it
        self.repo.set_subscription_paused(
            "I-ALICE-12345",
            paused_at=datetime.now(timezone.utc).isoformat(),
            access_until=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        )

        # 5b. Cannot pause an already paused subscription
        res = self.client.post("/api/account/subscription/pause", headers=self.alice_headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("already paused", res.json()["detail"].lower())

        # Cancel it
        self.repo.set_subscription_cancelled(
            "I-ALICE-12345",
            cancelled_at=datetime.now(timezone.utc).isoformat(),
            access_until=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        )

        # 5c. Cannot pause a cancelled subscription
        res = self.client.post("/api/account/subscription/pause", headers=self.alice_headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("cancelled", res.json()["detail"].lower())

        # 5d. Cannot resume a cancelled subscription
        res = self.client.post("/api/account/subscription/resume", headers=self.alice_headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("cancelled", res.json()["detail"].lower())

        # 5e. Cannot cancel an already cancelled subscription
        res = self.client.post("/api/account/subscription/cancel", headers=self.alice_headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("already cancelled", res.json()["detail"].lower())

    # 6. Access Check: Paused Inside Period -> has_access True
    def test_access_check_paused_inside_period_has_access_true(self):
        self._setup_alice_subscription(status="active")
        future_deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        self.repo.set_subscription_paused(
            "I-ALICE-12345",
            paused_at=datetime.now(timezone.utc).isoformat(),
            access_until=future_deadline,
        )

        # Verify entitlement status directly
        access = self.repo.get_user_access_status("alice@example.com")
        self.assertTrue(access["has_access"])
        self.assertEqual(access["reason"], "paused_access_until")
        self.assertEqual(access["access_until"], future_deadline)

        # Search gating must grant full access
        res = self.client.get("/api/search?q=setback", headers=self.alice_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["is_gated"])
        self.assertIn("25 feet minimum front yard", data["items"][0]["full"])

    # 7. Access Check: Cancelled After access_until -> has_access False
    def test_access_check_cancelled_after_access_until_has_access_false(self):
        # Expire user's initial trial
        past_trial = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        with self.repo._connect() as conn:
            conn.execute("UPDATE users SET trial_ends_at = ? WHERE email = ?", (past_trial, "alice@example.com"))
            conn.commit()

        self._setup_alice_subscription(status="active")
        past_deadline = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.repo.set_subscription_cancelled(
            "I-ALICE-12345",
            cancelled_at=(datetime.now(timezone.utc) - timedelta(days=32)).isoformat(),
            access_until=past_deadline,
        )

        # Verify entitlement status directly
        access = self.repo.get_user_access_status("alice@example.com")
        self.assertFalse(access["has_access"])
        self.assertEqual(access["reason"], "cancelled_expired")

        # Search gating must lock content
        res = self.client.get("/api/search?q=setback", headers=self.alice_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_gated"])
        self.assertEqual(data["gate_reason"], "cancelled_expired")
        self.assertTrue(data["items"][0]["is_locked"])

    # 8. Customer Token Isolation: Token Scoping Enforced
    def test_another_customers_token_cannot_touch_this_subscription(self):
        self._setup_alice_subscription(status="active")

        # Bob attempts to pause, resume, or cancel Alice's subscription
        # Because Bob has no subscription, Bob gets 404
        res = self.client.post("/api/account/subscription/pause", headers=self.bob_headers)
        self.assertEqual(res.status_code, 404)

        res = self.client.post("/api/account/subscription/resume", headers=self.bob_headers)
        self.assertEqual(res.status_code, 404)

        res = self.client.post("/api/account/subscription/cancel", headers=self.bob_headers)
        self.assertEqual(res.status_code, 404)

        # Alice's subscription must remain active and completely untouched
        alice_sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(alice_sub["status"], "active")
        self.assertIsNone(alice_sub.get("paused_at"))
        self.assertIsNone(alice_sub.get("cancelled_at"))

    # 9. Unauthenticated Requests Rejected
    def test_unauthenticated_requests_are_rejected(self):
        endpoints = [
            ("get", "/api/account/subscription"),
            ("post", "/api/account/subscription/pause"),
            ("post", "/api/account/subscription/resume"),
            ("post", "/api/account/subscription/cancel"),
        ]
        for method, ep in endpoints:
            if method == "get":
                res = self.client.get(ep)
            else:
                res = self.client.post(ep)
            self.assertEqual(res.status_code, 401, f"Endpoint {ep} must require authentication")

    # 10. Webhook: ACTIVATED on Paused Subscription Handled as Resume
    def test_activated_webhook_on_previously_paused_subscription_handled_as_resume(self):
        self._setup_alice_subscription(status="active")
        self.repo.set_subscription_paused(
            "I-ALICE-12345",
            paused_at=datetime.now(timezone.utc).isoformat(),
            access_until=(datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        )

        sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(sub["status"], "paused")

        # PayPal webhook delivery of BILLING.SUBSCRIPTION.ACTIVATED
        webhook_payload = {
            "id": "WH-ACTIVATE-RESUME-001",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-ALICE-12345",
                "plan_id": "professional_monthly",
                "status": "ACTIVE",
                "billing_info": {
                    "next_billing_time": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                },
                "subscriber": {
                    "email_address": "alice@example.com",
                    "name": {"given_name": "Alice", "surname": "Smith"}
                }
            }
        }

        with patch.object(main.paypal_provider, "verify_webhook", return_value=True):
            res = self.client.post("/api/webhooks/paypal", json=webhook_payload)
            self.assertEqual(res.status_code, 200)

        # Verify resumed locally
        updated_sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(updated_sub["status"], "active")
        self.assertIsNotNone(updated_sub["resumed_at"])

    # 11. Webhook: BILLING.SUBSCRIPTION.SUSPENDED Marks Subscription Paused
    def test_suspended_webhook_marks_subscription_paused(self):
        self._setup_alice_subscription(status="active", next_billing_days=22)

        webhook_payload = {
            "id": "WH-SUSPEND-002",
            "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
            "resource": {
                "id": "I-ALICE-12345",
                "plan_id": "professional_monthly",
                "status": "SUSPENDED",
                "subscriber": {
                    "email_address": "alice@example.com",
                    "name": {"given_name": "Alice", "surname": "Smith"}
                }
            }
        }

        with patch.object(main.paypal_provider, "verify_webhook", return_value=True):
            res = self.client.post("/api/webhooks/paypal", json=webhook_payload)
            self.assertEqual(res.status_code, 200)

        updated_sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(updated_sub["status"], "paused")
        self.assertIsNotNone(updated_sub["paused_at"])
        self.assertIsNotNone(updated_sub["access_until"])

    # 12. Webhook Idempotency: Duplicate Delivery Produces Consistent State
    def test_duplicate_webhook_delivery_is_idempotent(self):
        self._setup_alice_subscription(status="active", next_billing_days=18)

        webhook_payload = {
            "id": "WH-DUP-003",
            "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
            "resource": {
                "id": "I-ALICE-12345",
                "plan_id": "professional_monthly",
                "status": "SUSPENDED",
                "subscriber": {
                    "email_address": "alice@example.com",
                    "name": {"given_name": "Alice", "surname": "Smith"}
                }
            }
        }

        with patch.object(main.paypal_provider, "verify_webhook", return_value=True):
            # Delivery 1
            res1 = self.client.post("/api/webhooks/paypal", json=webhook_payload)
            self.assertEqual(res1.status_code, 200)

            # Delivery 2 (duplicate)
            res2 = self.client.post("/api/webhooks/paypal", json=webhook_payload)
            self.assertEqual(res2.status_code, 200)

        updated_sub = self.repo.get_subscription_by_external_id("I-ALICE-12345")
        self.assertEqual(updated_sub["status"], "paused")

    # 13. GET /api/account/subscription Endpoint Clean Handling
    def test_get_account_subscription_endpoint(self):
        # 13a. For user with NO subscription -> clean 200 response, not 500!
        res_bob = self.client.get("/api/account/subscription", headers=self.bob_headers)
        self.assertEqual(res_bob.status_code, 200)
        data_bob = res_bob.json()
        self.assertFalse(data_bob["has_subscription"])
        self.assertEqual(data_bob["status"], "none")
        self.assertIsNone(data_bob["external_subscription_id"])

        # 13b. For user WITH active subscription
        self._setup_alice_subscription(status="active", next_billing_days=25)
        res_alice = self.client.get("/api/account/subscription", headers=self.alice_headers)
        self.assertEqual(res_alice.status_code, 200)
        data_alice = res_alice.json()
        self.assertTrue(data_alice["has_subscription"])
        self.assertEqual(data_alice["status"], "active")
        self.assertEqual(data_alice["external_subscription_id"], "I-ALICE-12345")
        self.assertTrue(data_alice["access"]["has_access"])

    # 14. Customer Account HTML Page Route
    def test_serve_account_page(self):
        res = self.client.get("/account")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Customer Account", res.text)
        self.assertIn("state-signed-out", res.text)
        self.assertIn("state-active", res.text)
        self.assertIn("state-paused", res.text)
        self.assertIn("cancel-modal", res.text)
