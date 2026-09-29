"""Tests for the admin dashboard's data endpoints.

The dashboard previously rendered hardcoded sample subscribers, plans and
webhook deliveries, so none of this was ever served by the API. These tests
cover the endpoints it now reads, with particular attention to revenue
arithmetic and to cancellation, where being wrong means either billing a
customer who cancelled or telling the operator a cancellation happened when
PayPal never received it.
"""

import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as main
import api.auth as auth
from api.auth import get_password_hash
from db.repository import Repository

MONTHLY = "P-755622228P129234DNK55PJI"
ANNUAL = "P-4KS38013TS839013TNK55PTA"


def activation(sub_id, plan_id, given="Mara", surname="Ellison",
               email="mara@example.com", next_billing="2026-10-29T10:00:00Z"):
    return {
        "id": f"WH-{sub_id}",
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "resource": {
            "id": sub_id,
            "plan_id": plan_id,
            "subscriber": {
                "email_address": email,
                "name": {"given_name": given, "surname": surname},
            },
            "billing_info": {"next_billing_time": next_billing},
        },
    }


class AdminTestCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jurismon_admin_")
        self._saved_repo = main.repo
        main.repo = Repository(db_path=os.path.join(self._tmp, "admin.db"))

        self._saved_hash = auth.ADMIN_PASSWORD_HASH
        auth.ADMIN_PASSWORD_HASH = get_password_hash("admin-pass")

        self.client = TestClient(main.app)
        token = self.client.post(
            "/api/admin/login",
            json={"email": auth.ADMIN_EMAIL, "password": "admin-pass"},
        ).json()["access_token"]
        self.auth = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        main.repo = self._saved_repo
        auth.ADMIN_PASSWORD_HASH = self._saved_hash
        shutil.rmtree(self._tmp, ignore_errors=True)

    def send(self, payload, verified=True):
        with patch.object(main.paypal_provider, "verify_webhook", return_value=verified):
            return self.client.post("/api/webhooks/paypal", json=payload)


class TestPlanCatalogue(AdminTestCase):

    def test_plans_endpoint_returns_the_configured_catalogue(self):
        data = self.client.get("/api/admin/plans", headers=self.auth).json()

        ids = {p["paypal"] for p in data["plans"]}
        self.assertIn(MONTHLY, ids)
        self.assertIn(ANNUAL, ids)
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["trial_days"], 14)

    def test_plan_subscriber_counts_reflect_active_subscriptions(self):
        self.send(activation("I-A1", MONTHLY))
        self.send(activation("I-A2", MONTHLY, "Juno", "Reyes", "juno@example.com"))
        self.send(activation("I-A3", ANNUAL, "Hollis", "Park", "hollis@example.com"))

        plans = {p["paypal"]: p for p in
                 self.client.get("/api/admin/plans", headers=self.auth).json()["plans"]}

        self.assertEqual(plans[MONTHLY]["subscribers"], 2)
        self.assertEqual(plans[ANNUAL]["subscribers"], 1)

    def test_cancelled_subscribers_do_not_count_toward_a_plan(self):
        self.send(activation("I-B1", MONTHLY))
        self.send({
            "id": "WH-B1-cancel",
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {"id": "I-B1", "plan_id": MONTHLY},
        })

        plans = {p["paypal"]: p for p in
                 self.client.get("/api/admin/plans", headers=self.auth).json()["plans"]}
        self.assertEqual(plans[MONTHLY]["subscribers"], 0)

    def test_plans_require_admin_authentication(self):
        # No bearer token at all is 401; a valid token for the wrong user is 403.
        self.assertEqual(self.client.get("/api/admin/plans").status_code, 401)


