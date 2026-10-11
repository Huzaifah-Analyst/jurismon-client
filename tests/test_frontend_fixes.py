"""Visual and error-state regressions using real local API responses."""

import copy
import threading
from pathlib import Path

import pytest
from playwright.sync_api import expect

import api.main as main
import api.auth as auth
from test_frontend_crawl_polling import local_browser, admin_browser


def seed_search(repository, count=30):
    repository.upsert_source({"id": "browser-source", "name": "Local QA source",
                              "base_url": "https://example.invalid", "adapter_type": "custom"})
    for index in range(count):
        document = repository.get_or_create_document(
            "browser-source", f"Local QA ordinance {index}", f"https://example.invalid/{index}")
        repository.create_snapshot(document["id"], 1, str(index),
                                   "Section 1. Zoning requirements.", "Section 1. Zoning requirements.")


def login_customer(page, base, repository):
    repository.create_user("browser@example.invalid", auth.get_password_hash("browser-password"),
                           "Browser QA", is_verified=1)
    repository.activate_user_trial("browser@example.invalid")
    response = page.request.post(base + "/api/auth/login", data={
        "email": "browser@example.invalid", "password": "browser-password"})
    assert response.ok
    token = response.json()["access_token"]
    page.add_init_script("localStorage.setItem('jurismon_token', " + repr(token) + ")")


@pytest.mark.parametrize("signed_in", [False, True])
def test_mobile_pills_stay_inside_viewport(local_browser, signed_in):
    page, base, repository = local_browser
    seed_search(repository)
    if signed_in:
        login_customer(page, base, repository)
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(base + "/")
    expect(page.locator('[data-count="snapshot"]')).to_have_text("30" if signed_in else "2")
    dimensions = page.evaluate("""() => ({
        viewport: innerWidth, page: document.documentElement.scrollWidth,
        pills: document.querySelector('#pills').getBoundingClientRect().right,
        scroll: document.querySelector('#pills').scrollWidth,
        width: document.querySelector('#pills').clientWidth
    })""")
    assert dimensions["page"] <= dimensions["viewport"], dimensions
    assert dimensions["pills"] <= dimensions["viewport"], dimensions
    page.locator('[data-filter="snapshot"]').click()
    expect(page.locator('[data-filter="snapshot"]')).to_have_attribute("aria-pressed", "true")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_logged_in_load_shows_skeleton_before_session_returns(local_browser, monkeypatch):
    page, base, repository = local_browser
    seed_search(repository, 1)
    login_customer(page, base, repository)
    original = repository.get_user_by_email
    release = threading.Event()

    def delayed_user(email):
        release.wait(timeout=8)
        return original(email)

    monkeypatch.setattr(repository, "get_user_by_email", delayed_user)
    try:
        page.goto(base + "/", wait_until="domcontentloaded")
        expect(page.locator(".skel-row")).to_have_count(5, timeout=2000)
        expect(page.locator("#empty")).to_be_hidden()
        expect(page.locator("#summary")).not_to_contain_text("0 latest")
    finally:
        release.set()
    expect(page.locator(".result")).to_have_count(1, timeout=10000)


def test_unavailable_coverage_does_not_invent_counts(local_browser, monkeypatch):
    page, base, repository = local_browser
    seed_search(repository, 1)

    def unavailable_sources():
        raise RuntimeError("Local QA source lookup failure")

    monkeypatch.setattr(repository, "get_all_sources", unavailable_sources)
    page.goto(base + "/")
    expect(page.locator("#status-text")).to_have_text("Source coverage unavailable.")
    expect(page.locator(".result")).to_have_count(1)
    expect(page.locator("#gate-banner-text")).not_to_contain_text("41 live")
    expect(page.locator("#gate-banner-text")).not_to_contain_text("65 tracked")


