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

        self._plans_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "config", "plans.json")
        )
        with open(self._plans_path, "rb") as fh:
            self._saved_plans_bytes = fh.read()

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
        with open(self._plans_path, "wb") as fh:
            fh.write(self._saved_plans_bytes)
        main.invalidate_plan_catalogue_cache()

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


class TestPlanCatalogueManagement(AdminTestCase):

    def test_plan_write_requires_admin_authentication(self):
        # 401 unauthenticated
        res = self.client.put("/api/admin/plans/professional_monthly", json={"name": "New Name"})
        self.assertEqual(res.status_code, 401)

        patch_res = self.client.patch("/api/admin/plans", json={"trial_days": 7})
        self.assertEqual(patch_res.status_code, 401)

        # 403 with customer token
        cust_token = auth.create_customer_token("cust_1", "cust@example.com")
        cust_auth = {"Authorization": f"Bearer {cust_token}"}

        res_cust = self.client.put(
            "/api/admin/plans/professional_monthly",
            json={"name": "New Name"},
            headers=cust_auth,
        )
        self.assertEqual(res_cust.status_code, 403)

        patch_cust = self.client.patch(
            "/api/admin/plans",
            json={"trial_days": 7},
            headers=cust_auth,
        )
        self.assertEqual(patch_cust.status_code, 403)

    def test_successful_plan_name_edit(self):
        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 49.0, "currency": "USD", "interval": "month"}):
            res = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"name": "JurisMon Pro Monthly"},
                headers=self.auth,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            monthly = next(p for p in data["plans"] if p["id"] == "professional_monthly")
            self.assertEqual(monthly["name"], "JurisMon Pro Monthly")

            # Check GET /api/admin/plans returns the updated name
            get_res = self.client.get("/api/admin/plans", headers=self.auth)
            get_monthly = next(p for p in get_res.json()["plans"] if p["id"] == "professional_monthly")
            self.assertEqual(get_monthly["name"], "JurisMon Pro Monthly")

    def test_successful_price_edit_when_paypal_agrees(self):
        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 59.0, "currency": "USD", "interval": "month"}):
            res = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"price": 59.0},
                headers=self.auth,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            monthly = next(p for p in data["plans"] if p["id"] == "professional_monthly")
            self.assertEqual(monthly["price"], 59.0)

    def test_price_edit_rejected_with_409_when_disagreeing_with_paypal(self):
        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 49.0, "currency": "USD", "interval": "month"}):
            res = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"price": 59.0},
                headers=self.auth,
            )
            self.assertEqual(res.status_code, 409)
            detail = res.json()["detail"]
            self.assertIn("59", detail)
            self.assertIn("49", detail)

    def test_write_rejected_with_503_when_paypal_credentials_unset(self):
        with patch.object(main.paypal_provider, "client_id", ""):
            res = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"price": 49.0},
                headers=self.auth,
            )
            self.assertEqual(res.status_code, 503)

    def test_cannot_deactivate_last_active_plan(self):
        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 468.0, "currency": "USD", "interval": "year"}):
            # Deactivate annual first
            res1 = self.client.put(
                "/api/admin/plans/professional_annual",
                json={"is_active": False},
                headers=self.auth,
            )
            self.assertEqual(res1.status_code, 200)

        # Now attempt to deactivate monthly (the last active plan)
        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 49.0, "currency": "USD", "interval": "month"}):
            res2 = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"is_active": False},
                headers=self.auth,
            )
            self.assertEqual(res2.status_code, 409)
            self.assertIn("last active plan", res2.json()["detail"])

    def test_duplicate_paypal_plan_id_rejected_with_409(self):
        res = self.client.put(
            "/api/admin/plans/professional_monthly",
            json={"paypal_plan_id": ANNUAL},
            headers=self.auth,
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("already assigned", res.json()["detail"])

    def test_cache_invalidation_updates_get_api_plans_in_same_process(self):
        init_plans = self.client.get("/api/plans").json()["plans"]
        init_monthly = next(p for p in init_plans if p["id"] == "professional_monthly")
        self.assertEqual(init_monthly["price"], 49.0)

        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 75.0, "currency": "USD", "interval": "month"}):
            put_res = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"price": 75.0},
                headers=self.auth,
            )
            self.assertEqual(put_res.status_code, 200)

        # GET /api/plans in the same process must return the new price without restart
        new_plans = self.client.get("/api/plans").json()["plans"]
        new_monthly = next(p for p in new_plans if p["id"] == "professional_monthly")
        self.assertEqual(new_monthly["price"], 75.0)

    def test_grandfathered_subscriber_on_inactive_plan_resolves_plan_name(self):
        self.send(activation("I-GF1", MONTHLY))

        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 49.0, "currency": "USD", "interval": "month"}):
            # Deactivate monthly plan
            deact_res = self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"is_active": False},
                headers=self.auth,
            )
            self.assertEqual(deact_res.status_code, 200)

        # Grandfathered subscriber on inactive plan must still resolve plan name
        sub_res = self.client.get("/api/admin/subscribers", headers=self.auth)
        self.assertEqual(sub_res.status_code, 200)
        subs = sub_res.json()["subscribers"]
        gf_sub = next(s for s in subs if s.get("paypal") == "I-GF1")
        self.assertEqual(gf_sub["plan_name"], "Professional")
        self.assertIsNotNone(gf_sub["plan_price"])

    def test_atomic_write_leaves_no_tmp_file_on_success_or_failure(self):
        config_dir = os.path.dirname(self._plans_path)
        tmp_before = [f for f in os.listdir(config_dir) if f.endswith(".tmp")]
        self.assertEqual(len(tmp_before), 0)

        # Success case
        with patch.object(main.paypal_provider, "client_id", "test_id"), \
             patch.object(main.paypal_provider, "client_secret", "test_secret"), \
             patch.object(main.paypal_provider, "get_plan_details", return_value={"price": 49.0, "currency": "USD", "interval": "month"}):
            self.client.put(
                "/api/admin/plans/professional_monthly",
                json={"name": "Atomic Name Test"},
                headers=self.auth,
            )
            tmp_after = [f for f in os.listdir(config_dir) if f.endswith(".tmp")]
            self.assertEqual(len(tmp_after), 0)

        # Failure case: os.replace fails
        with patch("os.replace", side_effect=OSError("Disk write error")):
            try:
                main._write_plan_catalogue({"currency": "USD", "trial_days": 14, "plans": []})
            except OSError:
                pass
            tmp_fail = [f for f in os.listdir(config_dir) if f.endswith(".tmp")]
            self.assertEqual(len(tmp_fail), 0)

    def test_patch_catalogue_settings(self):
        res = self.client.patch(
            "/api/admin/plans",
            json={"trial_days": 21, "currency": "EUR"},
            headers=self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["trial_days"], 21)
        self.assertEqual(data["currency"], "EUR")

        # Public plans reflect updated settings
        pub = self.client.get("/api/plans").json()
        self.assertEqual(pub["trial_days"], 21)
        self.assertEqual(pub["currency"], "EUR")

    def test_plan_details_extraction_from_paypal_response(self):
        mock_response = {
            "id": "P-TESTPLAN123",
            "name": "JurisMon Pro Plan",
            "status": "ACTIVE",
            "billing_cycles": [
                {
                    "tenure_type": "TRIAL",
                    "pricing_scheme": {"fixed_price": {"value": "0", "currency_code": "USD"}},
                    "frequency": {"interval_unit": "DAY", "interval_count": 14},
                },
                {
                    "tenure_type": "REGULAR",
                    "pricing_scheme": {"fixed_price": {"value": "49.00", "currency_code": "USD"}},
                    "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                },
            ],
        }
        with patch.object(main.paypal_provider, "_get_access_token", return_value="fake_token"), \
             patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response
            details = main.paypal_provider.get_plan_details("P-TESTPLAN123")
            self.assertIsNotNone(details)
            self.assertEqual(details["price"], 49.0)
            self.assertEqual(details["currency"], "USD")
            self.assertEqual(details["interval"], "month")
            self.assertEqual(details["id"], "P-TESTPLAN123")


if __name__ == "__main__":
    unittest.main()
