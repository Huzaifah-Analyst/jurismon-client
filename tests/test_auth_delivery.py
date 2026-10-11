from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect

import api.main as main
from db.repository import Repository
from tests.test_frontend_crawl_polling import local_browser


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    repository = Repository(db_path=str(tmp_path / 'auth.db'))
    repository.supabase = None
    monkeypatch.setattr(main, 'repo', repository)
    monkeypatch.setattr(main, '_forgot_password_timestamps', {})
    return TestClient(main.app), repository


@pytest.mark.parametrize('endpoint', ['register', 'resend-code', 'forgot-password'])
@pytest.mark.parametrize('failure', ['false', 'exception'])
def test_failed_dispatch_preserves_existing_code(auth_client, monkeypatch, endpoint, failure):
    client, repository = auth_client
    email = 'existing@example.invalid'
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    repository.create_user(email, 'unused', verification_code='123456', verification_code_expires_at=expiry)
    def send(**kwargs):
        if failure == 'exception':
            raise RuntimeError('provider failure')
        return False
    monkeypatch.setattr(main.mailer, 'send', send)
    response = client.post('/api/auth/' + endpoint, json={'email': email, 'password': 'Password123!'})
    assert response.status_code == (200 if endpoint == 'forgot-password' else 503)
    assert 'has been sent' not in response.text
    assert repository.get_user_by_email(email)['verification_code'] == '123456'
    assert repository.validate_verification_code(email, '123456')['valid']
    if endpoint == 'forgot-password':
        unknown = client.post('/api/auth/forgot-password', json={'email': 'unknown@example.invalid'})
        assert unknown.json() == response.json()
    else:
        assert client.post('/api/auth/verify-code', json={'email': email, 'code': '123456'}).status_code == 200


def test_signup_failure_retry_and_persistence_failure(auth_client, monkeypatch):
    client, repository = auth_client
    payload = {'email': 'retry@example.invalid', 'password': 'Password123!'}
    monkeypatch.setattr(main.mailer, 'send', lambda **kwargs: False)
    assert client.post('/api/auth/register', json=payload).status_code == 503
    user = repository.get_user_by_email(payload['email'])
    assert user['verification_code'] is None
    assert user['trial_started_at'] is None
    monkeypatch.setattr(main.mailer, 'send', lambda **kwargs: True)
    assert client.post('/api/auth/register', json=payload).status_code == 200
    old = repository.get_user_by_email(payload['email'])['verification_code']
    monkeypatch.setattr(repository, 'set_verification_code', lambda *args: False)
    assert client.post('/api/auth/resend-code', json=payload).status_code == 503
    assert repository.get_user_by_email(payload['email'])['verification_code'] == old


def test_browser_delivery_failure_and_recovery(local_browser, monkeypatch):
    page, base, repository = local_browser
    monkeypatch.setattr(main.mailer, 'send', lambda **kwargs: False)
    page.goto(base + '/')
    page.locator('#btn-nav-login').click()
    page.locator('#tab-register').click()
    page.locator('#reg-email').fill('browser-mail@example.invalid')
    page.locator('#reg-password').fill('Password123!')
    page.locator('#btn-submit-reg').click()
    expect(page.locator('#auth-error')).to_contain_text('Unable to send')
    expect(page.locator('#form-register')).to_be_visible()
    expect(page.locator('#form-verify')).to_be_hidden()
    monkeypatch.setattr(main.mailer, 'send', lambda **kwargs: True)
    page.locator('#btn-submit-reg').click()
    expect(page.locator('#verify-code')).to_be_visible()
    old = repository.get_user_by_email('browser-mail@example.invalid')['verification_code']
    monkeypatch.setattr(main.mailer, 'send', lambda **kwargs: False)
    page.locator('#btn-resend-code').click()
    expect(page.locator('#auth-error')).to_contain_text('Unable to send')
    assert repository.get_user_by_email('browser-mail@example.invalid')['verification_code'] == old
    page.locator('#verify-code').fill(old)
    page.locator('#btn-submit-verify').click()
    expect(page.locator('#btn-nav-logout')).to_be_visible()
    page.locator('#btn-nav-logout').click()
    page.locator('#btn-nav-login').click()
    page.locator('#login-email').fill('browser-mail@example.invalid')
    page.locator('#link-forgot-password').click()
    expect(page.locator('#verify-modal-subtitle')).to_contain_text('If you receive a code')
    expect(page.locator('#verify-modal-subtitle')).not_to_contain_text('code sent')
    messages = []
    page.on('dialog', lambda dialog: (messages.append(dialog.message), dialog.accept()))
    page.locator('#btn-resend-code').click()
    expect(page.locator('#verify-code')).to_be_focused()
    assert messages and 'has been sent' not in messages[-1]