@pytest.mark.parametrize("width", [375, 1280])
def test_wrong_otp_does_not_move_code_field(local_browser, monkeypatch, width):
    page, base, _ = local_browser
    monkeypatch.setattr(main.mailer, "send", lambda **kwargs: True)
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(base + "/")
    page.locator("#btn-nav-register").click()
    page.locator("#reg-email").fill("otp-browser@example.invalid")
    page.locator("#reg-password").fill("browser-password")
    page.locator("#btn-submit-reg").click()
    code = page.locator("#verify-code")
    expect(code).to_be_visible()
    before = code.bounding_box()
    code.fill("000000")
    with page.expect_response(lambda response: response.url.endswith("/api/auth/verify-code")) as result:
        page.locator("#btn-submit-verify").click()
    assert result.value.status == 400
    expect(page.locator("#auth-error")).to_be_visible()
    after = code.bounding_box()
    assert abs(before["y"] - after["y"]) <= 1, (before, after)
    expect(code).to_be_focused()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_theme_and_responsive_pages(local_browser, mode):
    page, base, repository = local_browser
    seed_search(repository, 1)
    page.emulate_media(color_scheme=mode, reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    screenshot_dir = Path("test-results/frontend")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    for width in (375, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        for path in ("/", "/account", "/admin", "/about", "/terms", "/privacy"):
            page.goto(base + path)
            expected_bg = "rgb(11, 18, 32)" if mode == "dark" else "rgb(248, 250, 252)"
            expect(page.locator("body")).to_have_css("background-color", expected_bg)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (mode, width, path)
            if path == "/":
                expect(page.locator(".result")).to_have_count(1)
                page.locator('[data-act="toggle"]').click()
            page.screenshot(path=str(screenshot_dir / f'{mode}-{width}-{path.strip("/") or "home"}.png'), full_page=True)
    assert not errors, errors


@pytest.mark.parametrize("rejection", ["price", "last_active"])
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_admin_plan_rejections_are_visible(admin_browser, monkeypatch, rejection, mode):
    page, base, _ = admin_browser
    page.emulate_media(color_scheme=mode)
    catalogue = copy.deepcopy(main.get_plan_catalogue())
    plan = catalogue["plans"][0]
    if rejection == "last_active":
        for other in catalogue["plans"]:
            other["is_active"] = other["id"] == plan["id"]
    monkeypatch.setattr(main, "get_plan_catalogue", lambda: copy.deepcopy(catalogue))
    monkeypatch.setattr(main.paypal_provider, "client_id", "local-test")
    monkeypatch.setattr(main.paypal_provider, "client_secret", "local-test")
    monkeypatch.setattr(main.paypal_provider, "get_plan_details", lambda _: {
        "price": plan["price"], "currency": "USD", "interval": plan["interval"]})
    page.goto(base + "/admin")
    page.locator('#t-plans').click()
    page.locator(f'.btn-edit-plan[data-id="{plan["id"]}"]').click()
    if rejection == "price":
        page.locator(f'#edit-plan-price-{plan["id"]}').fill(str(plan["price"] + 1))
        message = "Price mismatch"
    else:
        page.locator(f'#edit-plan-active-{plan["id"]}').select_option("false")
        message = "Cannot deactivate the last active plan"
    with page.expect_response(lambda response: response.request.method == "PUT") as result:
        page.locator(f'.btn-save-plan[data-id="{plan["id"]}"]').click()
    assert result.value.status == 409
    expect(page.locator("#toast")).to_be_visible()
    expect(page.locator("#toast")).to_have_css("opacity", "1")
    expect(page.locator("#toast-text")).to_contain_text(message)
    expect(page.locator(f'.btn-save-plan[data-id="{plan["id"]}"]')).to_be_enabled()
    screenshot_dir = Path("test-results/frontend")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot_dir / f"admin-409-{mode}-{rejection}.png"))


@pytest.mark.parametrize("days", [14, 34, 45, 67, 0])
def test_trial_offer_uses_real_catalogue(local_browser, monkeypatch, days):
    page, base, repository = local_browser
    catalogue = copy.deepcopy(main.get_plan_catalogue())
    catalogue["trial_days"] = days
    monkeypatch.setattr(main, "get_plan_catalogue", lambda: catalogue)
    page.goto(base + "/")
    label = f"Start {days}-Day Free Trial" if days else "Create Account"
    expect(page.locator("#btn-nav-register")).to_have_text(label)
    page.locator("#btn-nav-register").click()
    expect(page.locator("#tab-register")).to_have_text(label)
    expect(page.locator("#btn-submit-reg")).to_have_text(label)
    expect(page.locator("#register-trial-description")).to_contain_text(
        f"{days}-day free trial" if days else "Subscribe for full access")
    expect(page.locator("#btn-submit-verify")).to_have_text(
        f"Confirm & Start {days}-Day Free Trial" if days else "Confirm Email")
    page.goto(base + "/account")
    expect(page.locator("#signed-out-trial-link")).to_have_text(
        f"Start {days}-day free trial" if days else "Create Account")


@pytest.mark.parametrize("days", [34, 0])
def test_terms_use_configured_trial(local_browser, monkeypatch, days):
    page, base, repository = local_browser
    catalogue = copy.deepcopy(main.get_plan_catalogue())
    catalogue["trial_days"] = days
    monkeypatch.setattr(main, "get_plan_catalogue", lambda: catalogue)
    page.goto(base + "/terms")
    expect(page.locator("#terms-trial-offer")).to_contain_text(
        "34-day free trial" if days else "No complimentary free trial")


def test_trial_offer_failure_does_not_invent_duration(local_browser, monkeypatch):
    page, base, repository = local_browser
    def unavailable():
        raise RuntimeError("Local QA catalogue unavailable")
    monkeypatch.setattr(main, "get_plan_catalogue", unavailable)
    page.goto(base + "/")
    expect(page.locator("#btn-nav-register")).to_have_text("Create Account")
    page.goto(base + "/account")
    expect(page.locator("#signed-out-trial-link")).to_have_text("Create Account")


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_about_describes_actual_scope(local_browser, mode):
    page, base, repository = local_browser
    page.emulate_media(color_scheme=mode)
    page.goto(base + "/about")
    expect(page.locator(".lede")).to_contain_text("international national registries")
    expect(page.locator("#ingestion-stat")).to_contain_text("configured")
    expect(page.locator("body")).to_contain_text("Remaining boilerplate")


