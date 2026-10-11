"""Automated WCAG audit of real pages, authenticated states and open dialogs."""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from playwright.sync_api import expect
import api.auth as auth
import api.main as main
from test_frontend_crawl_polling import local_browser
from test_frontend_fixes import login_customer

AXE_SCRIPT = Path(__file__).parent / 'vendor' / 'axe-core-4.10.3.min.js'

@pytest.mark.parametrize('mode', ['light', 'dark'])
@pytest.mark.parametrize('width', [375, 1280])
def test_pages_account_states_and_dialogs_accessibility(local_browser, mode, width, monkeypatch):
    page, base, repository = local_browser
    monkeypatch.setattr(main.mailer, "send", lambda **kwargs: True)
    page.set_viewport_size({'width': width, 'height': 900})
    page.emulate_media(color_scheme=mode)
    results = []
    artifacts = Path('test-results/qa-23-25/accessibility')
    artifacts.mkdir(parents=True, exist_ok=True)

    def audit(label):
        page.evaluate("""async () => {
            await document.fonts.ready;
            await new Promise(requestAnimationFrame);
            await Promise.all(document.getAnimations().filter(a =>
                a.effect.getComputedTiming().iterations !== Infinity
            ).map(a => a.finished.catch(() => {})));
        }""")
        if not page.evaluate("typeof axe !== 'undefined'"):
            page.add_script_tag(path=str(AXE_SCRIPT))
        result = page.evaluate("async () => await axe.run(document)")
        record = {'view': label, 'width': width, 'mode': mode,
                  'violations': [{'id': v['id'], 'impact': v['impact'], 'nodes': [{'target': n['target'], 'summary': n.get('failureSummary')} for n in v['nodes']]} for v in result['violations']],
                  'incomplete': [{'id': v['id'], 'nodes': [{'target': n['target'], 'summary': n.get('failureSummary')} for n in v['nodes']]} for v in result['incomplete']]}
        results.append(record)
        if record['violations']:
            page.screenshot(path=str(artifacts / f'{width}-{mode}-{label}.png'), full_page=True)

    for path in ['/', '/account', '/about', '/terms', '/privacy', '/admin']:
        page.goto(base + path, wait_until='networkidle')
        if path == '/account':
            expect(page.locator('#state-signed-out')).to_be_visible()
        audit('public-' + (path.strip('/') or 'home'))

    page.goto(base + '/', wait_until='networkidle')
    page.locator('#btn-nav-login').click()
    expect(page.locator('#auth-modal')).to_be_visible()
    audit('login-dialog')
    page.locator('#tab-register').click()
    expect(page.locator('#form-register')).to_be_visible()
    audit('register-dialog')
    page.locator('#reg-email').fill('axe-otp@example.invalid')
    page.locator('#reg-password').fill('isolated-axe-password')
    page.locator('#btn-submit-reg').click()
    expect(page.locator('#verify-code')).to_be_visible()
    audit('email-confirmation-dialog')
    stored = repository.get_user_by_email('axe-otp@example.invalid')
    wrong_code = '000000' if stored.get('verification_code') != '000000' else '111111'
    page.locator('#verify-code').fill(wrong_code)
    with page.expect_response(lambda r: r.url.endswith('/api/auth/verify-code')) as verification:
        page.locator('#btn-submit-verify').click()
    assert verification.value.status == 400
    expect(page.locator('#auth-error')).to_be_visible()
    audit('wrong-code-dialog')
    page.locator('#auth-modal-close').click()
    repository.create_user('axe-reset@example.invalid', auth.get_password_hash('isolated-axe-password'), 'Isolated QA', is_verified=1)
    page.locator('#btn-nav-login').click()
    page.locator('#login-email').fill('axe-reset@example.invalid')
    page.locator('#link-forgot-password').click()
    expect(page.locator('#reset-new-password')).to_be_visible()
    audit('password-reset-dialog')
    page.locator('#auth-modal-close').click()

    login_customer(page, base, repository)
    page.goto(base + '/account')
    expect(page.locator('#state-no-subscription')).to_be_visible()
    audit('trial-account')
    page.goto(base + '/?subscribe=1')
    expect(page.locator('#paywall-modal')).to_be_visible()
    audit('plan-dialog')

    user = repository.get_user_by_email('browser@example.invalid')
    for status, state in [('active', 'state-active'), ('suspended', 'state-paused'), ('cancelled', 'state-cancelled-in-period'), ('cancelled_expired', 'state-cancelled-expired')]:
        period = (datetime.now(timezone.utc) + timedelta(days=-2 if status == 'cancelled_expired' else 15)).isoformat()
        repository.record_subscription('I-LOCAL-AXE', 'professional_monthly', 'cancelled' if status == 'cancelled_expired' else status, user_email=user['email'], user_id=user['id'], next_billing_at=period)
        page.goto(base + '/account')
        expect(page.locator('#' + state)).to_be_visible()
        audit('account-' + status)
        if status == 'active':
            page.locator('#btn-cancel').click()
            expect(page.locator('#cancel-modal')).to_be_visible()
            audit('cancel-dialog')
            page.locator('#btn-cancel-abort').click()

    login = page.request.post(base + '/api/admin/login', data={'email': auth.ADMIN_EMAIL, 'password': 'local-browser-password'})
    assert login.ok
    page.add_init_script("localStorage.setItem('jurismon_admin_token', " + repr(login.json()['access_token']) + ")")
    page.goto(base + '/admin', wait_until='networkidle')
    expect(page.locator('#sources')).to_be_visible()
    audit('authenticated-admin')
    page.locator('#t-plans').click()
    expect(page.locator('#p-plans')).to_be_visible()
    audit('admin-plans')
    page.locator('.btn-edit-plan').first.click()
    expect(page.locator('[id^="edit-plan-name-"]')).to_be_visible()
    audit('admin-plan-editor')
    (artifacts / f'{width}-{mode}.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    failures = [r for r in results if r['violations']]
    assert not failures, json.dumps([{'view': r['view'], 'rules': [v['id'] for v in r['violations']]} for r in failures])
