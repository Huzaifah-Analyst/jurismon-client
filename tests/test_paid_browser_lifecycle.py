"""Genuine browser account transitions with isolated SQLite and mocked PayPal."""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import pytest
from playwright.sync_api import expect
import api.main as main
from test_frontend_crawl_polling import local_browser
from test_frontend_fixes import login_customer

@pytest.mark.parametrize('local_browser', ['chromium', 'firefox', 'webkit'], indirect=True)
def test_paid_account_pause_resume_cancel_and_expiry(local_browser, monkeypatch):
    page, base, repository = local_browser
    login_customer(page, base, repository)
    user = repository.get_user_by_email('browser@example.invalid')
    period = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    subscription_id = 'I-ISOLATED-BROWSER-LIFECYCLE'
    repository.record_subscription(subscription_id, 'professional_monthly', 'active', user_email=user['email'], user_id=user['id'], next_billing_at=period)
    provider = {}
    for name in ['suspend_subscription', 'activate_subscription', 'cancel_subscription']:
        provider[name] = Mock(return_value=True)
        monkeypatch.setattr(main.paypal_provider, name, provider[name])
    monkeypatch.setattr(main, '_send_subscription_lifecycle_email', lambda *args, **kwargs: False)
    page.set_viewport_size({'width': 375, 'height': 812})
    page.goto(base + '/account')
    expect(page.locator('#state-active')).to_be_visible()
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('#btn-pause').click()
    expect(page.locator('#state-paused')).to_be_visible()
    assert repository.get_subscription_by_external_id(subscription_id)['status'] in ['paused', 'suspended']
    provider['suspend_subscription'].assert_called_once()
    page.locator('#btn-resume').click()
    expect(page.locator('#state-active')).to_be_visible()
    provider['activate_subscription'].assert_called_once()
    page.locator('#btn-cancel').click()
    expect(page.locator('#cancel-modal')).to_be_visible()
    page.locator('#btn-cancel-abort').click()
    expect(page.locator('#cancel-modal')).to_be_hidden()
    assert not provider['cancel_subscription'].called
    page.locator('#btn-cancel').click()
    page.locator('#btn-cancel-confirm').click()
    expect(page.locator('#state-cancelled-in-period')).to_be_visible()
    provider['cancel_subscription'].assert_called_once()
    assert repository.get_user_access_status(user['email'])['has_access'] is True
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    repository.set_subscription_cancelled(subscription_id, cancelled_at=expired, access_until=expired, reason='Isolated expiry verification')
    page.reload()
    expect(page.locator('#state-cancelled-expired')).to_be_visible()
    assert repository.get_user_access_status(user['email'])['has_access'] is False