class TestSubscriberList(AdminTestCase):

    def test_subscriber_carries_name_plan_and_billing_date(self):
        self.send(activation("I-C1", MONTHLY))

        subs = self.client.get("/api/admin/subscribers", headers=self.auth).json()["subscribers"]
        self.assertEqual(len(subs), 1)

        s = subs[0]
        self.assertEqual(s["name"], "Mara Ellison")
        self.assertEqual(s["email"], "mara@example.com")
        self.assertEqual(s["plan_name"], "Professional")
        self.assertEqual(s["plan_price"], 49.0)
        self.assertEqual(s["plan_interval"], "month")
        self.assertEqual(s["paypal"], "I-C1")
        self.assertTrue(s["next_billing_at"].startswith("2026-10-29"))

    def test_business_subscriber_name_is_used_when_no_personal_name(self):
        self.send({
            "id": "WH-C2",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-C2", "plan_id": MONTHLY,
                "subscriber": {"email_address": "ops@firm.example",
                               "business_name": "Alder & Finch LLP"},
            },
        })
        subs = self.client.get("/api/admin/subscribers", headers=self.auth).json()["subscribers"]
        self.assertEqual(subs[0]["name"], "Alder & Finch LLP")

    def test_unknown_plan_still_lists_the_subscriber(self):
        """A webhook for a retired plan must not make a paying customer vanish."""
        self.send(activation("I-C3", "P-SOME-OLD-PLAN"))

        subs = self.client.get("/api/admin/subscribers", headers=self.auth).json()["subscribers"]
        self.assertEqual(len(subs), 1)
        self.assertIsNone(subs[0]["plan"])
        self.assertEqual(subs[0]["plan_name"], "Unrecognised plan")
        self.assertIsNone(subs[0]["plan_price"])

    def test_later_events_do_not_erase_known_details(self):
        """A cancellation carries no name or billing date; they must survive."""
        self.send(activation("I-C4", MONTHLY))
        self.send({
            "id": "WH-C4-cancel",
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {"id": "I-C4"},
        })

        s = self.client.get("/api/admin/subscribers", headers=self.auth).json()["subscribers"][0]
        self.assertEqual(s["status"], "cancelled")
        self.assertEqual(s["name"], "Mara Ellison")
        self.assertEqual(s["plan_name"], "Professional")


class TestRevenueArithmetic(AdminTestCase):

    def test_mrr_converts_annual_plans_to_a_monthly_figure(self):
        self.send(activation("I-D1", MONTHLY))
        self.send(activation("I-D2", MONTHLY, "Juno", "Reyes", "juno@example.com"))
        self.send(activation("I-D3", ANNUAL, "Hollis", "Park", "hollis@example.com"))

        o = self.client.get("/api/admin/overview", headers=self.auth).json()

        self.assertAlmostEqual(o["mrr"], 49 + 49 + 468 / 12, places=2)
        self.assertAlmostEqual(o["arr"], o["mrr"] * 12, places=2)

    def test_cancelled_subscribers_are_excluded_from_mrr(self):
        self.send(activation("I-E1", MONTHLY))
        self.send(activation("I-E2", MONTHLY, "Lin", "Shaw", "lin@example.com"))
        self.send({
            "id": "WH-E2-cancel",
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {"id": "I-E2"},
        })

        o = self.client.get("/api/admin/overview", headers=self.auth).json()
        self.assertAlmostEqual(o["mrr"], 49.0, places=2)
        self.assertEqual(o["active_subscribers"], 1)
        self.assertEqual(o["cancelled_subscribers"], 1)

    def test_unknown_plan_contributes_nothing_rather_than_crashing(self):
        self.send(activation("I-F1", "P-RETIRED"))
        o = self.client.get("/api/admin/overview", headers=self.auth).json()
        self.assertEqual(o["mrr"], 0)
        self.assertEqual(o["active_subscribers"], 1)

    def test_suspended_counts_as_past_due(self):
        self.send(activation("I-G1", MONTHLY))
        self.send({
            "id": "WH-G1-susp",
            "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
            "resource": {"id": "I-G1"},
        })
        o = self.client.get("/api/admin/overview", headers=self.auth).json()
        self.assertEqual(o["past_due_subscribers"], 1)
        self.assertEqual(o["mrr"], 0)


