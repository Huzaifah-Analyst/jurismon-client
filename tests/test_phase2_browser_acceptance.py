"""Sequential customer actions against real HTTP/SQLite; external services isolated."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from playwright.sync_api import expect

import api.auth as auth
import api.main as main
from test_frontend_crawl_polling import local_browser, admin_browser


def test_customer_journey_one_step_at_a_time(local_browser, monkeypatch):
    page, base, repository = local_browser
    email = "phase2@example.invalid"
    repository.create_user(email, auth.get_password_hash("local-browser-password"),
                           "Isolated acceptance customer", is_verified=1)
    repository.activate_user_trial(email)
    provider_calls = {}
    for action in ("suspend_subscription", "activate_subscription", "cancel_subscription"):
        provider_calls[action] = Mock(return_value=True)
        monkeypatch.setattr(main.paypal_provider, action, provider_calls[action])
    mail = Mock(return_value=True)
    monkeypatch.setattr(main.mailer, "send", mail)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    # 1: genuine signed-out gate, rejected login, successful form login.
    page.goto(base + "/account")
    expect(page.locator("#state-signed-out")).to_be_visible()
    expect(page.locator("#btn-pause")).not_to_be_visible()
    page.locator("#login-email").fill(email)
    page.locator("#login-password").fill("incorrect-password")
    page.locator("#btn-submit-login").click()
    expect(page.locator("#login-error")).to_be_visible()
    page.locator("#login-password").fill("local-browser-password")
    page.locator("#btn-submit-login").click()

    # 2: trial overview persists across refresh.
    expect(page.locator("#state-no-subscription")).to_be_visible()
    expect(page.locator("#no-sub-email")).to_have_text(email)
    expect(page.locator("#btn-no-sub-upgrade")).to_be_visible()
    page.reload()
    expect(page.locator("#state-no-subscription")).to_be_visible()

    # 3: real database paid subscription, rendered by the account API.
    user = repository.get_user_by_email(email)
    billing = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    repository.record_subscription("I-ISOLATED-PHASE2", "professional_monthly", "active",
                                   user_email=email, user_id=user["id"], next_billing_at=billing)
    page.reload()
    expect(page.locator("#state-active")).to_be_visible()
    expect(page.locator("#active-sub-id")).to_have_text("I-ISOLATED-PHASE2")

    # 4: dismissing the native pause confirmation never calls the provider.
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.locator("#btn-pause").click()
    provider_calls["suspend_subscription"].assert_not_called()
    expect(page.locator("#state-active")).to_be_visible()

    # 5-6: pause, refresh and one confirmation submission (not inbox delivery).
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#btn-pause").click()
    expect(page.locator("#state-paused")).to_be_visible()
    provider_calls["suspend_subscription"].assert_called_once()
    assert mail.call_count == 1
    page.reload()
    expect(page.locator("#state-paused")).to_be_visible()
    expect(page.locator("#paused-sub-id")).to_have_text("I-ISOLATED-PHASE2")

    # 7: resume the same subscription and retain state after refresh.
    page.locator("#btn-resume").click()
    expect(page.locator("#state-active")).to_be_visible()
    provider_calls["activate_subscription"].assert_called_once()
    assert mail.call_count == 2
    page.reload()
    expect(page.locator("#active-sub-id")).to_have_text("I-ISOLATED-PHASE2")

    # 8: abort cancellation without a provider call.
    page.locator("#btn-cancel").click()
    expect(page.locator("#cancel-modal")).to_be_visible()
    page.locator("#btn-cancel-abort").click()
    expect(page.locator("#cancel-modal")).not_to_be_visible()
    provider_calls["cancel_subscription"].assert_not_called()

    # 9: confirmed cancellation preserves paid access and submits one email.
    page.locator("#btn-cancel").click()
    page.locator("#cancel-reason-input").fill("Isolated acceptance verification")
    page.locator("#btn-cancel-confirm").click()
    expect(page.locator("#state-cancelled-in-period")).to_be_visible()
    provider_calls["cancel_subscription"].assert_called_once()
    assert mail.call_count == 3
    page.reload()
    expect(page.locator("#state-cancelled-in-period")).to_be_visible()
    token = page.evaluate("localStorage.getItem('jurismon_token')")
    headers = {"Authorization": "Bearer " + token}
    assert page.request.get(base + "/api/search?q=zoning", headers=headers).json()["is_gated"] is False

    # 10: retry opens the real application checkout, without external payment.
    page.locator("#btn-cancelled-resubscribe").click()
    expect(page.locator("#paywall-modal")).to_be_visible()
    assert repository.get_subscription_by_external_id("I-ISOLATED-PHASE2")["status"] == "cancelled"
    assert errors == []


def test_admin_plan_edit_cancel_preserves_catalogue(admin_browser):
    page, base, repository = admin_browser
    original = page.request.get(base + "/api/plans").json()
    page.goto(base + "/admin")
    page.locator("#t-plans").click()
    edit = page.locator('.btn-edit-plan[data-id="professional_monthly"]')
    expect(edit).to_be_visible()
    edit.click()
    expect(page.locator("#edit-plan-active-professional_monthly")).to_be_visible()
    expect(page.locator("#edit-plan-paypal-professional_monthly")).to_be_visible()
    page.locator("#edit-plan-name-professional_monthly").fill("Discard this isolated edit")
    page.locator("#edit-plan-price-professional_monthly").fill("59")
    page.locator('.btn-cancel-plan[data-id="professional_monthly"]').click()
    expect(edit).to_be_visible()
    page.reload()
    page.locator("#t-plans").click()
    expect(edit).to_be_visible()
    assert page.request.get(base + "/api/plans").json() == original
