import pytest
from playwright.sync_api import expect
from tests.test_frontend_crawl_polling import local_browser


@pytest.mark.parametrize('local_browser', ['chromium', 'firefox', 'webkit'], indirect=True)
def test_closed_dialogs_and_keyboard_lifecycle(local_browser):
    page, base, _ = local_browser
    page.goto(base + '/')
    for _ in range(30):
        page.keyboard.press('Tab')
        assert not page.evaluate("!!document.activeElement.closest('.modal-overlay')")
    opener = page.locator('#btn-nav-login')
    opener.click()
    expect(page.locator('#auth-modal-close')).to_be_focused()
    page.keyboard.press('Shift+Tab')
    assert page.evaluate("document.activeElement.closest('#auth-modal') !== null")
    for _ in range(15):
        page.keyboard.press('Tab')
        assert page.evaluate("document.activeElement.closest('#auth-modal') !== null")
    page.keyboard.press('Escape')
    expect(opener).to_be_focused()
    assert page.locator('#auth-modal').evaluate('el => el.inert')
    page.goto(base + '/?subscribe=1')
    expect(page.locator('#paywall-modal-close')).to_be_focused()
    for _ in range(12):
        page.keyboard.press('Tab')
        assert page.evaluate("document.activeElement.closest('#paywall-modal') !== null")
    page.keyboard.press('Escape')
    assert page.locator('#paywall-modal').evaluate('el => el.inert')
    assert not page.locator('main').evaluate('el => el.inert')