@pytest.mark.parametrize("local_browser", ["chromium", "firefox", "webkit"], indirect=True)
def test_browser_authenticated_mobile_search_and_account(local_browser):
    page, base, repository = local_browser
    seed_search(repository, 3)
    login_customer(page, base, repository)
    page.set_viewport_size({"width": 375, "height": 812})
    page.emulate_media(color_scheme="dark")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/")
    expect(page.locator('[data-count="snapshot"]')).to_have_text("3")
    page.locator('#btn-nav-logout').click()
    expect(page.locator('#auth-status')).to_have_text('Signed out successfully.')
    expect(page.locator('#btn-nav-login')).to_be_visible()
    expect(page.locator('[data-count="snapshot"]')).to_have_text("2")
    page.add_init_script("localStorage.removeItem('jurismon_token')")
    page.goto(base + "/account")
    expect(page.locator('#state-signed-out')).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert errors == []


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("status,state", [("active", "state-active"), ("suspended", "state-paused"), ("cancelled", "state-cancelled-in-period"), ("cancelled_expired", "state-cancelled-expired")])
def test_real_subscription_account_states(local_browser, mode, status, state):
    from datetime import datetime, timezone, timedelta
    page, base, repository = local_browser
    login_customer(page, base, repository)
    user = repository.get_user_by_email("browser@example.invalid")
    billing = (datetime.now(timezone.utc) + timedelta(days=-2 if status == "cancelled_expired" else 15)).isoformat()
    repository.record_subscription("I-LOCAL-QA", "professional_monthly",
        "cancelled" if status == "cancelled_expired" else status,
        user_email=user["email"], user_id=user["id"], next_billing_at=billing)
    page.emulate_media(color_scheme=mode)
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(base + "/account")
    expect(page.locator('#' + state)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_real_pending_search_and_logout_loading(local_browser):
    import time
    page, base, repository = local_browser
    seed_search(repository, 3)
    login_customer(page, base, repository)
    page.goto(base + "/")
    expect(page.locator('[data-count="snapshot"]')).to_have_text("3")
    # Delay delivery of the genuine server response, without changing its data.
    def delayed_response(route):
        response = route.fetch()
        time.sleep(0.5)
        route.fulfill(response=response)
    page.route("**/api/search?*", delayed_response)
    page.locator('#btn-nav-logout').click()
    expect(page.locator('.skel-row')).to_have_count(5)
    expect(page.locator('[data-count="snapshot"]')).to_have_text("2")


def test_login_success_feedback_and_pending_results(local_browser):
    page, base, repository = local_browser
    repository.create_user("signin@example.invalid", auth.get_password_hash("browser-password"), "QA", is_verified=1)
    repository.activate_user_trial("signin@example.invalid")
    page.goto(base + "/")
    page.locator('#btn-nav-login').click()
    page.locator('#login-email').fill("signin@example.invalid")
    page.locator('#login-password').fill("browser-password")
    page.locator('#btn-submit-login').click()
    expect(page.locator('#auth-status')).to_have_text("Signed in successfully.")
    expect(page.locator('#btn-nav-logout')).to_be_visible()


def test_older_search_response_cannot_replace_new_results(local_browser):
    page, base, repository = local_browser
    seed_search(repository, 3)
    login_customer(page, base, repository)
    page.goto(base + "/")
    expect(page.locator('.result')).to_have_count(3)
    held = []
    def hold_old(route):
        held.append((route, route.fetch()))
    page.route("**/api/search?q=0", hold_old)
    page.locator('#q').fill("0")
    expect(page.locator('.skel-row')).to_have_count(5)
    # Let the browser deliver the pending route callback.
    page.wait_for_timeout(400)
    assert held
    page.locator('#q').fill("zoning")
    expect(page.locator('.result')).to_have_count(3)
    held[0][0].fulfill(response=held[0][1])
    page.wait_for_timeout(200)
    expect(page.locator('.result')).to_have_count(3)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("signed_in", [False, True])
def test_admin_mobile_header_fits(local_browser, mode, signed_in):
    page, base, repository = local_browser
    if signed_in:
        response = page.request.post(base + "/api/admin/login", data={"email": auth.ADMIN_EMAIL, "password": "local-browser-password"})
        assert response.ok
        page.add_init_script("localStorage.setItem('jurismon_admin_token', " + repr(response.json()["access_token"]) + ")")
    page.set_viewport_size({"width": 375, "height": 812})
    page.emulate_media(color_scheme=mode)
    page.goto(base + "/admin")
    expect(page.locator('#btn-logout') if signed_in else page.locator('#auth-gate')).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), page.evaluate("() => [...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName, cls:e.className, id:e.id, right:e.getBoundingClientRect().right})).slice(0,15)")