class TestWebhookLog(AdminTestCase):

    def test_processed_delivery_is_stored_with_its_payload(self):
        self.send(activation("I-H1", MONTHLY))

        data = self.client.get("/api/admin/webhooks", headers=self.auth).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["failed"], 0)

        e = data["events"][0]
        self.assertEqual(e["type"], "BILLING.SUBSCRIPTION.ACTIVATED")
        self.assertEqual(e["sub"], "Mara Ellison")
        self.assertEqual(e["result"], "processed")
        self.assertEqual(e["payload"]["resource"]["id"], "I-H1")

    def test_rejected_delivery_is_stored_with_the_reason(self):
        """A failing signature is exactly when the log has to work."""
        res = self.send(activation("I-H2", MONTHLY), verified=False)
        self.assertEqual(res.status_code, 400)

        data = self.client.get("/api/admin/webhooks", headers=self.auth).json()
        self.assertEqual(data["failed"], 1)

        e = data["events"][0]
        self.assertEqual(e["result"], "rejected")
        self.assertIn("Signature verification failed", e["error"])
        self.assertEqual(e["payload"]["resource"]["id"], "I-H2")

    def test_payment_amount_is_captured(self):
        self.send({
            "id": "WH-H3",
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "billing_agreement_id": "I-H3",
                "amount": {"total": "49.00", "currency": "USD"},
            },
        })
        e = self.client.get("/api/admin/webhooks", headers=self.auth).json()["events"][0]
        self.assertEqual(e["amount"], 49.0)
        self.assertEqual(e["currency"], "USD")

    def test_events_are_newest_first(self):
        self.send(activation("I-H4", MONTHLY))
        self.send(activation("I-H5", MONTHLY, "Later", "Person", "later@example.com"))

        events = self.client.get("/api/admin/webhooks", headers=self.auth).json()["events"]
        self.assertEqual(events[0]["payload"]["resource"]["id"], "I-H5")

    def test_limit_is_bounded(self):
        self.assertEqual(
            self.client.get("/api/admin/webhooks?limit=500", headers=self.auth).status_code, 422
        )


class TestAdminCancellation(AdminTestCase):
    """Cancelling must reach PayPal before the local record changes."""

    def test_successful_cancellation_updates_the_local_status(self):
        self.send(activation("I-J1", MONTHLY))

        with patch.object(main.paypal_provider, "cancel_subscription", return_value=True) as m, \
                patch.object(main.paypal_provider, "client_id", "cid"):
            res = self.client.post("/api/admin/subscriptions/I-J1/cancel", headers=self.auth)

        self.assertEqual(res.status_code, 200)
        m.assert_called_once()
        self.assertEqual(m.call_args[0][0], "I-J1")

        s = self.client.get("/api/admin/subscribers", headers=self.auth).json()["subscribers"][0]
        self.assertEqual(s["status"], "cancelled")

    def test_paypal_refusal_leaves_the_subscription_active(self):
        """Marking it cancelled locally would stop the operator chasing it
        while PayPal kept charging the customer."""
        self.send(activation("I-J2", MONTHLY))

        with patch.object(main.paypal_provider, "cancel_subscription", return_value=False), \
                patch.object(main.paypal_provider, "client_id", "cid"):
            res = self.client.post("/api/admin/subscriptions/I-J2/cancel", headers=self.auth)

        self.assertEqual(res.status_code, 502)
        self.assertIn("still active", res.json()["detail"])

        s = self.client.get("/api/admin/subscribers", headers=self.auth).json()["subscribers"][0]
        self.assertEqual(s["status"], "active")

    def test_cancellation_refused_when_paypal_is_not_configured(self):
        with patch.object(main.paypal_provider, "client_id", ""):
            res = self.client.post("/api/admin/subscriptions/I-J3/cancel", headers=self.auth)
        self.assertEqual(res.status_code, 503)

    def test_cancellation_requires_admin_authentication(self):
        self.assertEqual(
            self.client.post("/api/admin/subscriptions/I-J4/cancel").status_code, 401
        )


class TestPlanCatalogueFile(unittest.TestCase):
    """config/plans.json drives pricing shown to the operator."""

    @classmethod
    def setUpClass(cls):
        with open("config/plans.json", encoding="utf-8") as fh:
            cls.cat = json.load(fh)

    def test_every_plan_is_complete(self):
        for p in self.cat["plans"]:
            for field in ("id", "name", "paypal_plan_id", "price", "interval"):
                self.assertIn(field, p, f"{p.get('id')} missing '{field}'")
            self.assertGreater(p["price"], 0)
            self.assertIn(p["interval"], ("month", "year"))

    def test_paypal_plan_ids_are_unique_and_well_formed(self):
        ids = [p["paypal_plan_id"] for p in self.cat["plans"]]
        self.assertEqual(len(ids), len(set(ids)))
        for pid in ids:
            self.assertTrue(pid.startswith("P-"), pid)


if __name__ == "__main__":
    unittest.main()
